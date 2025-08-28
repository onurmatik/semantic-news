import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.functional import cached_property
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _, get_language
from django.conf import settings
from slugify import slugify
from semanticnews.openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex
from ..utils import translate, get_relevance


class Topic(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    status = models.CharField(max_length=20, db_index=True, choices=(
        ('removed', 'Removed'),
        ('draft', 'Draft'),
        ('published', 'Published'),
    ), default='draft')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='topics'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    events = models.ManyToManyField(
        'agenda.Event', through='TopicEvent',
        related_name='topics', blank=True)
    contents = models.ManyToManyField(
        'contents.Content', through='TopicContent',
        related_name='topics', blank=True)

    def __str__(self):
        return f"{self.title}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['slug', 'created_by'], name='unique_topic_title_user')
        ]
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
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('topics_detail', kwargs={
            'slug': str(self.slug),
            'username': self.created_by.username,
        })

    @cached_property
    def image(self):
        img = self.images.first()
        if img:
            return img.image

    @cached_property
    def thumbnail(self):
        img = self.images.first()
        if img:
            return img.thumbnail

    def get_embedding(self):
        if self.embedding is None or len(self.embedding) == 0:
            client = OpenAI()
            embedding = client.embeddings.create(
                input=self.title,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding

    @cached_property
    def get_similar_topics(self, limit=5):
        return Topic.objects\
                   .exclude(id=self.id)\
                   .exclude(embedding__isnull=True)\
                   .exclude(status='r')\
                   .order_by(L2Distance('embedding', self.embedding))[:limit]


class TopicEvent(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    event = models.ForeignKey('agenda.Event', on_delete=models.CASCADE)

    role = models.CharField(
        max_length=20,
        choices=[('support','Support'), ('counter','Counter'), ('context','Context')],
        default='support'
    )
    source = models.CharField(
        max_length=10,
        choices=[('user','User'), ('agent','Agent'), ('rule','Rule')],
        default='user'
    )

    relevance = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    pinned = models.BooleanField(default=False)
    rank = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['topic', 'event'], name='unique_topic_event')
        ]
        indexes = [
            models.Index(fields=['topic']),
            models.Index(fields=['event']),
            models.Index(fields=['topic', 'pinned', 'rank']),
        ]

    def __str__(self):
        return f"{self.topic} ↔ {self.event} ({self.role})"

    def save(self, *args, **kwargs):
        if self.relevance is None and getattr(self.topic, 'embedding', None) is not None and getattr(self.event, 'embedding', None) is not None:
            self.relevance = get_relevance(self.topic.embedding, self.event.embedding)
        super().save(*args, **kwargs)


class TopicContent(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    content = models.ForeignKey('contents.Content', on_delete=models.CASCADE)

    role = models.CharField(
        max_length=20,
        choices=[('evidence', 'Evidence'), ('summary', 'Summary'), ('quote', 'Quote')],
        default='evidence'
    )
    source = models.CharField(
        max_length=10,
        choices=[('user', 'User'), ('ml', 'ML'), ('rule', 'Rule')],
        default='user'
    )

    relevance = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    pinned = models.BooleanField(default=False)
    rank = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['topic', 'content'], name='unique_topic_content')
        ]
        indexes = [models.Index(fields=['topic']), models.Index(fields=['content'])]

    def __str__(self):
        return f'Topic: {self.topic}'

    def save(self, *args, **kwargs):
        if self.relevance is None and getattr(self.topic, 'embedding', None) is not None and getattr(self.content, 'embedding', None) is not None:
            self.relevance = get_relevance(self.topic.embedding, self.content.embedding)
        super().save(*args, **kwargs)
