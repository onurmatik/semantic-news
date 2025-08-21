from django import template
from slugify import slugify


register = template.Library()


@register.filter(name='slugify')
def custom_slugify(value):
    return slugify(value)
