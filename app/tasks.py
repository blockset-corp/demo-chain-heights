import time
from django.utils import timezone
from celery import shared_task
from celery.utils.log import get_task_logger
from .checkers import get_all_check_runners
from .models import Service, Blockchain, ChainHeightResult, RESULT_STATUS_OK, RESULT_STATUS_ERR


logger = get_task_logger('app.tasks')


@shared_task
def update_all_supported_blockchains():
    services = Service.objects.all()
    for svc in services:
        update_supported_blockchain.apply_async((svc.slug,))


@shared_task
def update_supported_blockchain(service_slug):
    runner = get_check_runners().get(service_slug)
    chains_result = runner.get_supported_chains()
    svc = Service.objects.get(slug=service_slug)
    for chain in chains_result:
        Blockchain.objects.get_or_create(
            name=chain.name,
            slug=chain.slug,
            service=svc,
            is_testnet=chain.testnet
        )


@shared_task
def update_all_blockchain_heights():
    services = Service.objects.all()
    for svc in services:
        chains = Blockchain.objects.filter(service=svc)
        for chain in chains:
            update_blockchain_height.apply_async((svc.slug, chain.slug))


@shared_task
def update_blockchain_height(service_slug, chain_id):
    runner = get_check_runners().get(service_slug)
    error = None
    height_result = None
    status = RESULT_STATUS_OK
    started_time = timezone.now()
    started_ns = time.time_ns()
    try:
        height_result = runner.get_block_height(chain_id)
    except Exception as e:
        error = str(e)
        status = RESULT_STATUS_ERR
    end_ns = time.time_ns()
    svc = Service.objects.get(slug=service_slug)
    kwargs = {
        'blockchain': Blockchain.objects.get(service=svc, slug=chain_id),
        'started': started_time,
        'duration': end_ns - started_ns,
        'status': status
    }
    if height_result is not None:
        kwargs['height'] = height_result.height
    if error is not None:
        kwargs['error'] = error
    ChainHeightResult.objects.create(**kwargs)


check_runners = None


def get_check_runners():
    global check_runners
    if check_runners is None:
        check_runners = get_all_check_runners()
    return check_runners
