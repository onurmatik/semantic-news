from __future__ import annotations

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

import markdown as md
from bleach.sanitizer import Cleaner

register = template.Library()


MARKDOWN_EXTENSIONS = ["extra", "sane_lists", "smarty"]

MARKDOWN_CLEANER = Cleaner(
    tags=[
        "a",
        "abbr",
        "acronym",
        "blockquote",
        "code",
        "dd",
        "dl",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "strong",
        "sup",
        "sub",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    ],
    attributes={
        "a": ["href", "title"],
        "abbr": ["title"],
        "acronym": ["title"],
        "img": ["alt", "src", "title"],
    },
    protocols=["http", "https", "mailto"],
    strip=True,
    strip_comments=True,
)


@register.filter(name="markdownify", needs_autoescape=True)
def markdownify(value, autoescape: bool = True):
    """Render ``value`` as Markdown, sanitize it, and mark the result as safe HTML."""

    if value is None:
        return ""

    text = conditional_escape(value) if autoescape else value
    text = str(text)
    html = md.markdown(
        text,
        extensions=MARKDOWN_EXTENSIONS,
        output_format="html5",
    )
    sanitized = MARKDOWN_CLEANER.clean(html)
    return mark_safe(sanitized)
