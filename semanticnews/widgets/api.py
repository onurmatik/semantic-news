"""API endpoints for managing topic widgets and executions."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.timezone import make_naive
from ninja import NinjaAPI, Router, Schema
from ninja.errors import HttpError

from slugify import slugify
from semanticnews.topics.models import Topic, TopicSection
from semanticnews.widgets.models import Widget, WidgetAction, WidgetActionExecution
from semanticnews.widgets.tasks import (
    execute_widget_action as execute_widget_action_task,
)

logger = logging.getLogger(__name__)

router = Router()
widgets_api = NinjaAPI(title="Widgets API", urls_namespace="widgets")
widgets_api.add_router("", router)


class WidgetDefinition(Schema):
    id: int
    name: str
    key: str


class WidgetActionDefinition(Schema):
    id: int
    name: str
    icon: Optional[str] = None


class WidgetDefinitionListResponse(Schema):
    total: int
    items: List[WidgetDefinition]


class WidgetDetailResponse(Schema):
    id: int
    name: str
    key: str
    description: Optional[str]
    template: str
    response_format: Dict[str, Any]
    input_format: List[Dict[str, Any]]
    actions: List[WidgetActionDefinition]


class WidgetActionExecutionCreateRequest(Schema):
    topic_uuid: str
    widget_id: int
    action_id: int
    section_id: Optional[int] = None
    widget_type: Optional[str] = None
    extra_instructions: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = None
    tools: Optional[List[Any]] = None


class WidgetActionExecutionStatusResponse(Schema):
    id: int
    widget_id: int
    widget_type: Optional[str] = None
    action_id: int
    topic_id: Optional[int] = None
    topic_uuid: Optional[str] = None
    section_id: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


def _serialize_widget(widget: Widget) -> WidgetDefinition:
    return WidgetDefinition(
        id=widget.id,
        name=widget.name,
        key=_derive_widget_key(widget),
    )


def _derive_widget_key(widget: Widget) -> str:
    name = widget.name or ""
    slug = slugify(name)
    if slug:
        return slug
    return f"widget-{widget.pk or uuid.uuid4().hex[:8]}"


def _serialize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if timezone.is_aware(value):
        return make_naive(value)
    return value


def _serialize_execution(execution: WidgetActionExecution) -> WidgetActionExecutionStatusResponse:
    section = execution.section
    topic = section.topic if section else execution.topic
    widget = execution.widget

    return WidgetActionExecutionStatusResponse(
        id=execution.id,
        widget_id=widget.id,
        widget_type=execution.widget_type or widget.name,
        action_id=execution.action_id,
        topic_id=topic.id if topic else None,
        topic_uuid=str(topic.uuid) if topic else None,
        section_id=section.id if section else None,
        status=execution.status,
        error_message=execution.error_message,
        error_code=execution.error_code,
        model_name=execution.model_name or None,
        created_at=_serialize_datetime(execution.created_at) or timezone.now(),
        updated_at=_serialize_datetime(execution.updated_at) or timezone.now(),
        started_at=_serialize_datetime(execution.started_at),
        completed_at=_serialize_datetime(execution.completed_at),
    )


@router.get("/definitions", response=WidgetDefinitionListResponse)
def list_widgets(request):
    widgets = Widget.objects.all().order_by("name")
    items = [_serialize_widget(widget) for widget in widgets]
    return WidgetDefinitionListResponse(total=len(items), items=items)


@router.get("/{identifier}/details", response=WidgetDetailResponse)
def widget_details(request, identifier: str):
    try:
        widget = _resolve_widget(identifier)
    except Widget.DoesNotExist:
        raise HttpError(404, "Widget not found")

    actions = [
        WidgetActionDefinition(id=action.id, name=action.name, icon=action.icon or None)
        for action in widget.actions.all()
    ]

    return WidgetDetailResponse(
        id=widget.id,
        name=widget.name,
        key=_derive_widget_key(widget),
        description=widget.description or None,
        template=(widget.template or "").strip(),
        response_format=widget.context_structure or {},
        input_format=list(widget.input_format or []),
        actions=actions,
    )


def _resolve_widget(identifier: str) -> Widget:
    queryset = Widget.objects.all()

    try:
        widget_id = int(identifier)
    except (TypeError, ValueError):
        widget_id = None

    if widget_id is not None:
        try:
            return queryset.get(id=widget_id)
        except Widget.DoesNotExist:
            pass

    normalized = slugify(str(identifier or ""))
    if not normalized:
        raise Widget.DoesNotExist()

    for widget in queryset:
        if slugify(widget.name or "") == normalized:
            return widget

    raise Widget.DoesNotExist()


@router.post("/execute", response=WidgetActionExecutionStatusResponse)
def execute_widget_action(request, payload: WidgetActionExecutionCreateRequest):
    """Execute the action via the LLM and populate the topic section"""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic_uuid = uuid.UUID(str(payload.topic_uuid))
    except (ValueError, TypeError):
        raise HttpError(400, "Invalid topic UUID")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except (Topic.DoesNotExist, ValidationError):
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    try:
        widget = Widget.objects.get(id=payload.widget_id)
    except Widget.DoesNotExist:
        raise HttpError(404, "Widget not found")

    try:
        action = WidgetAction.objects.get(id=payload.action_id, widget=widget)
    except WidgetAction.DoesNotExist:
        raise HttpError(404, "Widget action not found")

    section: Optional[TopicSection] = None
    if payload.section_id is not None:
        try:
            section = TopicSection.objects.get(
                id=payload.section_id,
                topic=topic,
                widget_name=widget.name,
            )
        except TopicSection.DoesNotExist:
            raise HttpError(404, "Topic section not found")

    if section is None:
        section = TopicSection.objects.create(topic=topic, widget_name=widget.name)

    metadata = dict(payload.metadata or {})
    extra_instructions = (payload.extra_instructions or "").strip()

    execution = WidgetActionExecution.objects.create(
        action=action,
        section=section,
        widget_type=payload.widget_type or widget.name,
        extra_instructions=extra_instructions,
        metadata=metadata,
        response_schema=payload.response_schema,
        model_name=payload.model_name or "",
        tools=payload.tools or [],
    )

    execution.topic = topic

    try:
        execute_widget_action_task.delay(execution_id=execution.id)
    except Exception:
        logger.exception("Failed to enqueue widget execution %s", execution.id)
        raise

    return _serialize_execution(execution)


@router.get("/executions/{execution_id}", response=WidgetActionExecutionStatusResponse)
def get_execution_status(request, execution_id: int, topic_uuid: str):
    """Get and update the execution status"""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic_uuid_obj = uuid.UUID(str(topic_uuid))
    except (ValueError, TypeError):
        raise HttpError(400, "Invalid topic UUID")

    try:
        topic = Topic.objects.get(uuid=topic_uuid_obj)
    except (Topic.DoesNotExist, ValidationError):
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    try:
        execution = (
            WidgetActionExecution.objects.select_related("section__topic", "action__widget")
            .get(id=execution_id)
        )
    except WidgetActionExecution.DoesNotExist:
        raise HttpError(404, "Execution not found")

    section = execution.section
    if not section or section.topic_id != topic.id:
        raise HttpError(404, "Execution not found")

    return _serialize_execution(execution)
