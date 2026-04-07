from django import template
register = template.Library()

@register.simple_tag(takes_context=True)
def url_replace(context, field, value):
    request = context['request']
    d = request.GET.copy()
    d[field] = value
    return d.urlencode()