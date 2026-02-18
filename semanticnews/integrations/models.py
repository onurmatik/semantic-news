import uuid

from django.db import models


class ExternalTopicConnection(models.Model):
    """Tracks remote topic IDs for provider connections."""

    PROVIDER_NEWSRADAR = "newsradar"
    PROVIDER_CHOICES = (
        (PROVIDER_NEWSRADAR, "NewsRadar"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, db_index=True)
    topic = models.ForeignKey(
        "topics.Topic",
        on_delete=models.CASCADE,
        related_name="external_connections",
    )
    external_topic_id = models.CharField(max_length=255, db_index=True)
    display_name = models.CharField(max_length=255, blank=True)
    query = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            ("provider", "topic"),
            ("provider", "external_topic_id"),
        )
        ordering = ("-updated_at",)

    def __str__(self):
        return f"{self.provider}:{self.external_topic_id} -> {self.topic_id}"
