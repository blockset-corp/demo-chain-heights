from collections import defaultdict
from django.db.models import Count, Prefetch, Max, OuterRef, F, Subquery
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import Service, CheckInstance, ChainHeightResult, CheckError, Blockchain, \
    CHECK_TYPE_BLOCK_HEIGHT, PingResult, BlockValidationInstance, BlockValidationResult


def index(request):
    context = {}
    context.update(get_difftable_context(request))
    context.update(get_validtable_context(request))
    return render(request, 'app/index.html', context)


def difftable_partial(request):
    context = get_difftable_context(request)
    return render(request, 'app/difftable.html', context)


def validtable_partial(request):
    context = get_validtable_context(request)
    return render(request, 'app/validtable.html', context)


def service_detail(request, service_slug):
    service = get_object_or_404(Service, slug=service_slug)
    errors = CheckError.objects.for_service(service).select_related(
        'blockchain').order_by('-pk')
    errors_paginator = Paginator(errors, 10)
    errors_page = request.GET.get('error_page', None)
    context = {
        'service': service,
        'errors_page': errors_paginator.get_page(errors_page),
        'error_counts': CheckError.objects.for_service(service).get_error_counts(),
        'ping_ticks': PingResult.objects.filter(service=service).get_minutely_stats()
    }
    recent_checks = CheckInstance.objects.filter(
        type__exact=CHECK_TYPE_BLOCK_HEIGHT
    ).exclude(completed__isnull=True).order_by('-completed')
    if recent_checks.count() > 0:
        latest_check = recent_checks.first()
        chain_info = ChainHeightResult.objects.for_service(service).get_hourly_stats()
        context['latest_check'] = latest_check
        latest_check_results = ChainHeightResult.objects.for_service(
            service, check_instance=latest_check
        ).common_related()
        for height_result in latest_check_results:
            chain_info[height_result.blockchain.slug]['latest_height'] = height_result
            chain_info[height_result.blockchain.slug][
                'script_tag'] = f'{height_result.blockchain.slug}-data'
        chain_ids = list(chain_info.keys())
        chain_ids.sort()
        context['all_chains'] = [chain_info[k] for k in chain_ids]
        context['all_chain_ids'] = chain_ids
        if len(chain_ids) > 0:
            context['height_avg_labels'] = chain_info[chain_ids[0]]['labels']
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
            context['chain_metas'][
                result.blockchain.meta.chain_slug] = result.blockchain.meta
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


def get_validtable_context(request):
    context = {}
    height_count = 100
    chains = Blockchain.objects.annotate(
        results_count=Count('validation_results')
    ).filter(
        results_count__gt=0, service__private=False
    ).select_related(
        'service', 'meta'
    )
    services = defaultdict(dict)
    for chain in chains:
        service = services[chain.service.slug]
        service.setdefault('service', chain.service)
        service.setdefault('chains', [])
        service['chains'].append({
            'chain': chain,
            'heights': list(chain.validation_results.filter().order_by('height')[:60])
        })
    for svc_ctx in services.values():
        svc_ctx['chains'].sort(key=lambda c: c['chain'].slug)
    context['block_validations'] = sorted(services.items())
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
            blockchain__service__private=False
        ).exclude(blockchain__meta__isnull=True).select_related(
            'blockchain', 'blockchain__service', 'blockchain__meta',
            'best_result__blockchain', 'best_result__blockchain__service'
        )
    return check, results
