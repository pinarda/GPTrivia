# In your custom_tags.py
from django import template

register = template.Library()

@register.filter
def get_range(value):
    return range(1, value + 1)


@register.filter(name='zip')
def zip_lists(a, b):
    return zip(a, b)

@register.filter
def index(sequence, position):
    try:
        return sequence[position]
    except IndexError:
        return ''

@register.filter
def multiply(value, arg):
    return value * arg