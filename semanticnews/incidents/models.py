import uuid
from django.db import models
from pgvector.django import VectorField, HnswIndex
from semanticnews.users.models import User


class Incident(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    date = models.DateField(db_index=True)

    created_by = models.ForeignKey(
        User, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='topics'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    contents = models.ManyToManyField('contents.Content', blank=True, through='TopicContent', related_name='topics')

    def __str__(self):
        return f"{self.name}"

    class Meta:
        indexes = [
            HnswIndex(
                name='topic_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]

    def save(self, *args, **kwargs):
        if self.embedding is None or len(self.embedding) == 0:
            self.embedding = self.get_embedding()

        if not self.slug:
            self.slug = slugify_topic(self.name, self.event_date)

        super().save(*args, **kwargs)
