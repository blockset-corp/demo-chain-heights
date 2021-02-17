import time
import traceback
from collections import namedtuple
from django.utils import timezone
from celery import shared_task, chord
from celery.utils.log import get_task_logger
from requests import exceptions as requests_exceptions

from .checkers import get_all_check_runners
from .models import Service, Blockchain, CheckInstance, ChainHeightResult, CheckError, \
    RESULT_STATUS_OK, RESULT_STATUS_WARN, RESULT_STATUS_ERR, CHECK_TYPE_BLOCK_HEIGHT, \
    ERROR_TAG_TIMEOUT, ERROR_TAG_SYSTEM, ERROR_TAG_SSL, ERROR_TAG_ENCODING, ERROR_TAG_HTTP, \
    ERROR_TAG_UNKNOWN, ERROR_TAG_CONNECTION, CHECK_TYPE_PING, PingResult

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
