from django.db import models


class TopicImage(models.Model):
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='images', blank=True, null=True)
    image = models.ImageField(upload_to='topics_images')
    thumbnail = models.ImageField(upload_to='topics_images', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'topics'

    def __str__(self):
        return self.topic.title
