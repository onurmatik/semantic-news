"""API endpoints for managing topic widget sections and executions."""
from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional, Literal

from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError
from pydantic import Field, ValidationError, create_model, validator

from semanticnews.topics.models import Topic, TopicSection
from semanticnews.widgets.helpers import build_topic_context_snippet, fetch_external_assets
from semanticnews.widgets.models import Widget, WidgetAPIExecution
from semanticnews.widgets.services import (
    WidgetResponseValidationError,
    _validate_against_schema,
)
from semanticnews.widgets.rendering import (
    build_renderable_section,
    normalize_widget_content,
    resolve_widget_template,
)
from semanticnews.widgets.tasks import execute_widget

logger = logging.getLogger(__name__)

router = Router()


class WidgetDefinition(Schema):
    id: int
    name: str
    prompt_template: str | None = None
    response_format: Dict[str, Any] = Field(default_factory=dict)
    tools: List[Any] = Field(default_factory=list)
    template: str | None = None


class WidgetDefinitionListResponse(Schema):
    total: int
    items: List[WidgetDefinition]


class WidgetSectionContent(Schema):
    content: Any = None


class WidgetSectionCreateRequest(WidgetSectionContent):
    topic_uuid: str
    widget_id: int
    language_code: Optional[str] = None
    display_order: Optional[int] = None


class WidgetSectionUpdateRequest(WidgetSectionContent):
    topic_uuid: str
    language_code: Optional[str] = None
    display_order: Optional[int] = None
    status: Optional[Literal["in_progress", "finished", "error"]] = None


class WidgetSectionResponse(WidgetSectionContent):
    id: int
    topic_id: int
    topic_uuid: str
    widget_id: int
    display_order: int
    language_code: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    published_at: Optional[str] = None


class WidgetSectionOperationResponse(Schema):
    success: bool


class WidgetExecutionCreateRequest(Schema):
    topic_uuid: str
    widget_id: int
    section_id: Optional[int] = None
    widget_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    model_name: Optional[str] = None
    extra_instructions: Optional[str] = None
    language_code: Optional[str] = None
    mode: Literal["ai", "manual"] = "ai"
    content: Any = None


class WidgetExecutionStatusResponse(Schema):
    id: int
    topic_id: int
    section_id: Optional[int] = None
    widget_id: int
    status: str
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


def _get_owned_topic(request, topic_uuid: str) -> Topic:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")
    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist as exc:
        raise HttpError(404, "Topic not found") from exc
    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")
    return topic


def _get_widget(widget_id: int) -> Widget:
    try:
        return Widget.objects.get(pk=widget_id)
    except Widget.DoesNotExist as exc:
        raise HttpError(404, "Widget not found") from exc


def _get_section_for_topic(topic: Topic, section_id: int) -> TopicSection:
    try:
        section = topic.sections.get(pk=section_id, is_deleted=False)
    except TopicSection.DoesNotExist as exc:
        raise HttpError(404, "Section not found") from exc
    return section


def _build_content_model(widget: Widget, base: type[WidgetSectionContent]) -> type[WidgetSectionContent]:
    schema = widget.response_format or {}

    def _validate_content(cls, value):
        if value is None:
            return None
        try:
            _validate_against_schema(value, schema)
        except WidgetResponseValidationError as exc:
            raise ValueError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ValueError(str(exc)) from exc
        return value

    model_name = f"{base.__name__}ForWidget{widget.pk or 'unsaved'}"
    return create_model(
        model_name,
        __base__=base,
        __validators__={
            "validate_content": validator("content", allow_reuse=True)(_validate_content),
        },
    )


def _validate_section_content(
    widget: Widget, content: Any, *, raise_http_error: bool = True
) -> Any:
    model = _build_content_model(widget, WidgetSectionContent)
    try:
        payload = model(content=content)
    except ValidationError as exc:
        message = exc.errors()[0]["msg"] if exc.errors() else "Invalid content payload"
        if not raise_http_error:
            logger.warning(
                "Stored widget content for widget %s failed validation: %s",
                widget.id,
                message,
            )
            return content
        raise HttpError(400, message) from exc
    return payload.content


def _determine_status_from_content(content: Any) -> str:
    if content is None:
        return "in_progress"
    if isinstance(content, str):
        return "finished" if content.strip() else "in_progress"
    if isinstance(content, (list, dict)):
        return "finished" if bool(content) else "in_progress"
    return "finished"


def _create_topic_section(
    *,
    topic: Topic,
    widget: Widget,
    language_code: Optional[str] = None,
    display_order: Optional[int] = None,
    content: Any = None,
    status: Optional[str] = None,
) -> TopicSection:
    with transaction.atomic():
        if display_order is None:
            max_order = (
                topic.sections.filter(is_deleted=False)
                .aggregate(Max("display_order"))
                .get("display_order__max")
            )
            display_order = (max_order or 0) + 1
        section = TopicSection(
            topic=topic,
            widget=widget,
            display_order=display_order,
            language_code=language_code or None,
            content=content,
        )
        if status:
            section.status = status
        section.full_clean()
        section.save()
    return section


