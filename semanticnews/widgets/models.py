from django.db import models
from django.utils import timezone
from django import forms
from django.utils.translation import gettext_lazy as _


INPUT_FIELD_TYPES = {
    "text": forms.CharField,
    "char": forms.CharField,
    "markdown": lambda: forms.CharField(widget=forms.Textarea(attrs={"class": "markdown"})),
    "url": forms.URLField,
    "img": forms.ImageField,
    "doc": forms.FileField,
}


class Widget(models.Model):
    """Reusable widget definition that can be attached to topic sections."""

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)

    input_format = models.JSONField(
        default=[{"type": "text", "required": True}],
        help_text=_("List of input field definitions."),
    )
    context_structure = models.JSONField(
        blank=True, default=dict,
        help_text=_("The context parameters to be passed to the template."),
    )

    template = models.TextField(
        blank=True,
        help_text=_("Template used to render the widget's content."),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    def get_response_format(self):
        """Create the response format definition to be fed to the LLM based on the context attribute."""


class WidgetAction(models.Model):
    widget = models.ForeignKey(Widget, on_delete=models.CASCADE, related_name="actions")
    name = models.CharField(max_length=150, unique=True)
    icon = models.CharField(max_length=150, blank=True)
    prompt_template = models.TextField(blank=True)
    tools = models.JSONField(
        blank=True, default=list,
        help_text=_("List of tool identifiers made available to the LLM."),
    )

    def __str__(self):
        return self.name


class WidgetActionExecution(models.Model):
    """Track LLM executions performed for widgets."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        SUCCESS = "success", _("Success")
        FAILURE = "failure", _("Failure")

    action = models.ForeignKey(WidgetAction, on_delete=models.CASCADE)
    section = models.ForeignKey(
        "topics.TopicSection",
        related_name="executions",
        on_delete=models.SET_NULL,
        blank=True, null=True,
    )
    widget_type = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Registry type identifier used to resolve execution strategy."),
    )
    prompt_template = models.TextField(blank=True)
    prompt_context = models.JSONField(blank=True, default=dict)
    prompt_text = models.TextField(blank=True)
    extra_instructions = models.TextField(blank=True)
    model_name = models.CharField(max_length=150, blank=True)
    tools = models.JSONField(blank=True, default=list)
    metadata = models.JSONField(blank=True, default=dict)
    response_schema = models.JSONField(blank=True, null=True)
    raw_response = models.JSONField(blank=True, null=True)
    parsed_response = models.JSONField(blank=True, null=True)
    response = models.JSONField(blank=True, null=True)
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

    @property
    def widget(self) -> Widget:
        """Convenience accessor to the related widget definition."""

        return self.action.widget

    @property
    def topic(self):
        """Return the topic associated with this execution."""

        if self.section:
            return self.section.topic
        return getattr(self, "_topic", None)

    @topic.setter
    def topic(self, value):
        self._topic = value

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
