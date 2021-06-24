import time
import traceback
from datetime import timedelta
from collections import namedtuple
from django.utils import timezone
from celery import shared_task, chord
from celery.utils.log import get_task_logger
from requests import exceptions as requests_exceptions

from .checkers import get_all_check_runners, CHECK_BLOCK_VALIDATION
from .models import Service, Blockchain, CheckInstance, ChainHeightResult, CheckError, \
    RESULT_STATUS_OK, RESULT_STATUS_WARN, RESULT_STATUS_ERR, CHECK_TYPE_BLOCK_HEIGHT, \
    ERROR_TAG_TIMEOUT, ERROR_TAG_SYSTEM, ERROR_TAG_SSL, ERROR_TAG_ENCODING, ERROR_TAG_HTTP, \
    ERROR_TAG_UNKNOWN, ERROR_TAG_CONNECTION, CHECK_TYPE_PING, PingResult, \
    BlockValidationInstance, BlockValidationResult

logger = get_task_logger('app.tasks')


@shared_task
def update_all_supported_blockchains():
    services = Service.objects.all()
    for svc in services:
        update_supported_blockchain.apply_async((svc.slug,))


@shared_task
def update_supported_blockchain(service_slug):
    runner = get_check_runners().get(service_slug, None)
    if runner is None:
        return
    chains_result = runner.get_supported_chains()
    svc = Service.objects.get(slug=service_slug)
    for chain in chains_result:
        existing = Blockchain.objects.filter(slug=chain.slug, service=svc, is_testnet=chain.testnet)
        if existing.count():
            existing.first().create_meta_if_not_exists()
            continue
        blockchain = Blockchain.objects.create(
            name=chain.name,
            slug=chain.slug,
            service=svc,
            is_testnet=chain.testnet
        )
        blockchain.create_meta_if_not_exists()


@shared_task
def update_all_blockchain_heights():
    services = Service.objects.all()
    check = CheckInstance.objects.create(started=timezone.now(), type=CHECK_TYPE_BLOCK_HEIGHT)
    jobs = []
    for svc in services:
        runner = get_check_runners().get(svc.slug, None)
        if runner is None:
            continue
        chains = Blockchain.objects.filter(service=svc, ignore=False).exclude(meta__isnull=True)
        if svc.bulk_chain_query and 'height_bulk' in runner.get_supported_checks():
            jobs.append(update_blockchain_heights_bulk.s(svc.slug, [chain.slug for chain in chains], check.pk))
        elif 'height' in runner.get_supported_checks():
            for chain in chains:
                jobs.append(update_blockchain_height.s(svc.slug, chain.slug, check.pk))
    chord(jobs, complete_check.si(check.pk)).apply_async()


@shared_task
def update_all_pings():
    check = CheckInstance.objects.create(started=timezone.now(), type=CHECK_TYPE_PING)
    services = Service.objects.all()
    jobs = []
    for svc in services:
        runner = get_check_runners().get(svc.slug, None)
        if runner is not None and 'ping' in runner.get_supported_checks():
            jobs.append(do_ping.s(svc.slug, check.pk))
    chord(jobs, complete_ping_check.si(check.pk)).apply_async()


@shared_task
def validate_all_blockchains():
    fullnode_service = Service.objects.get(slug='fullnode')
    supported_chains = Blockchain.objects.filter(service=fullnode_service, ignore=False).exclude(meta__isnull=True)
    for chain in supported_chains:
        update_canonical_chain.apply_async(args=(chain.pk,))


@shared_task
def update_canonical_chain(blockchain_id):
    chain = Blockchain.objects.get(pk=blockchain_id)
    # determine most recent result
    most_recent = BlockValidationInstance.objects.filter(
        blockchain=chain, timed_out=False
    ).order_by('-end_height').first()

    runner = get_check_runners().get('fullnode')
    current_height = runner.get_block_height(chain.slug)
    finality_depth = chain.meta.testnet_finality_depth if chain.is_testnet else chain.meta.mainnet_finality_depth
    final_block_height = current_height.height - finality_depth

    start_height, end_height = None, final_block_height

    if most_recent is None:
        # no block validations for this chain yet, kick things off by validating the most recent 100 blocks
        print(f'no block validations for {chain} yet')
        start_height = final_block_height - 10
    elif most_recent.completed and most_recent.end_height < final_block_height:
        print(f'most recent block validation for {chain} complete, will initiate checking '
              f'{most_recent.end_height} - {final_block_height}')
        # if the most recent BVI is complete, and new blocks are ready to be validated, start a new validation round
        start_height = most_recent.end_height
    elif not most_recent.completed:
        # if the most recent BVI has not been completed, ensure it is not timed out
        timeout = timezone.now() - timedelta(hours=1)
        if most_recent.started <= timeout:
            print(f'timing out {most_recent}')
            most_recent.completed = timezone.now()
            most_recent.timed_out = True
            most_recent.save()

    if start_height is not None:
        instance = BlockValidationInstance.objects.create(
            blockchain=chain,
            start_height=start_height,
            end_height=end_height,
            started=timezone.now()
        )
        jobs = []
        for i in range(instance.start_height, instance.end_height):
            jobs.append(fetch_canonical_block.s(instance.pk, i))
        chord(jobs, perform_all_block_validations.si(instance.pk)).apply_async()


