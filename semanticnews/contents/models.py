import uuid

from openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex
from django.db import models
from django.core.validators import URLValidator
from django.conf import settings


class Source(models.Model):
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Content(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, blank=True, null=True, related_name="contents")
    url = models.URLField(unique=True, null=True, blank=True, validators=[URLValidator()])

    content_type = models.CharField(max_length=100, db_index=True)

    title = models.CharField(max_length=500, blank=True, null=True)
    markdown = models.TextField(blank=True, null=True)

    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    language_code = models.CharField(max_length=10, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='content'
    )

    # Source specific extra information, if any
    metadata = models.JSONField(blank=True, null=True)

    embedding = VectorField(dimensions=1536, blank=True, null=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            HnswIndex(
                name='content_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]

    def __str__(self):
        return self.title or self.url

    def get_embedding(self):
        if self.embedding is None or len(self.embedding) == 0 and self.markdown:
            client = OpenAI()
            embedding = client.embeddings.create(
                input=self.markdown,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding

    def get_related_topics(self, limit=5):
        # Similar topics by embedding vector
        from ..topics.models import Topic
        return Topic.objects.exclude(embedding__isnull=True).exclude(
            name__isnull=True).exclude(status='r'
        ).order_by(L2Distance('embedding', self.embedding))[:limit]

    def get_related_content(self, limit=5):
        # Similar content by embedding vector
        return Content.objects.exclude(embedding__isnull=True).order_by(L2Distance('embedding', self.embedding))[:limit]
