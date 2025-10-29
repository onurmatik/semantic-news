from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe


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
