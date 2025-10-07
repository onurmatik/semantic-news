from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from ....utils import get_relevance


class TopicEvent(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE)
    event = models.ForeignKey('agenda.Event', on_delete=models.CASCADE)

    role = models.CharField(
        max_length=20,
        choices=[('support', 'Support'), ('counter', 'Counter'), ('context', 'Context')],
        default='support'
    )
    source = models.CharField(
        max_length=10,
        choices=[('user', 'User'), ('agent', 'Agent'), ('rule', 'Rule')],
        default='user'
    )

    relevance = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    significance = models.PositiveSmallIntegerField(
        choices=((1, 'Normal'), (2, 'High'), (3, 'Very high')),
        default=1,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        app_label = 'topics'
        constraints = [
            models.UniqueConstraint(fields=['topic', 'event'], name='unique_topic_event')
        ]
        indexes = [
            models.Index(fields=['topic']),
            models.Index(fields=['event']),
            models.Index(fields=['topic', 'significance']),
        ]

    def __str__(self):
        return f"{self.topic} ↔ {self.event} ({self.role})"

    def save(self, *args, **kwargs):
        if (
            self.relevance is None
            and getattr(self.topic, 'embedding', None) is not None
            and getattr(self.event, 'embedding', None) is not None
        ):
            self.relevance = get_relevance(self.topic.embedding, self.event.embedding)
        super().save(*args, **kwargs)
