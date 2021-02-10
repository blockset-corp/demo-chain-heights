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
