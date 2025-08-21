import re

from django import template
import markdown as md
from django.utils.safestring import mark_safe
from django.utils.text import Truncator

register = template.Library()


@register.filter(name='markdownify')
def markdownify(text):
    return mark_safe(md.markdown(text, extensions=['markdown.extensions.fenced_code']))


@register.filter(name='markdown_truncate_html')
def markdown_truncate_html(text, num_words=None):
    """
    1) Render Markdown → HTML (with fenced code + nl2br)
    2) Strip the outer <p>…</p>, even if it has attributes
    3) If num_words is provided and >0, truncate to that many words
       preserving inner tags; otherwise return full HTML.
    """
    # 1) Markdown → HTML
    html = md.markdown(
        text or "",
        extensions=[
            'markdown.extensions.fenced_code',
            'markdown.extensions.nl2br',
        ]
    )

    # 2) Strip outer <p>…</p> wrapper
    html = re.sub(
        r'^<p[^>]*>(.*)</p>\s*$',
        r'\1',
        html,
        flags=re.DOTALL
    )

    # 3) Optional truncate
    if num_words is None:
        return mark_safe(html)

    try:
        count = int(num_words)
    except (TypeError, ValueError):
        return mark_safe(html)

    if count <= 0:
        return mark_safe(html)

    truncated = Truncator(html).words(count, html=True, truncate='…')
    return mark_safe(truncated)
