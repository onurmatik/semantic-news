"""Service layer utilities for topic widget executions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from semanticnews.topics.models import Topic, TopicSection

from .base import Widget, WidgetAction


@dataclass
class TopicWidgetExecution:
    """Lightweight descriptor representing a widget execution request."""

    section: TopicSection
    widget_name: str
    action: str
    status: str
    queued_at: datetime
    metadata: dict[str, Any]
    extra_instructions: str
    state: dict[str, Any]


class TopicWidgetExecutionService:
    """Persist and expose widget execution state for topic sections."""

    default_status = "queued"

    def queue_execution(
        self,
        *,
        topic: Topic,
        widget: Widget,
        action: WidgetAction,
        section: TopicSection | None = None,
        metadata: Mapping[str, Any] | None = None,
        extra_instructions: str | None = None,
    ) -> TopicWidgetExecution:
        """Create or update a section and mark the execution as queued."""

        action_name = getattr(action, "name", "") or action.__class__.__name__
        normalized_metadata = dict(metadata or {})
        normalized_instructions = (extra_instructions or "").strip()
        queued_at = timezone.now()

        with transaction.atomic():
            if section is None:
                section = TopicSection.objects.create(
                    topic=topic,
                    widget_name=widget.name,
                )
            else:
                section.widget_name = widget.name

            state = dict(section.execution_state or {})
            state.update(
                {
                    "status": self.default_status,
                    "action": action_name,
                    "widget": widget.name,
                    "queued_at": queued_at.isoformat(),
                    "extra_instructions": normalized_instructions,
                    "updated_at": queued_at.isoformat(),
                }
            )

            section.execution_state = state
            section.metadata = normalized_metadata
            section.save(update_fields=["widget_name"])

        return TopicWidgetExecution(
            section=section,
            widget_name=widget.name,
            action=action_name,
            status=state.get("status", self.default_status),
            queued_at=queued_at,
            metadata=dict(section.metadata or {}),
            extra_instructions=normalized_instructions,
            state=state,
        )

    def get_state(self, *, section: TopicSection) -> TopicWidgetExecution:
        """Derive the execution descriptor for the provided section."""

        state = dict(section.execution_state or {})
        action_name = str(state.get("action") or "")
        status = str(state.get("status") or self.default_status)
        queued_at = self._parse_timestamp(state.get("queued_at")) or timezone.now()
        extra_instructions = str(state.get("extra_instructions") or "")

        return TopicWidgetExecution(
            section=section,
            widget_name=section.widget_name,
            action=action_name,
            status=status,
            queued_at=queued_at,
            metadata=dict(section.metadata or {}),
            extra_instructions=extra_instructions,
            state=state,
        )

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None


__all__ = [
    "TopicWidgetExecution",
    "TopicWidgetExecutionService",
]
