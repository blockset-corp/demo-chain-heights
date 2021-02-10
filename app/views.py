from django.shortcuts import render
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
    check_instances = CheckInstance.objects.filter(
        type__exact=CHECK_TYPE_BLOCK_HEIGHT,
    ).exclude(completed__isnull=True).order_by('-completed')
    if check_instances.count() > 0:
        # import pdb;pdb.set_trace()
        context['check'] = check_instances.first()
        results = ChainHeightResult.objects.filter(
            check_instance=context['check']
        ).select_related(
            'blockchain', 'blockchain__service', 'best_result__blockchain',
            'best_result__blockchain__service'
        )
        chain_set = set()
        service_set = set()
        for result in results:
            if result.difference_from_best() == 0:
                context['chain_heights'][result.blockchain.slug] = result.height
            key = result.blockchain.service.slug + result.blockchain.slug
            context['results_by_service_by_chain'][key] = result
            chain_set.add(result.blockchain.slug)
            service_set.add(result.blockchain.service.slug)
        context['chains'] = list(chain_set)
        context['chains'].sort()
        context['services'] = list(service_set)
        context['services'].sort()
    return context
