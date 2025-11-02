"""Celery tasks for executing widgets via the registry pipeline."""
from __future__ import annotations

import logging
from typing import Any, Dict

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import WidgetAPIExecution
from .services import (
    WidgetExecutionError,
    WidgetExecutionService,
    WidgetRegistryLookupError,
    WidgetResponseValidationError,
)

logger = logging.getLogger(__name__)


def _resolve_error_code(exc: Exception) -> str:
    if getattr(exc, "code", None):
        return str(exc.code)
    if isinstance(exc, WidgetRegistryLookupError):
        return "registry_missing"
    if isinstance(exc, WidgetResponseValidationError):
        return "schema_validation_failed"
    if isinstance(exc, WidgetExecutionError):
        return "execution_error"
    return exc.__class__.__name__


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def execute_widget(self, *, execution_id: int) -> Dict[str, Any]:
    """Execute a widget using the configured registry and persist results."""

    execution = (
        WidgetAPIExecution.objects.select_related("widget", "section__topic", "topic")
        .get(pk=execution_id)
    )

    section = execution.section

    execution.status = WidgetAPIExecution.Status.RUNNING
    execution.started_at = timezone.now()
    execution.error_message = None
    execution.error_code = None
    execution.save(update_fields=["status", "started_at", "error_message", "error_code", "updated_at"])

    if section:
        section.status = "in_progress"
        section.error_message = None
        section.error_code = None
        section.save(update_fields=["status", "error_message", "error_code"])

    service = WidgetExecutionService()

    try:
        state = service.execute(execution)
    except Exception as exc:
        logger.exception("Widget execution %s failed", execution_id)
        error_code = _resolve_error_code(exc)
        error_message = str(exc)

        with transaction.atomic():
            if section:
                section.status = "error"
                section.error_message = error_message
                section.error_code = error_code
                section.save(update_fields=["status", "error_message", "error_code"])

            execution.status = WidgetAPIExecution.Status.FAILURE
            execution.error_message = error_message
            execution.error_code = error_code
            execution.completed_at = timezone.now()
            execution.save(
                update_fields=[
                    "prompt_template",
                    "prompt_context",
                    "prompt_text",
                    "extra_instructions",
                    "model_name",
                    "tools",
                    "metadata",
                    "raw_response",
                    "parsed_response",
                    "widget_type",
                    "status",
                    "error_message",
                    "error_code",
                    "completed_at",
                    "updated_at",
                ]
            )

        raise

    with transaction.atomic():
        if section:
            section.content = state.parsed_response
            section.status = "finished"
            section.error_message = None
            section.error_code = None
            section.save(update_fields=["content", "status", "error_message", "error_code"])

        execution.status = WidgetAPIExecution.Status.SUCCESS
        execution.error_message = None
        execution.error_code = None
        execution.completed_at = timezone.now()
        execution.save(
            update_fields=[
                "prompt_template",
                "prompt_context",
                "prompt_text",
                "extra_instructions",
                "model_name",
                "tools",
                "metadata",
                "raw_response",
                "parsed_response",
                "widget_type",
                "status",
                "error_message",
                "error_code",
                "completed_at",
                "updated_at",
            ]
        )

    return {
        "execution_id": execution.id,
        "section_id": section.id if section else None,
        "status": execution.status,
    }
