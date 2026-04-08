from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Lookup dictionary[key], returns None if missing."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.simple_tag
def get_shift(shift_map, employee_id, date):
    """
    Lookup shift_map[(employee_id, date)] for the schedule grid.
    Usage: {% get_shift shift_map employee.pk day as shift %}
    """
    if isinstance(shift_map, dict):
        return shift_map.get((employee_id, date))
    return None


@register.filter
def stars_range(score):
    """Return a list of (filled: bool) for 5 stars. Used in templates."""
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 0
    return [{"filled": i < score} for i in range(5)]

