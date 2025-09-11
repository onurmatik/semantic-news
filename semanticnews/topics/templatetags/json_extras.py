import json
from django import template

register = template.Library()

@register.filter
def jsonify(value):
    """Serialize a Python object to JSON."""
    return json.dumps(value)
