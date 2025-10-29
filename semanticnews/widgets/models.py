from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Dict, Iterable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class WidgetType(models.TextChoices):
    """All supported widget shells within a topic."""

    TITLE = "title", _("Title")
    RECAP = "recap", _("Recap")
    COVER_IMAGE = "cover_image", _("Cover image")
    TEXT = "text", _("Text block")
    DATA = "data", _("Data block")
    TIMELINE = "timeline", _("Timeline")
    EVENTS = "events", _("Linked events")
    RELATED_TOPICS = "related_topics", _("Related topics")
    EXTERNAL_LINKS = "external_links", _("External links")
    DOCUMENTS = "documents", _("Documents")
    ENTITIES = "entities", _("Entities")


@dataclass(frozen=True)
class WidgetDefinition:
    """Static metadata that drives widget behaviour."""

    type: WidgetType
    multiple_per_topic: bool = False
    translatable: bool = True


class WidgetRegistry:
    """Registry of widget capabilities for quick lookups."""

    _definitions: ClassVar[Dict[str, WidgetDefinition]] = {}

    @classmethod
    def register(cls, definition: WidgetDefinition) -> None:
        cls._definitions[definition.type] = definition

    @classmethod
    def get(cls, widget_type: WidgetType) -> WidgetDefinition:
        try:
            return cls._definitions[widget_type]
        except KeyError as exc:  # pragma: no cover - guarded by tests
            raise LookupError(f"Unknown widget type: {widget_type}") from exc

    @classmethod
    def all(cls) -> Iterable[WidgetDefinition]:
        return cls._definitions.values()


for definition in (
    WidgetDefinition(WidgetType.TITLE, multiple_per_topic=False),
    WidgetDefinition(WidgetType.RECAP, multiple_per_topic=False),
    WidgetDefinition(WidgetType.COVER_IMAGE, multiple_per_topic=False),
    WidgetDefinition(WidgetType.TEXT, multiple_per_topic=True),
    WidgetDefinition(WidgetType.DATA, multiple_per_topic=True),
    WidgetDefinition(WidgetType.TIMELINE, multiple_per_topic=False),
    WidgetDefinition(WidgetType.EVENTS, multiple_per_topic=False),
    WidgetDefinition(WidgetType.RELATED_TOPICS, multiple_per_topic=False),
    WidgetDefinition(WidgetType.EXTERNAL_LINKS, multiple_per_topic=False),
    WidgetDefinition(WidgetType.DOCUMENTS, multiple_per_topic=False),
    WidgetDefinition(WidgetType.ENTITIES, multiple_per_topic=False),
):
    WidgetRegistry.register(definition)


class TopicWidgetQuerySet(models.QuerySet):
    def for_language(self, language_code: str) -> "TopicWidgetQuerySet":
        return self.filter(language_code=language_code)

    def primary(self) -> "TopicWidgetQuerySet":
        return self.filter(is_primary_language=True)


class TopicWidget(models.Model):
    """Base widget instance stored inline on the topic editing page."""

    topic = models.ForeignKey(
        "topics.Topic",
        on_delete=models.CASCADE,
        related_name="widgets",
    )
    widget_type = models.CharField(
        max_length=50,
        choices=WidgetType.choices,
    )
    language_code = models.CharField(
        max_length=12,
        default=getattr(settings, "LANGUAGE_CODE", "en"),
        help_text=_("BCP 47 language tag identifying the widget's content."),
    )
    is_primary_language = models.BooleanField(
        default=False,
        help_text=_("Marks the widget instance for the topic's primary language."),
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text=_("Ordering within the widget's column."),
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Optional short title displayed with the widget."),
    )
    body = models.TextField(
        blank=True,
        help_text=_("Free-form textual payload for the widget."),
    )
    payload = models.JSONField(
        blank=True,
        default=dict,
        help_text=_("Structured payload for widget specific data."),
    )
    ai_context = models.JSONField(
        blank=True,
        default=dict,
        help_text=_("State shared with AI assistants when suggesting updates."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TopicWidgetQuerySet.as_manager()

    class Meta:
        ordering = ("display_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("topic", "widget_type"),
                condition=Q(is_primary_language=True),
                name="widgets_unique_primary_per_type",
            ),
            models.UniqueConstraint(
                fields=("topic", "widget_type", "language_code"),
                condition=Q(widget_type__in=[
                    WidgetType.TITLE,
                    WidgetType.RECAP,
                    WidgetType.COVER_IMAGE,
                    WidgetType.TIMELINE,
                    WidgetType.EVENTS,
                    WidgetType.RELATED_TOPICS,
                    WidgetType.EXTERNAL_LINKS,
                    WidgetType.DOCUMENTS,
                    WidgetType.ENTITIES,
                ]),
                name="widgets_unique_singleton_per_language",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.is_primary_language and self.language_code != getattr(settings, "LANGUAGE_CODE", "en"):
            raise ValidationError(
                {"is_primary_language": _("Primary widgets must use the project's default language code.")}
            )

        definition = WidgetRegistry.get(self.widget_type)
        if not definition.multiple_per_topic:
            clash = (
                TopicWidget.objects.exclude(pk=self.pk)
                .filter(
                    topic=self.topic,
                    widget_type=self.widget_type,
                    language_code=self.language_code,
                )
                .exists()
            )
            if clash:
                raise ValidationError(
                    _("Only one widget of this type is allowed per topic and language."),
                )

    def save(self, *args, **kwargs):
        if kwargs.get("raw"):
            super().save(*args, **kwargs)
            return

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.topic_id}:{self.widget_type}:{self.language_code}"
