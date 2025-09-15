from django.db import models


class TopicMedia(models.Model):
    MEDIA_TYPES = [
        ("image", "Image"),
        ("youtube", "YouTube"),
        ("other", "Other"),
    ]

    topic = models.ForeignKey(
        'topics.Topic', on_delete=models.CASCADE, related_name='media'
    )
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES)
    url = models.URLField(blank=True, null=True)
    image = models.ImageField(upload_to='topics_media', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return f"{self.media_type} for {self.topic.title}"
