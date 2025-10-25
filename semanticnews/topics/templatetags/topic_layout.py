from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from ..layouts import (
    PRIMARY_FIXED_BASE_MODULES,
    REORDERABLE_BASE_MODULES,
    SIDEBAR_FIXED_BASE_MODULES,
)


register = template.Library()


@register.simple_tag(takes_context=True)
def render_topic_module(context, module):
    """Render a layout module using its resolved template configuration."""

    template_name = module.get("template_name")
    if not template_name:
        return ""

    base_context = context.flatten()
    overrides = module.get("context_overrides", {})
    if overrides:
        base_context.update(overrides)
    base_context["module"] = module

    request = context.get("request")
    rendered = render_to_string(template_name, base_context, request=request)
    return mark_safe(rendered)


def _normalize_base_key(value):
    if value is None:
        return ""
    return str(value)


@register.filter
def is_reorderable_module(base_module_key):
    """Return ``True`` if ``base_module_key`` is user-reorderable."""

    return _normalize_base_key(base_module_key) in REORDERABLE_BASE_MODULES


@register.filter
def is_primary_fixed_module(base_module_key):
    """Return ``True`` for fixed primary-column modules."""

    return _normalize_base_key(base_module_key) in PRIMARY_FIXED_BASE_MODULES


@register.filter
def is_sidebar_fixed_module(base_module_key):
    """Return ``True`` for fixed sidebar modules."""

    return _normalize_base_key(base_module_key) in SIDEBAR_FIXED_BASE_MODULES
