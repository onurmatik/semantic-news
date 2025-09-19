from __future__ import annotations

from django import template
from django.urls import NoReverseMatch, translate_url

register = template.Library()


@register.simple_tag(takes_context=True)
def switch_language_url(context, language_code: str) -> str:
    """Return the current request path translated to the given language."""

    request = context.get("request")
    if request is None:
        return "/"

    current_path = request.get_full_path()

    try:
        return translate_url(current_path, language_code)
    except NoReverseMatch:
        return current_path
