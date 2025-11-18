from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Mapping, TYPE_CHECKING

from celery import shared_task
from django.apps import apps
from django.utils import timezone

from semanticnews.topics.widgets.execution import (
    WidgetExecutionError,
    WidgetExecutionLogEntry,
    WidgetExecutionPipeline,
    WidgetExecutionRequest,
    normalise_tools,
    resolve_widget_action,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Only for type checkers; does not run at import time, so no circular import
    from semanticnews.topics.models import TopicSection as TopicSectionType
else:
    TopicSectionType = Any


def _get_topic_section_model():
    """
    Lazy access to the TopicSection model to avoid circular imports at module import time.
    """
    return apps.get_model("topics", "TopicSection")


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def execute_widget_action(self, *, execution_id: int) -> Dict[str, Any]:
    """
    Execute the widget action associated with a topic section.

    This is the low-level task that actually runs the widget pipeline.
    """
    TopicSection = _get_topic_section_model()

    try:
        section = TopicSection.objects.select_related("topic").get(pk=execution_id)
    except TopicSection.DoesNotExist as exc:
        logger.error("TopicSection %s not found", execution_id)
        raise WidgetExecutionError("Topic section not found") from exc

    state = dict(section.execution_state or {})
    action_identifier = str(state.get("action") or "").strip()
    if not action_identifier:
        message = "Topic section is missing an action identifier"
        _mark_failure(section, state, section.metadata, [], message, code="missing_action")
        raise WidgetExecutionError(message)

    widget = section.widget
    try:
        action = resolve_widget_action(widget, action_identifier)
    except WidgetExecutionError as exc:
        _mark_failure(section, state, section.metadata, [], str(exc), code="action_not_found")
        raise

    metadata = dict(section.metadata or {})
    previous_logs = list(metadata.get("execution_logs") or [])
    extra_instructions = str(state.get("extra_instructions") or "")
    model_name = state.get("model") or metadata.get("model")
    tools_override = state.get("tools")

    pipeline = WidgetExecutionPipeline()
    request = WidgetExecutionRequest(
        section=section,
        widget=widget,
        action=action,
        metadata=metadata,
        extra_instructions=extra_instructions,
        model=model_name,
        tools=tools_override or getattr(action, "tools", None),
    )

    _mark_running(section, state)

    try:
        result = pipeline.execute(request)
    except Exception as exc:
        logger.exception("Widget execution failed for section %s", section.pk)
        _mark_failure(
            section,
            state,
            metadata,
            previous_logs,
            str(exc),
            code=getattr(exc, "code", None),
            model_name=model_name or pipeline.default_model,
            tools=normalise_tools(tools_override or getattr(action, "tools", []) or []),
        )
        raise

    completed_at = timezone.now()
    state.update(
        {
            "status": "finished",
            "completed_at": completed_at.isoformat(),
            "updated_at": completed_at.isoformat(),
            "prompt": result.prompt,
            "model": result.model,
            "tools": result.tools,
            "context": result.context,
            "raw_response": result.raw_response,
            "parsed_response": result.parsed_response,
            "error_message": None,
            "error_code": None,
        }
    )

    metadata_payload = dict(result.metadata or {})
    logs = list(previous_logs)
    if result.log_entry is not None:
        logs.append(result.log_entry.to_dict())
    if logs:
        metadata_payload["execution_logs"] = logs

    section.content = dict(result.content or {})
    section.metadata = metadata_payload
    section.execution_state = state

    return {
        "section_id": section.id,
        "status": state["status"],
        "content": section.content,
        "metadata": section.metadata,
    }


def _mark_running(section: TopicSectionType, state: Dict[str, Any]) -> None:
    now = timezone.now()
    state.update(
        {
            "status": "running",
            "started_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "error_message": None,
            "error_code": None,
        }
    )
    section.execution_state = state


def _mark_failure(
    section: TopicSectionType,
    state: Dict[str, Any],
    base_metadata: Mapping[str, Any] | None,
    previous_logs: Iterable[Mapping[str, Any]],
    message: str,
    *,
    code: str | None = None,
    model_name: str | None = None,
    tools: Iterable[Mapping[str, Any]] | None = None,
) -> None:
    now = timezone.now()
    state.update(
        {
            "status": "failed",
            "error_message": message,
            "error_code": code,
            "failed_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    )

    log_entry = WidgetExecutionLogEntry(
        status="failure",
        created_at=now,
        prompt=str(state.get("prompt", "")),
        model=model_name or str(state.get("model") or ""),
        tools=list(tools or []),
        error_message=message,
    )

    metadata = dict(base_metadata or {})
    logs = list(previous_logs)
    logs.append(log_entry.to_dict())
    metadata["execution_logs"] = logs

    section.metadata = metadata
    section.execution_state = state
