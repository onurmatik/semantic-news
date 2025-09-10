from django.db import models


class TopicRecap(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='recaps')
    recap = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("in_progress", "In progress"),
            ("finished", "Finished"),
            ("error", "Error"),
        ],
        default="in_progress",
    )
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"Recap for {self.topic}"
