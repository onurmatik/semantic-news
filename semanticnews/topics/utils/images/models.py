from django.db import models


class TopicImage(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='images', blank=True, null=True)
    image = models.ImageField(upload_to='topics_images')
    thumbnail = models.ImageField(upload_to='topics_images', blank=True, null=True)
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
    error_code = models.CharField(blank=True, null=True, max_length=20)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return self.topic.title
