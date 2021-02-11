from django import template

register = template.Library()

@register.simple_tag
def get_result(results, chain_id, service_id):
    key = service_id + chain_id
    ret = results.get(key, None)
    return ret


@register.simple_tag
def get_height(heights, chain_id):
    return heights.get(chain_id, None)


@register.simple_tag
def get_chain_meta(metas, chain_id):
    chain_slug, _ = chain_id.split('-')
    return metas[chain_slug]

@register.simple_tag
def is_testnet(meta, chain_id):
    _, network = chain_id.split('-')
    if network in meta.testnet_slugs:
        return True
    return False


@register.filter
def network_name(name):
    _, network = name.split('-')
    return network.title()
