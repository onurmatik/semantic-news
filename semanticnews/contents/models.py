import uuid

from semanticnews.openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex
from django.db import models
from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator
from django.conf import settings

from semanticnews.utils import get_relevance


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

    language_code = models.CharField(max_length=10, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='content'
    )

    events = models.ManyToManyField(
        'agenda.Event',
        through='ContentEvent',
        related_name='contents'
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
            with OpenAI() as client:
                embedding = client.embeddings.create(
                    input=self.markdown,
                    model='text-embedding-3-small'
                ).data[0].embedding
            return embedding


class ContentEvent(models.Model):
    content = models.ForeignKey('contents.Content', on_delete=models.CASCADE)
    event = models.ForeignKey('agenda.Event', on_delete=models.CASCADE)

    source = models.CharField(
        max_length=10,
        choices=[('agent','Agent'), ('user','User'), ('rule','Rule')],
        default='agent'
    )
    relevance = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['content', 'event', 'source'], name='unique_content_event__source')
        ]
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['content']),
            models.Index(fields=['-relevance']),
        ]

    def save(self, *args, **kwargs):
        if self.relevance is None and getattr(self.content, 'embedding', None) is not None and getattr(self.event, 'embedding', None) is not None:
            self.relevance = get_relevance(self.content.embedding, self.event.embedding)
        super().save(*args, **kwargs)
