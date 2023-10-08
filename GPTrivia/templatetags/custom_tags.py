# In your custom_tags.py
from django import template

register = template.Library()

@register.inclusion_tag('your_app_name/range_template.html')
def input_range(count, prefix, label, name):
    return {
        'range': range(1, count + 1),
        'prefix': prefix,
        'label': label,
        'name': name
    }