def _serialize_widget(widget: Widget) -> WidgetDefinition:
    return WidgetDefinition(
        id=widget.id,
        name=widget.name,
        prompt_template=widget.prompt_template or None,
        response_format=widget.response_format or {},
        tools=list(widget.tools or []),
        template=widget.template or None,
    )


def _serialize_section(section: TopicSection) -> WidgetSectionResponse:
    widget = section.widget
    content = _validate_section_content(widget, section.content, raise_http_error=False)
    normalized_content = normalize_widget_content(widget, content)
    published_at = section.published_at
    return WidgetSectionResponse(
        id=section.id,
        topic_id=section.topic_id,
        topic_uuid=str(section.topic.uuid),
        widget_id=section.widget_id,
        display_order=section.display_order,
        language_code=section.language_code,
        status=section.status,
        error_message=section.error_message,
        error_code=section.error_code,
        content=normalized_content,
        published_at=make_naive(published_at).isoformat() if published_at else None,
    )


def _serialize_execution(execution: WidgetAPIExecution) -> WidgetExecutionStatusResponse:
    def _normalize(dt):
        return make_naive(dt).isoformat() if dt else None

    return WidgetExecutionStatusResponse(
        id=execution.id,
        topic_id=execution.topic_id,
        section_id=execution.section_id,
        widget_id=execution.widget_id,
        status=execution.status,
        error_message=execution.error_message,
        error_code=execution.error_code,
        created_at=_normalize(execution.created_at),
        started_at=_normalize(execution.started_at),
        completed_at=_normalize(execution.completed_at),
    )


def _build_renderable_section_descriptor(section: TopicSection) -> SimpleNamespace:
    descriptor = build_renderable_section(section, edit_mode=False)
    descriptor.key = f"section:{section.id}"
    return descriptor


