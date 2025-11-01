from __future__ import annotations

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

import markdown as md

register = template.Library()


@register.filter(name="markdownify", needs_autoescape=True)
def markdownify(value, autoescape: bool = True):
    """Render ``value`` as Markdown and mark the result as safe HTML."""

    if value is None:
        return ""

    text = conditional_escape(value) if autoescape else value
    text = str(text)
    html = md.markdown(
        text,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html5",
    )
    return mark_safe(html)
