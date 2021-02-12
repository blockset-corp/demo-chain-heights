import datetime
from collections import defaultdict
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import Trunc
from django.utils import timezone
from .models import Service, CheckInstance, ChainHeightResult, CheckError, CHECK_TYPE_BLOCK_HEIGHT


def index(request):
    context = get_difftable_context(request)
    return render(request, 'app/index.html', context)


def difftable_partial(request):
    context = get_difftable_context(request)
    return render(request, 'app/difftable.html', context)


def service_detail(request, service_slug):
    service = get_object_or_404(Service, slug=service_slug)
    errors = CheckError.objects.for_service(service).select_related('blockchain').order_by('-pk')
    errors_paginator = Paginator(errors, 10)
    errors_page = request.GET.get('error_page', None)
    context = {
        'service': service,
        'errors_page': errors_paginator.get_page(errors_page),
        'error_counts': get_error_counts(CheckError.objects.for_service(service))
    }
    recent_checks = CheckInstance.objects.filter(
        type__exact=CHECK_TYPE_BLOCK_HEIGHT
    ).exclude(completed__isnull=True).order_by('-completed')
    if recent_checks.count() > 0:
        latest_check = recent_checks.first()
        context['latest_check'] = latest_check
        context['latest_check_results'] = ChainHeightResult.objects.filter(
            check_instance=latest_check,
            blockchain__service=service
        ).exclude(blockchain__meta__isnull=True).select_related(
            'blockchain', 'blockchain__service', 'blockchain__meta',
            'best_result__blockchain', 'best_result__blockchain__service'
        )
    return render(request, 'app/service_detail.html', context)


def error_detail(request, error_id):
    error = get_object_or_404(CheckError, pk=error_id)
    context = {
        'error': error,
        'height_results': ChainHeightResult.objects.filter(error_details=error)
    }
    return render(request, 'app/error_detail.html', context)


def json_summary(request):
    raw_objects = defaultdict(lambda: defaultdict(dict))
    check, height_results = get_check_and_results(request)
    if height_results is not None:
        for result in height_results:
            raw_objects[result.blockchain.slug][result.blockchain.service.slug] = result

    serialized_objects = defaultdict(lambda: defaultdict(dict))
    for chain_id, services in raw_objects.items():
        for service_id, height_result in services.items():
            serialized_objects[chain_id][service_id] = {
                'service': height_result.service_slug(),
                'blockchain': height_result.blockchain_slug(),
                'difference_from_best': height_result.difference_from_best(),
                'difference_from_best_status': height_result.difference_from_best_status(),
                'duration_ms': height_result.duration_ms(),
                'best_service': height_result.best_service(),
                'height': height_result.height,
                'status': height_result.get_status_display(),
                'error': height_result.error
            }
    ret = {
        'check_id': check.pk,
        'check_started': check.started,
        'check_completed': check.completed,
        'chains': serialized_objects
    }
    return JsonResponse(ret)


def get_difftable_context(request):
    context = {
        'results_by_service_by_chain': {},
        'chain_heights': {},
        'chains': [],
        'services': [],
        'chain_metas': {},
        'check': None
    }
    check, height_results = get_check_and_results(request)
    if height_results is not None:
        context['check'] = check
        all_heights = defaultdict(list)
        chain_set = set()
        service_set = set()
        for result in height_results:
            context['chain_metas'][result.blockchain.meta.chain_slug] = result.blockchain.meta
            if result.difference_from_best() == 0:
                context['chain_heights'][result.blockchain.slug] = result.height
            all_heights[result.blockchain.slug].append(result.height)
            key = result.blockchain.service.slug + result.blockchain.slug
            context['results_by_service_by_chain'][key] = result
            chain_set.add(result.blockchain.slug)
            service_set.add(result.blockchain.service.slug)
        chains_to_ignore = set()
        for chain_id in chain_set:
            if sum(all_heights[chain_id]) == 0:
                chains_to_ignore.add(chain_id)
        context['chains'] = list(chain_set - chains_to_ignore)
        context['chains'].sort()
        context['services'] = list(service_set)
        context['services'].sort()
    return context


def get_check_and_results(request):
    check, results = (None, None)
    check_instances = CheckInstance.objects.filter(
        type__exact=CHECK_TYPE_BLOCK_HEIGHT,
    ).exclude(completed__isnull=True).order_by('-completed')
    if check_instances.count() > 0:
        check = check_instances.first()
        results = ChainHeightResult.objects.filter(
            check_instance=check,
        ).exclude(blockchain__meta__isnull=True).select_related(
            'blockchain', 'blockchain__service', 'blockchain__meta',
            'best_result__blockchain', 'best_result__blockchain__service'
        )
    return check, results


def get_error_counts(qs, distance=datetime.timedelta(days=7)):
    tick_time_format = '%y-%m-%d %H:00'
    now = timezone.now()
    then = now - distance
    counts = qs.filter(created__gt=then).annotate(
        started_hour=Trunc('created', 'hour'),
    ).values('tag', 'started_hour').annotate(errors=Count('tag'))
    seen_tags = set()
    hour_buckets = defaultdict(dict)
    for agg in counts:
        seen_tags.add(agg['tag'])
        hour_buckets[agg['tag']][agg['started_hour'].strftime(tick_time_format)] = agg['errors']
    hours = int(distance.total_seconds() / 60 / 60)
    ticks = {'labels': [], 'data': defaultdict(list)}
    for i in range(hours, -1, -1):
        date = (now - datetime.timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
        tick_date = date.strftime(tick_time_format)
        ticks['labels'].append(tick_date)
        for tag in seen_tags:
            value = hour_buckets[tag].get(tick_date, 0)
            ticks['data'][tag].append(value)
    return ticks
