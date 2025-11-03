from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
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


class WidgetAPIExecution(models.Model):
    """Track LLM executions performed for widgets."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        SUCCESS = "success", _("Success")
        FAILURE = "failure", _("Failure")
        MANUAL = "manual", _("Manual")

    topic = models.ForeignKey(
        "topics.Topic",
        related_name="widget_api_executions",
        on_delete=models.CASCADE,
    )
    section = models.ForeignKey(
        "topics.TopicSection",
        related_name="executions",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    widget = models.ForeignKey(
        "widgets.Widget",
        related_name="executions",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="widget_api_executions",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    widget_type = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Registry type identifier used to resolve execution strategy."),
    )
    prompt_template = models.TextField(blank=True)
    prompt_context = models.JSONField(default=dict, blank=True)
    prompt_text = models.TextField(blank=True)
    extra_instructions = models.TextField(blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    tools = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(blank=True, null=True)
    parsed_response = models.JSONField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    error_message = models.TextField(blank=True, null=True)
    error_code = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def mark_running(self) -> None:
        """Update the execution to indicate it has started."""

        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_failure(self, *, message: str, code: str | None = None) -> None:
        """Persist a failure result."""

        self.status = self.Status.FAILURE
        self.error_message = message
        self.error_code = code
        self.completed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "error_message",
                "error_code",
                "completed_at",
                "updated_at",
            ]
        )

    def mark_success(self) -> None:
        """Persist a successful execution."""

        self.status = self.Status.SUCCESS
        self.error_message = None
        self.error_code = None
        self.completed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "error_message",
                "error_code",
                "completed_at",
                "updated_at",
            ]
        )
