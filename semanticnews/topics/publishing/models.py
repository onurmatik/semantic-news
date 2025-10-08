from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class TopicPublication(models.Model):
    """Snapshot of a topic captured at publish time."""

    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        related_name='publications',
    )
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='topic_publications',
    )
    layout_snapshot = models.JSONField(default=dict)
    context_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'
        ordering = ('-published_at', 'id')

    def __str__(self):
        return f"Publication for {self.topic} at {self.published_at:%Y-%m-%d %H:%M:%S}"


class TopicPublicationModule(models.Model):
    """Serialized module payload stored for a publication."""

    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='modules',
    )
    module_key = models.CharField(max_length=50)
    placement = models.CharField(max_length=20)
    display_order = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict)

    class Meta:
        app_label = 'topics'
        ordering = ('placement', 'display_order', 'id')

    def __str__(self):
        return f"{self.module_key} ({self.placement}) for {self.publication_id}"


class TopicPublicationSnapshot(models.Model):
    """Generic snapshot payload captured during publication."""

    publication = models.ForeignKey(
        TopicPublication,
        on_delete=models.CASCADE,
        related_name='snapshots',
    )
    component_type = models.CharField(max_length=100)
    module_key = models.CharField(max_length=100, blank=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'
        ordering = ('publication', 'id')
        indexes = [
            models.Index(fields=('publication', 'component_type')),
        ]

    def __str__(self):
        return f"Snapshot {self.component_type} for publication {self.publication_id}"