@shared_task(bind=True)
def fetch_canonical_block(task, validation_instance_id, height):
    instance = BlockValidationInstance.objects.get(pk=validation_instance_id)
    runner = get_check_runners().get('fullnode')
    resp = run_http_method(runner.get_block_at_height, instance.blockchain.slug, height)
    if resp.error:
        # can not absorb an error for canonical chain fetch failure, just retry
        print(f'canonical fetch failed at height {height} for instance {instance} failed with {resp.error}')
        raise task.retry(max_retries=13)
    BlockValidationResult.objects.create(
        blockchain=instance.blockchain,
        validation_instance=instance,
        service=instance.blockchain.service,
        started=resp.started_time,
        duration=resp.duration,
        status=resp.status,
        height=resp.result.height,
        block_hash=resp.result.hash,
        transaction_ids=resp.result.txids,
        is_canonical=True,
        missing_transaction_ids=[]
    )


@shared_task
def perform_all_block_validations(validation_instance_id):
    """
    Finalize the BVI for the canonical block, and kick off validations for any services that support it
    """
    instance = BlockValidationInstance.objects.get(pk=validation_instance_id)
    instance.completed = timezone.now()
    instance.save()

    services = Service.objects.all()
    for svc in services:
        runner = get_check_runners().get(svc.slug, None)
        # ensure the runner supports the check and chain we are looking at
        if runner is None or CHECK_BLOCK_VALIDATION not in runner.get_supported_checks():
            continue
        supported_chain_slugs = {c.slug for c in runner.get_supported_chains()}
        if instance.blockchain.slug not in supported_chain_slugs:
            continue
        chain = Blockchain.objects.get(service=svc, slug=instance.blockchain.slug)
        # ensure there isn't already a validation instance running
        existing_service_instance = BlockValidationInstance.objects.filter(
            blockchain=chain, timed_out=False, start_height=instance.start_height, end_height=instance.end_height
        ).first()
        if existing_service_instance:
            continue
        # kick off a validation for this service/chain/block range
        service_instance = BlockValidationInstance.objects.create(
            blockchain=chain,
            start_height=instance.start_height,
            end_height=instance.end_height,
            started=timezone.now()
        )
        jobs = []
        for i in range(service_instance.start_height, service_instance.end_height):
            canonical_block_result = BlockValidationResult.objects.get(validation_instance=instance, height=i)
            jobs.append(fetch_service_block.s(service_instance.pk, canonical_block_result.pk, i))
        chord(jobs, finalize_service_block_validation.si(service_instance.pk)).apply_async()


@shared_task(bind=True)
def fetch_service_block(task, validation_instance_id, canonical_block_id, height):
    instance = BlockValidationInstance.objects.get(pk=validation_instance_id)
    runner = get_check_runners().get(instance.blockchain.service.slug)
    resp = run_http_method(runner.get_block_at_height, instance.blockchain.slug, height)
    if resp.error:
        print(f'service fetch failed at height {height} for instance {instance} failed with {resp.error}')
        raise task.retry(max_retries=13)
    canonical_result = BlockValidationResult.objects.get(pk=canonical_block_id)
    kwargs = {
        'blockchain': instance.blockchain,
        'validation_instance': instance,
        'service': instance.blockchain.service,
        'started': resp.started_time,
        'duration': resp.duration,
        'status': resp.status,
        'height': resp.result.height,
        'block_hash': resp.result.hash,
        'transaction_ids': resp.result.txids,
        'canonical_result': canonical_result,
        'missing_transaction_ids': []
    }
    if resp.result.hash != canonical_result.block_hash:
        kwargs['hash_mismatch'] = True
    for txid in canonical_result.transaction_ids:
        if txid not in resp.result.txids:
            kwargs['missing_transaction_ids'].append(txid)
    BlockValidationResult.objects.create(**kwargs)


@shared_task
def finalize_service_block_validation(validation_instance_id):
    instance = BlockValidationInstance.objects.get(pk=validation_instance_id)
    instance.completed = timezone.now()
    instance.save()


@shared_task
def do_ping(service_slug, check_id):
    runner = get_check_runners().get(service_slug)
    result = run_http_method(runner.get_ping)
    service = Service.objects.get(slug=service_slug)
    kwargs = {
        'service': service,
        'check_instance_id': check_id,
        'started': result.started_time,
        'duration': result.duration,
        'status': result.status,
    }
    if result.error:
        result.error.service = service
        result.error.check_instance_id = check_id
        result.error.save()
        kwargs['error_details'] = result.error
    PingResult.objects.create(**kwargs)


@shared_task
def complete_ping_check(check_id):
    check = CheckInstance.objects.get(pk=check_id)
    check.completed = timezone.now()
    check.save()


