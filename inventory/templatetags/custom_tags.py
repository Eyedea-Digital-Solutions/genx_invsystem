from django import template
register = template.Library()

@register.filter
def getfield(form, field_name):
    return form[field_name]