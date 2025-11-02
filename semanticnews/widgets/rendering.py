"""Utilities for rendering widget sections and normalising content."""

from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace
from typing import Any

from .models import Widget


DEFAULT_SECTION_TEMPLATE = "widgets/topics/widgets/fallback.html"


def normalize_widget_content(widget: Widget, content: Any) -> Any:
    """Return content normalised according to the widget's response format."""

    response_format = getattr(widget, "response_format", None) or {}
    response_type = response_format.get("type")

    if response_type == "markdown":
        if isinstance(content, dict):
            required_order = response_format.get("sections") or []
            if required_order:
                ordered: OrderedDict[str, Any] = OrderedDict()
                for key in required_order:
                    if key in content:
                        ordered[key] = content[key]
                for key, value in content.items():
                    if key not in ordered:
                        ordered[key] = value
                return ordered
            return content
        return {}

    if response_type in {"bulleted_metrics", "timeline", "link_list", "image_list"}:
        return content if isinstance(content, list) else []

    if response_type == "json_object":
        return content if isinstance(content, dict) else {}

    return content


def resolve_widget_template(widget: Widget) -> str:
    """Return the Django template path used to render the widget response."""

    template = getattr(widget, "template", None)
    if isinstance(template, str) and template.strip():
        return template.strip()
    return DEFAULT_SECTION_TEMPLATE


def build_renderable_section(section, *, edit_mode: bool = False):
    """Create a descriptor object used when rendering widget sections."""

    widget = section.widget
    normalized_content = normalize_widget_content(widget, section.content)
    template_path = resolve_widget_template(widget)
    descriptor = SimpleNamespace(
        section=section,
        widget=widget,
        template_path=template_path,
        response_type=(widget.response_format or {}).get("type"),
        content=normalized_content,
        format=widget.response_format or {},
        edit_mode=edit_mode,
    )
    descriptor.key = f"section:{getattr(section, 'id', None) or 'unsaved'}"
    return descriptor