@shared_task
def update_blockchain_heights_bulk(service_slug, chain_ids, check_id):
    runner = get_check_runners().get(service_slug)
    results = run_http_method(runner.get_all_block_heights, chain_ids)
    all_heights = results.result
    if all_heights is None:
        all_heights = [None for _ in chain_ids]
    service = Service.objects.get(slug=service_slug)
    if results.error is not None:
        all_blockchain, _ = Blockchain.objects.get_or_create(
            name='ALL',
            service=service,
            slug=service_slug + '-all',
        )
        results.error.check_instance_id = check_id
        results.error.blockchain = all_blockchain
        results.error.save()
    for chain_id, chain_height in zip(chain_ids, all_heights):
        kwargs = {
            'blockchain': Blockchain.objects.get(service__slug=service_slug, slug=chain_id),
            'check_instance_id': check_id,
            'started': results.started_time,
            'duration': results.duration / int(len(chain_ids) * .8),
            'status': results.status
        }
        if chain_height is not None:
            kwargs['height'] = chain_height.height
        if results.error is not None:
            kwargs['error'] = results.error.error_message
            kwargs['error_details'] = results.error
        ChainHeightResult.objects.create(**kwargs)


@shared_task
def update_blockchain_height(service_slug, chain_id, check_id):
    runner = get_check_runners().get(service_slug)
    blockchain = Blockchain.objects.get(service__slug=service_slug, slug=chain_id)
    result = run_http_method(runner.get_block_height, chain_id)
    kwargs = {
        'blockchain': blockchain,
        'check_instance_id': check_id,
        'started': result.started_time,
        'duration': result.duration,
        'status': result.status
    }
    if result.result is not None:
        kwargs['height'] = result.result.height
    if result.error is not None:
        result.error.blockchain = blockchain
        result.error.check_instance_id = check_id
        result.error.save()
        kwargs['error'] = result.error.error_message
        kwargs['error_details'] = result.error
    ChainHeightResult.objects.create(**kwargs)


@shared_task
def complete_check(check_id):
    check = CheckInstance.objects.get(pk=check_id)
    check.completed = timezone.now()
    check.save()

    results = ChainHeightResult.objects.filter(check_instance=check).select_related('blockchain')
    best = {}

    # calculate the best height for each blockchain id
    for result in results:
        if result.blockchain.slug in best:
            current_best = best[result.blockchain.slug]
            if result.height > current_best.height:
                best[result.blockchain.slug] = result
        else:
            best[result.blockchain.slug] = result

    # save the difference from best height in each result
    for result in results:
        result.best_result = best[result.blockchain.slug]
        result.save()


HttpMethodResult = namedtuple('HttpMethodResult', (
    'result', 'error', 'status', 'started_time', 'duration'))


def run_http_method(method, *args, **kwargs):
    error = None
    result = None
    status = RESULT_STATUS_OK
    started_time = timezone.now()
    started_ns = time.time_ns()
    try:
        result = method(*args, **kwargs)
    except requests_exceptions.RequestException as e:
        error = CheckError(
            error_message=str(e),
            traceback=''.join(traceback.format_exc()),
            tag=classify_error_tag(e)
        )
        if e.request is not None:
            error.method = e.request.method
            error.url = e.request.url
            error.request_headers = {k: v for k, v in e.request.headers.items()}
            error.request_body = e.request.body if e.request.body is not None else ''
        if e.response is not None:
            error.status_code = e.response.status_code
            error.response_headers = {k: v for k, v in e.response.headers.items()}
            error.response_body = e.response.text if e.response.text is not None else ''
            if 400 <= e.response.status_code < 500:
                status = RESULT_STATUS_WARN  # error in the 400s are not a service failure
            else:
                status = RESULT_STATUS_ERR
        else:
            status = RESULT_STATUS_ERR
    except Exception as e:
        error = CheckError(
            error_message=str(e),
            traceback=''.join(traceback.format_exc()),
            tag=ERROR_TAG_SYSTEM
        )
        status = RESULT_STATUS_ERR
    end_ns = time.time_ns()
    return HttpMethodResult(result, error, status, started_time, (end_ns - started_ns) / 1_000_000)


def classify_error_tag(exc):
    e = requests_exceptions
    tag_map = {
        ERROR_TAG_HTTP: (e.HTTPError, e.TooManyRedirects),
        ERROR_TAG_SSL: (e.SSLError,),
        ERROR_TAG_SYSTEM: (e.ProxyError, e.URLRequired, e.InvalidURL),
        ERROR_TAG_ENCODING: (e.ChunkedEncodingError, e.ContentDecodingError),
        ERROR_TAG_TIMEOUT: (e.Timeout,),
        ERROR_TAG_CONNECTION: (e.ConnectionError,),
    }
    # try to classify based on exception class
    for k, v in tag_map.items():
        for exc_cls in v:
            if isinstance(exc, exc_cls):
                return k
    return ERROR_TAG_UNKNOWN


check_runners = None


def get_check_runners():
    global check_runners
    if check_runners is None:
        check_runners = get_all_check_runners()
    return check_runners
