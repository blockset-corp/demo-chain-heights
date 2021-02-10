from collections import defaultdict
from django.shortcuts import render
from django.http import JsonResponse
from .models import CheckInstance, ChainHeightResult, CHECK_TYPE_BLOCK_HEIGHT


def index(request):
    context = get_difftable_context(request)
    return render(request, 'app/index.html', context)


def difftable_partial(request):
    context = get_difftable_context(request)
    return render(request, 'app/difftable.html', context)


def get_difftable_context(request):
    context = {
        'results_by_service_by_chain': {},
        'chain_heights': {},
        'chains': [],
        'services': [],
        'check': None
    }
    check, height_results = get_check_and_results(request)
    if height_results is not None:
        all_heights = defaultdict(list)
        chain_set = set()
        service_set = set()
        for result in height_results:
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
            check_instance=check
        ).select_related(
            'blockchain', 'blockchain__service', 'best_result__blockchain',
            'best_result__blockchain__service'
        )
    return check, results


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
