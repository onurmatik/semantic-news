"""Utilities for rendering topic widget sections."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING

from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from .base import Widget, WidgetAction

if TYPE_CHECKING:  # pragma: no cover - import used for type checking only
    from semanticnews.topics.models import TopicSection


logger = logging.getLogger(__name__)


@dataclass
class RenderableSection:
    """Lightweight descriptor used by templates to render a section."""

    section: "TopicSection"
    widget: Widget
    content: Mapping[str, Any]
    edit_mode: bool = False
    template_name: str = ""
    form_template: str = ""
    icon: str = ""
    schema: Optional[Any] = None
    context_structure: Dict[str, Any] = field(default_factory=dict)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    rendered: Optional[str] = None
    key: str = ""


def _serialise_action(widget: Widget, action: WidgetAction, index: int) -> Dict[str, Any]:
    """Return a JSON-serialisable payload describing the widget action."""

    name = getattr(action, "name", "") or ""
    identifier = getattr(action, "id", None)
    if identifier is None:
        base = name or widget.name or widget.__class__.__name__
        identifier = f"{base}-{index}".replace(" ", "-").lower()

    payload: Dict[str, Any] = {
        "id": identifier,
        "name": name,
        "icon": getattr(action, "icon", "") or "",
    }

    tools = getattr(action, "tools", None)
    if tools:
        payload["tools"] = list(tools)

    prompt = getattr(action, "prompt", None)
    if prompt:
        payload["prompt"] = prompt

    schema = getattr(action, "schema", None)
    if schema is not None:
        payload["schema"] = schema

    return payload


def build_renderable_section(
    section: "TopicSection", *, edit_mode: bool = False
) -> RenderableSection:
    """Build a renderable descriptor for the provided topic section."""

    widget = section.widget

    # NORMALISE CONTENT FOR PARAGRAPH WIDGET
    raw_content = section.content or {}
    if widget.name == "paragraph":
        if "text" not in raw_content and "result" in raw_content:
            content = dict(raw_content)
            content["text"] = content["result"]
        else:
            content = raw_content
    else:
        content = raw_content

    template_context = {
        "section": section,
        "widget": widget,
        "content": content,
        "edit_mode": edit_mode,
    }

    rendered: Optional[str] = None
    template_name = widget.template or ""
    if template_name:
        try:
            rendered = render_to_string(template_name, template_context)
        except TemplateDoesNotExist:
            logger.warning(
                "Topic widget template '%s' is not available", template_name
            )
        except Exception:  # pragma: no cover - template rendering is best effort
            logger.exception(
                "Failed to render topic widget template '%s'", template_name
            )

    actions = [
        _serialise_action(widget, action, index)
        for index, action in enumerate(widget.get_actions(), start=1)
    ]

    return RenderableSection(
        section=section,
        widget=widget,
        content=content,
        edit_mode=edit_mode,
        template_name=template_name,
        form_template=widget.form_template or "",
        icon=widget.icon or "",
        schema=getattr(widget, "schema", None),
        context_structure=dict(getattr(widget, "context_structure", {}) or {}),
        actions=actions,
        context=template_context,
        rendered=rendered,
    )

