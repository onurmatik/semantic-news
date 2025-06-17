from django import template
register = template.Library()


@register.filter
def get_item(dict_obj, key):
    return dict_obj.get(key, 0)
