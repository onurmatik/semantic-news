from django.db import models
from pgvector.django import VectorField, HnswIndex


class TopicImage(models.Model):
    image = models.ImageField(upload_to='images')
    thumbnail = models.ImageField(upload_to='images', blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True)
    topic = models.ForeignKey('topics.Topic', on_delete=models.CASCADE, related_name='images', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.embedding is None or len(self.embedding) == 0:
            if self.topic:
                self.embedding = self.topic.embedding
            elif self.keyword:
                self.embedding = self.keyword.embedding
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            HnswIndex(
                name='topicimage_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]
