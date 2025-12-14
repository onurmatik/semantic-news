"""API endpoints for topic widget discovery and executions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.timezone import make_naive
from django.template.loader import render_to_string
from ninja import Router, Schema
from ninja.errors import HttpError
from slugify import slugify

from semanticnews.topics.models import Topic, TopicSection
from semanticnews.topics.widgets import WIDGET_REGISTRY, get_widget, load_widgets
from semanticnews.topics.widgets.base import Widget, WidgetAction
from semanticnews.topics.widgets.rendering import build_renderable_section

from .execution import WidgetExecutionError, resolve_widget_action
from .services import (
    TopicWidgetExecution,
    TopicWidgetExecutionService,
)
from .tasks import execute_widget_action_task

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


class WidgetSectionDeleteResponse(Schema):
    success: bool


class WidgetSectionCreateRequest(Schema):
    topic_uuid: uuid.UUID
    widget_id: Optional[str] = None
    content: Optional[Any] = None


class WidgetSectionCreateResponse(Schema):
    id: int
    draft_display_order: int
    shell: Optional[str] = None


class WidgetSectionOrderItem(Schema):
    id: int
    display_order: int


class WidgetSectionReorderRequest(Schema):
    topic_uuid: uuid.UUID
    section_ids: List[int]


class WidgetSectionReorderResponse(Schema):
    sections: List[WidgetSectionOrderItem]


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


def _resolve_widget_identifier(
    identifier: str | None = None, *, payload: WidgetSectionCreateRequest | None = None
) -> Widget:
    widget_identifier = identifier or None
    if widget_identifier is None and payload is not None:
        widget_identifier = payload.widget_id

    if widget_identifier is None:
        raise HttpError(400, "Widget identifier is required")

    return _resolve_widget(str(widget_identifier))


def _create_widget_section(
    request, payload: WidgetSectionCreateRequest, *, identifier: str | None = None
) -> WidgetSectionCreateResponse:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    widget = _resolve_widget_identifier(identifier, payload=payload)

    max_order = (
        TopicSection.objects.filter(topic=topic, is_deleted=False, is_draft_deleted=False)
        .aggregate(max_order=Max("draft_display_order"))
        .get("max_order")
        or 0
    )

    section = TopicSection.objects.create(
        topic=topic,
        widget_name=widget.name,
        draft_display_order=max_order + 1,
        display_order=max_order + 1,
    )
    section._get_or_create_draft_record()

    content = payload.content if payload.content is not None else {}
    section.content = content

    renderable = build_renderable_section(section, edit_mode=True)
    renderable.key = f"section:{section.id}"
    shell = render_to_string(
        "widgets/topics/widgets/section.html",
        {"renderable": renderable, "edit_mode": True},
    )

    return WidgetSectionCreateResponse(
        id=section.id, draft_display_order=section.draft_display_order, shell=shell
    )


@router.post("/sections", response=WidgetSectionCreateResponse)
def create_widget_section(request, payload: WidgetSectionCreateRequest):
    return _create_widget_section(request, payload)


@router.post("/{identifier}/sections", response=WidgetSectionCreateResponse)
def create_widget_section_for_identifier(
    request, identifier: str, payload: WidgetSectionCreateRequest
):
    return _create_widget_section(request, payload, identifier=identifier)


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

    if section is None:
        max_order = (
            TopicSection.objects.filter(
                topic=topic, is_deleted=False, is_draft_deleted=False
            )
            .aggregate(max_order=Max("draft_display_order"))
            .get("max_order")
            or 0
        )
        section = TopicSection.objects.create(
            topic=topic,
            widget_name=widget.name,
            draft_display_order=max_order + 1,
            display_order=max_order + 1,
        )

    execute_widget_action_task.delay(
        topic_uuid=str(payload.topic_uuid),
        widget_name=payload.widget_name,
        action=payload.action,
        section_id=section.id,
        extra_instructions=payload.extra_instructions,
        metadata=payload.metadata,
    )
    execution = _execution_service.get_state(section=section)
    return _serialize_execution(execution, topic_uuid=str(topic.uuid))


@router.post("/sections/reorder", response=WidgetSectionReorderResponse)
def reorder_widget_sections(request, payload: WidgetSectionReorderRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    if not payload.section_ids:
        raise HttpError(400, "Section identifiers are required")

    if len(payload.section_ids) != len(set(payload.section_ids)):
        raise HttpError(400, "Section identifiers must be unique")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    sections = list(
        TopicSection.objects.filter(
            topic=topic,
            is_deleted=False,
            is_draft_deleted=False,
            id__in=payload.section_ids,
        )
    )

    section_map = {section.id: section for section in sections}
    if len(section_map) != len(payload.section_ids):
        raise HttpError(400, "One or more sections are invalid for this topic")

    with transaction.atomic():
        updates: list[TopicSection] = []
        for order, section_id in enumerate(payload.section_ids, start=1):
            section = section_map[section_id]
            original_order = section.draft_display_order
            section.draft_display_order = order
            if original_order != order:
                updates.append(section)

        if updates:
            TopicSection.objects.bulk_update(updates, ["draft_display_order"])

    ordered_sections = sorted(
        sections, key=lambda item: (item.draft_display_order, item.id)
    )
    return WidgetSectionReorderResponse(
        sections=[
            WidgetSectionOrderItem(
                id=section.id, display_order=section.draft_display_order
            )
            for section in ordered_sections
        ]
    )


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


@router.delete("/sections/{section_id}", response=WidgetSectionDeleteResponse)
def delete_widget_section(request, section_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        section = TopicSection.objects.select_related("topic").get(id=section_id)
    except TopicSection.DoesNotExist:
        raise HttpError(404, "Topic section not found")

    topic = section.topic
    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    if not section.is_draft_deleted:
        section.is_draft_deleted = True
        section.save(update_fields=["is_draft_deleted"])

    return WidgetSectionDeleteResponse(success=True)


__all__ = ["router"]
