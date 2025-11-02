from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Widget(models.Model):
    """Reusable widget definition that can be attached to topic sections."""

    name = models.CharField(max_length=150, unique=True)
    prompt_template = models.TextField(blank=True, help_text=_("Prompt sent to the LLM for this widget."))
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

    def __str__(self) -> str:
        return self.name

    def clean(self):
        """Validate widget JSON metadata."""

        super().clean()

        errors = {}

        if self.response_format in (None, ""):
            # Normalise falsy values into an empty object so downstream code has a dict.
            self.response_format = {}
        if not isinstance(self.response_format, dict):
            errors["response_format"] = _("Response format must be a JSON object.")

        if self.tools in (None, ""):
            self.tools = []
        if not isinstance(self.tools, list):
            errors["tools"] = _("Tools must be provided as a list of strings.")
        else:
            invalid_tools = [tool for tool in self.tools if not isinstance(tool, str) or not tool.strip()]
            if invalid_tools:
                errors["tools"] = _("Each tool identifier must be a non-empty string.")

        if errors:
            raise ValidationError(errors)
