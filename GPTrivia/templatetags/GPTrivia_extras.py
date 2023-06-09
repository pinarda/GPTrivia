from django.template.defaulttags import register
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def zip_lists(list1, list2):
    return zip(list1, list2)

@register.filter(name='replace')
def replace(value, args):
    search, replace_with = args.split(',')
    return value.replace(search, replace_with)