"""Utilities for rendering topic widget sections."""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING

from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from .base import Widget, WidgetAction

if TYPE_CHECKING:  # pragma: no cover - import used for type checking only
    from semanticnews.topics.models import TopicSection

logger = logging.getLogger(__name__)


try:
    from pydantic import BaseModel
except Exception:
    BaseModel = None


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


def normalise_section_content(widget: Widget, section: "TopicSection") -> Dict[str, Any]:
    """
    Normalise TopicSection.content into the shape templates and forms expect.
    """

    raw = section.content or {}
    if not isinstance(raw, Mapping):
        raw = {}

    content: Dict[str, Any] = dict(raw)
    widget_name = widget.name or ""

    schema = getattr(widget, "schema", None)
    if BaseModel and isinstance(schema, type) and issubclass(schema, BaseModel):  # type: ignore[arg-type]
        defaults: Dict[str, Any] = {}
        try:
            instance = schema()
        except Exception:
            # Required fields with no defaults -> ignore schema defaults
            defaults = {}
        else:
            if hasattr(instance, "model_dump"):
                defaults = instance.model_dump()
            elif hasattr(instance, "dict"):
                defaults = instance.dict()
            else:
                defaults = {}
        merged = dict(defaults)
        merged.update(content)
        content = merged

    if widget_name == "paragraph":
        result_val = content.get("result")
        if "text" not in content and isinstance(result_val, str):
            content["text"] = result_val

    if widget_name == "image":
        image_source = (
            content.get("image_data")
            or content.get("image")
            or content.get("image_url")
            or content.get("url")
        )
        result_val = content.get("result")

        def _is_valid_image_source(value: str) -> bool:
            if not value:
                return False
            cleaned_value = value.strip()
            if cleaned_value.startswith(("http://", "https://")):
                return True
            if cleaned_value.lower().startswith("data:image/"):
                return True
            return False

        def _normalise_base64_image(value: str) -> str | None:
            if not value:
                return None
            cleaned_value = value.strip()
            if " " in cleaned_value:
                return None
            if not re.fullmatch(r"[A-Za-z0-9+/=\n\r]+", cleaned_value):
                return None
            try:
                decoded = base64.b64decode(cleaned_value, validate=True)
            except Exception:
                return None
            if not decoded:
                return None
            return f"data:image/png;base64,{cleaned_value}"

        if isinstance(image_source, str) and not _is_valid_image_source(image_source):
            image_source = None

        if not image_source and isinstance(result_val, str) and result_val.strip():
            cleaned = result_val.strip()
            if cleaned.startswith(("http://", "https://")):
                image_source = cleaned
            elif cleaned.lower().startswith("data:image/"):
                image_source = cleaned
            else:
                base64_candidate = _normalise_base64_image(cleaned)
                if base64_candidate:
                    image_source = base64_candidate

        content["image_data"] = image_source or ""
        content.setdefault("prompt", "")
        content["form_prompt"] = content.get("form_prompt", "") or ""
        content["form_image_url"] = content.get("form_image_url", "") or ""

    return content


def build_renderable_section(
    section: "TopicSection", *, edit_mode: bool = False
) -> RenderableSection:
    """Build a renderable descriptor for the provided topic section."""

    widget = section.widget

    # Normalisation for all widgets
    content = normalise_section_content(widget, section)

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
