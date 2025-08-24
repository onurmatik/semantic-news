from django.db import models
from pgvector.django import VectorField, HnswIndex


class TopicImage(models.Model):
    image = models.ImageField(upload_to='topics_images')
    thumbnail = models.ImageField(upload_to='topics_images', blank=True, null=True)
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='images', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.topic.title
