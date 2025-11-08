"""API endpoints for topic widget discovery and executions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.utils import timezone
from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError
from slugify import slugify

from semanticnews.topics.models import Topic, TopicSection
from semanticnews.topics.widgets import WIDGET_REGISTRY, get_widget, load_widgets
from semanticnews.topics.widgets.base import Widget, WidgetAction

from .execution import WidgetExecutionError, resolve_widget_action
from .services import TopicWidgetExecutionService, TopicWidgetExecution

router = Router(tags=["widgets"])
_execution_service = TopicWidgetExecutionService()


class WidgetActionDefinition(Schema):
    id: str
    name: str
    icon: Optional[str] = None
    tools: Optional[List[str]] = None


class WidgetDefinition(Schema):
    id: str
    name: str
    key: str
    icon: Optional[str] = None


class WidgetDefinitionListResponse(Schema):
    total: int
    items: List[WidgetDefinition]


class WidgetDetailResponse(Schema):
    id: str
    name: str
    key: str
    icon: Optional[str] = None
    form_template: Optional[str] = None
    template: Optional[str] = None
    context_structure: Dict[str, Any]
    schema: Optional[Dict[str, Any]] = None
    actions: List[WidgetActionDefinition]


class WidgetExecutionRequest(Schema):
    topic_uuid: uuid.UUID
    widget_name: str
    action: str
    section_id: Optional[int] = None
    extra_instructions: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WidgetExecutionResponse(Schema):
    section_id: int
    topic_uuid: str
    widget_name: str
    action: str
    status: str
    queued_at: datetime
    extra_instructions: Optional[str] = None
    metadata: Dict[str, Any]
    content: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None


def _serialize_widget(widget: Widget) -> WidgetDefinition:
    identifier = widget.name
    return WidgetDefinition(
        id=identifier,
        name=widget.name,
        key=slugify(widget.name) if widget.name else identifier,
        icon=getattr(widget, "icon", None) or None,
    )


def _serialize_action(widget: Widget, action: WidgetAction) -> WidgetActionDefinition:
    identifier = getattr(action, "name", "") or action.__class__.__name__
    tools = getattr(action, "tools", None)
    return WidgetActionDefinition(
        id=str(identifier),
        name=str(getattr(action, "name", identifier) or identifier),
        icon=getattr(action, "icon", None) or None,
        tools=list(tools) if tools else None,
    )


def _schema_to_dict(schema: Any) -> Dict[str, Any] | None:
    if schema is None:
        return None
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()  # type: ignore[call-arg]
    if hasattr(schema, "schema"):
        return schema.schema()  # type: ignore[call-arg]
    if isinstance(schema, dict):
        return schema
    return None


def _serialize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if timezone.is_aware(value):
        return make_naive(value)
    return value


def _serialize_execution(execution: TopicWidgetExecution, *, topic_uuid: str) -> WidgetExecutionResponse:
    section = execution.section
    state = execution.state or {}

    queued_at = _serialize_datetime(execution.queued_at) or timezone.now()

    return WidgetExecutionResponse(
        section_id=section.id,
        topic_uuid=topic_uuid,
        widget_name=execution.widget_name,
        action=execution.action,
        status=execution.status,
        queued_at=queued_at,
        extra_instructions=execution.extra_instructions or None,
        metadata=dict(execution.metadata or {}),
        content=section.content or None,
        error_message=state.get("error_message"),
        error_code=state.get("error_code"),
    )


def _resolve_widget(identifier: str) -> Widget:
    load_widgets()
    normalized = str(identifier or "").strip()
    if not normalized:
        raise HttpError(404, "Widget not found")

    try:
        return get_widget(normalized)
    except KeyError:
        pass

    slug = slugify(normalized)
    for widget in WIDGET_REGISTRY.values():
        if widget.name == normalized:
            return widget
        if slug and slugify(widget.name or "") == slug:
            return widget

    raise HttpError(404, "Widget not found")
@router.get("/definitions", response=WidgetDefinitionListResponse)
def list_widgets(request) -> WidgetDefinitionListResponse:
    widgets = list(load_widgets().values())
    widgets.sort(key=lambda item: item.name)
    items = [_serialize_widget(widget) for widget in widgets]
    return WidgetDefinitionListResponse(total=len(items), items=items)


@router.get("/{identifier}/details", response=WidgetDetailResponse)
def widget_details(request, identifier: str) -> WidgetDetailResponse:
    widget = _resolve_widget(identifier)
    schema = _schema_to_dict(getattr(widget, "schema", None))
    actions = [_serialize_action(widget, action) for action in widget.get_actions()]

    return WidgetDetailResponse(
        id=widget.name,
        name=widget.name,
        key=slugify(widget.name) if widget.name else widget.name,
        icon=getattr(widget, "icon", None) or None,
        form_template=getattr(widget, "form_template", None) or None,
        template=getattr(widget, "template", None) or None,
        context_structure=dict(getattr(widget, "context_structure", {}) or {}),
        schema=schema,
        actions=actions,
    )


@router.post("/execute", response=WidgetExecutionResponse)
def execute_widget_action(request, payload: WidgetExecutionRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    widget = _resolve_widget(payload.widget_name)
    try:
        action = resolve_widget_action(widget, payload.action)
    except WidgetExecutionError as exc:
        raise HttpError(404, str(exc)) from exc

    section: TopicSection | None = None
    if payload.section_id is not None:
        try:
            section = TopicSection.objects.get(id=payload.section_id, topic=topic)
        except TopicSection.DoesNotExist:
            raise HttpError(404, "Topic section not found")
        if section.widget_name and section.widget_name != widget.name:
            raise HttpError(400, "Topic section is linked to a different widget")

    execution = _execution_service.queue_execution(
        topic=topic,
        widget=widget,
        action=action,
        section=section,
        metadata=payload.metadata or {},
        extra_instructions=payload.extra_instructions,
    )

    return _serialize_execution(execution, topic_uuid=str(topic.uuid))


@router.get("/sections/{section_id}", response=WidgetExecutionResponse)
def get_execution_status(request, section_id: int, topic_uuid: uuid.UUID):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    try:
        section = TopicSection.objects.get(id=section_id, topic=topic)
    except TopicSection.DoesNotExist:
        raise HttpError(404, "Topic section not found")

    execution = _execution_service.get_state(section=section)
    return _serialize_execution(execution, topic_uuid=str(topic.uuid))


__all__ = ["router"]
