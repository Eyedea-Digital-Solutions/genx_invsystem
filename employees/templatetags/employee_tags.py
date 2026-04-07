from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Lookup dictionary[key], returns None if missing."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None