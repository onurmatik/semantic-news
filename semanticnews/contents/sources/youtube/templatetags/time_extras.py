from django import template

register = template.Library()

@register.filter
def timestamp(seconds):
    """Format seconds as M:SS or H:MM:SS."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "0:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"