def _build_manual_prompt_context(topic, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    context = {
        "topic": {
            "id": topic.id,
            "uuid": str(topic.uuid),
            "title": topic.title,
        }
    }
    snippet = build_topic_context_snippet(topic, metadata=metadata)
    if snippet:
        context["topic"]["context_snippet"] = snippet
    if metadata.get("resolved_assets"):
        context["assets"] = metadata["resolved_assets"]
    return context


def _perform_manual_execution(
    request,
    payload: WidgetExecutionCreateRequest,
    *,
    topic: Topic,
    widget: Widget,
    metadata: Dict[str, Any],
) -> WidgetAPIExecution:
    if payload.content is None:
        raise HttpError(400, "Content is required for manual submissions")

    validated_content = _validate_section_content(widget, payload.content)
    status = _determine_status_from_content(validated_content)

    metadata.setdefault("mode", "manual")
    fetch_external_assets(widget, metadata)

    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None

    if payload.section_id is not None:
        section = _get_section_for_topic(topic, payload.section_id)
        if section.widget_id != widget.id:
            raise HttpError(400, "Section widget mismatch")
        updates = ["content", "status", "error_message", "error_code"]
        section.content = validated_content
        section.status = status
        section.error_message = None
        section.error_code = None
        if payload.language_code:
            section.language_code = payload.language_code
            updates.append("language_code")
        section.save(update_fields=list(dict.fromkeys(updates)))
    else:
        section = _create_topic_section(
            topic=topic,
            widget=widget,
            language_code=payload.language_code,
            content=validated_content,
            status=status,
        )

    now = timezone.now()

    execution = WidgetAPIExecution.objects.create(
        topic=topic,
        section=section,
        widget=widget,
        user=user,
        widget_type=payload.widget_type or widget.name,
        metadata=metadata,
        model_name=payload.model_name or "",
        extra_instructions=payload.extra_instructions or "",
        status=WidgetAPIExecution.Status.MANUAL,
        prompt_template=widget.prompt_template or "",
        prompt_context=_build_manual_prompt_context(topic, metadata),
        prompt_text="",
        parsed_response=validated_content,
        raw_response=None,
        started_at=now,
        completed_at=now,
    )

    return execution


@router.get("/definitions", response=WidgetDefinitionListResponse)
def list_widgets(request):
    widgets = Widget.objects.all().order_by("name")
    items = [_serialize_widget(widget) for widget in widgets]
    return WidgetDefinitionListResponse(total=len(items), items=items)


@router.post("/sections", response=WidgetSectionResponse)
def create_section(request, payload: WidgetSectionCreateRequest):
    topic = _get_owned_topic(request, payload.topic_uuid)
    widget = _get_widget(payload.widget_id)
    validated_content = _validate_section_content(widget, payload.content)
    status = _determine_status_from_content(validated_content)
    section = _create_topic_section(
        topic=topic,
        widget=widget,
        language_code=payload.language_code,
        display_order=payload.display_order,
        content=validated_content,
        status=status,
    )
    return _serialize_section(section)


@router.put("/sections/{section_id}", response=WidgetSectionResponse)
def update_section(request, section_id: int, payload: WidgetSectionUpdateRequest):
    topic = _get_owned_topic(request, payload.topic_uuid)
    section = _get_section_for_topic(topic, section_id)
    widget = section.widget

    data = payload.dict(exclude_unset=True)
    updates: List[str] = []
    clear_errors = False

    if "content" in data:
        validated_content = _validate_section_content(widget, data.get("content"))
        section.content = validated_content
        section.status = _determine_status_from_content(validated_content)
        updates.append("content")
        updates.append("status")
        clear_errors = True

    if "language_code" in data:
        section.language_code = data.get("language_code") or None
        updates.append("language_code")

    if "display_order" in data and data["display_order"] is not None:
        section.display_order = data["display_order"]
        updates.append("display_order")

    if "status" in data and data["status"]:
        section.status = data["status"]
        if "status" not in updates:
            updates.append("status")
        clear_errors = True

    if clear_errors:
        section.error_message = None
        section.error_code = None
        updates.extend(["error_message", "error_code"])

    if updates:
        section.full_clean()
        section.save(update_fields=list(dict.fromkeys(updates)))

    section.refresh_from_db()
    return _serialize_section(section)


@router.delete("/sections/{section_id}", response=WidgetSectionOperationResponse)
def delete_section(request, section_id: int, topic_uuid: str):
    topic = _get_owned_topic(request, topic_uuid)
    section = _get_section_for_topic(topic, section_id)
    section.is_deleted = True
    section.save(update_fields=["is_deleted"])
    return WidgetSectionOperationResponse(success=True)


@router.post("/executions", response=WidgetExecutionStatusResponse)
def trigger_execution(request, payload: WidgetExecutionCreateRequest):
    topic = _get_owned_topic(request, payload.topic_uuid)
    widget = _get_widget(payload.widget_id)

    if payload.metadata is None:
        payload.metadata = {}

    metadata = dict(payload.metadata)

    if payload.mode == "manual":
        execution = _perform_manual_execution(
            request,
            payload,
            topic=topic,
            widget=widget,
            metadata=metadata,
        )
        return _serialize_execution(execution)

    section = None
    created_section = False
    previous_state: tuple[str, Optional[str], Optional[str]] | None = None
    if payload.section_id is not None:
        section = _get_section_for_topic(topic, payload.section_id)
        if section.widget_id != widget.id:
            raise HttpError(400, "Section widget mismatch")
        previous_state = (section.status, section.error_message, section.error_code)
        section.status = "in_progress"
        section.error_message = None
        section.error_code = None
        section.save(update_fields=["status", "error_message", "error_code"])
    else:
        section = _create_topic_section(
            topic=topic,
            widget=widget,
            language_code=payload.language_code,
            content=None,
            status="in_progress",
        )
        created_section = True

    execution = WidgetAPIExecution.objects.create(
        topic=topic,
        section=section,
        widget=widget,
        user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        widget_type=payload.widget_type or widget.name,
        metadata=metadata,
        model_name=payload.model_name or "",
        extra_instructions=payload.extra_instructions or "",
    )

    try:
        execute_widget.delay(execution_id=execution.id)
    except Exception:  # pragma: no cover - background task submission failures
        logger.exception("Failed to enqueue widget execution %s", execution.id)
        execution.delete()
        if created_section:
            section.delete()
        elif previous_state is not None:
            section.status, section.error_message, section.error_code = previous_state
            section.save(update_fields=["status", "error_message", "error_code"])
        raise HttpError(502, "Unable to start widget execution")

    return _serialize_execution(execution)


@router.get("/executions/{execution_id}", response=WidgetExecutionStatusResponse)
def get_execution_status(request, execution_id: int, topic_uuid: str):
    topic = _get_owned_topic(request, topic_uuid)
    try:
        execution = topic.widget_api_executions.get(pk=execution_id)
    except WidgetAPIExecution.DoesNotExist as exc:
        raise HttpError(404, "Execution not found") from exc
    return _serialize_execution(execution)


@router.get("/sections/{section_id}/download")
def download_section(request, section_id: int, topic_uuid: str):
    topic = _get_owned_topic(request, topic_uuid)
    section = _get_section_for_topic(topic, section_id)
    descriptor = _build_renderable_section_descriptor(section)
    html = render_to_string(
        "widgets/topics/widgets/section.html",
        {"renderable": descriptor, "edit_mode": False},
    )
    filename_base = slugify(section.widget.name or "widget-section") or "widget-section"
    filename = f"{filename_base}-{section.id}.html"
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f"attachment; filename={filename}"
    return response
