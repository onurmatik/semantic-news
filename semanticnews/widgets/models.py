from django.db import models
from django.utils.translation import gettext_lazy as _


class WidgetType(models.TextChoices):
    """Supported widget shells available to topics."""

    IMAGE = "image", _("Image block")
    TEXT = "text", _("Text block")
    DATA = "data", _("Data block")
    WEBCONTENT = "webcontent", _("Web content")


class Widget(models.Model):
    """Reusable widget definition that can be attached to topic sections."""

    name = models.CharField(max_length=150, unique=True)
    type = models.CharField(max_length=50, choices=WidgetType.choices)
    prompt = models.TextField(blank=True, help_text=_("Prompt sent to the LLM for this widget."))
    response_format = models.JSONField(
        blank=True,
        default=dict,
        help_text=_("Expected response formatting metadata."),
    )
    tools = models.JSONField(
        blank=True,
        default=list,
        help_text=_("List of tool identifiers made available to the LLM."),
    )
    template = models.TextField(
        blank=True,
        help_text=_("Template used to render the widget's content."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name
