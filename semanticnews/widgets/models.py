from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class WidgetType(models.TextChoices):
    """All supported widget shells within a topic."""

    IMAGE = "image", _("Image block")
    TEXT = "text", _("Text block")
    DATA = "data", _("Data block")
    WEBCONTENT = "webcontent", _("Web content")


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
                condition=models.Q(is_primary_language=True),
                name="widgets_unique_primary_per_type",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.is_primary_language and self.language_code != getattr(settings, "LANGUAGE_CODE", "en"):
            raise ValidationError(
                {"is_primary_language": _("Primary widgets must use the project's default language code.")}
            )

    def save(self, *args, **kwargs):
        if kwargs.get("raw"):
            super().save(*args, **kwargs)
            return

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.topic_id}:{self.widget_type}:{self.language_code}"
