from django.db import models


class TopicText(models.Model):
    topic = models.ForeignKey(
        'topics.Topic',
        on_delete=models.CASCADE,
        related_name='texts',
    )
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)
    is_deleted = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ("in_progress", "In progress"),
            ("finished", "Finished"),
            ("error", "Error"),
        ],
        default="finished",
    )
    error_message = models.TextField(blank=True, null=True)
    error_code = models.CharField(blank=True, null=True, max_length=20)

    class Meta:
        app_label = 'topics'
        ordering = ['created_at']

    def __str__(self):
        return f"Text block for {self.topic}" if self.topic_id else "Text block"
