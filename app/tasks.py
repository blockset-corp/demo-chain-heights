from dataclasses import asdict
from celery import shared_task
from celery.utils.log import get_task_logger
from celery.contrib import rdb
from .checkers import get_all_check_runners
from .models import Service


logger = get_task_logger('app.tasks')


@shared_task
def update_all_supported_blockchains():
    # rdb.set_trace()
    logger.info('update all supported blockchains')
    services = Service.objects.all()
    logger.info(f'queueing updates for {len(services)} services')
    for svc in Service.objects.all():
        print(f'queueing blockchain updates for {svc.slug}')
        update_supported_blockchain.apply_async((svc.slug,))


@shared_task
def update_supported_blockchain(service_slug):
    logger.info(f'updating supported blockchain {service_slug}')
    runner = get_check_runners().get(service_slug)
    chains = runner.get_supported_chains()
    svc = Service.objects.get(slug=service_slug)
    svc.supported_chains = [asdict(c) for c in chains]
    svc.save()


check_runners = None


def get_check_runners():
    global check_runners
    if check_runners is None:
        check_runners = get_all_check_runners()
    return check_runners
