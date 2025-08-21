import uuid

from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _, get_language
from django.conf import settings
from slugify import slugify
from openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex
from ..utils import translate, get_relevance


class Topic(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    status = models.CharField(max_length=1, db_index=True, choices=(
        ('r', 'Removed'),
        ('d', 'Draft'),
        ('p', 'Published'),
    ), default='d')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='topics'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    categories = models.ManyToManyField('Keyword', through='TopicCategory', blank=True)

    contents = models.ManyToManyField('contents.Content', blank=True, through='TopicContent', related_name='topics')

    def __str__(self):
        return f"{self.title}"

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
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

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

    def get_absolute_url(self):
        return reverse('topics_detail', args=[str(self.slug)])

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

    @cached_property
    def contributors(self):
        User = get_user_model()  # noqa
        users = User.objects.filter(topiccontent__topic=self).exclude(topiccontent__added_by__isnull=True)
        if self.created_by:
            users |= User.objects.filter(id=self.created_by.id)
        return users.distinct()


class TopicContent(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    content = models.ForeignKey('contents.Content', on_delete=models.CASCADE)

    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    added_at = models.DateTimeField(auto_now_add=True)

    embedding = VectorField(dimensions=1536, blank=True, null=True)
    relevance = models.FloatField()

    def __str__(self):
        return f'Topic: {self.topic}'

    class Meta:
        indexes = [
            HnswIndex(
                name='topiccontent_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Update topic metadata
        self.topic.updated_at = timezone.now()
        if self.topic.status == 'd':  # draft
            self.topic.status = 'p'  # published
        self.topic.save()

        if is_new:
            # Trigger recap update for the topic
            from .tasks import update_topic_recap
            update_topic_recap.delay_on_commit(self.topic.pk)

    def get_relevance(self):
        return get_relevance(self.topic.embedding, self.embedding)


class Keyword(models.Model):
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, blank=True, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    embedding = VectorField(dimensions=1536, blank=True, null=True)

    # Variant of another more standard name
    variant_of = models.ForeignKey('self', blank=True, null=True, on_delete=models.CASCADE)

    # Keywords to ignore; ambiguous abbreviations, etc.
    ignore = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            HnswIndex(
                name='keyword_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]

    def get_name_i18n(self):
        if get_language() != 'tr':
            return self.name_en or self.name
        return self.name

    def save(self, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        if self.embedding is None or len(self.embedding) == 0:
            self.embedding = self.get_embedding()

        super().save(**kwargs)

    def get_embedding(self):
        if self.embedding is None or len(self.embedding) == 0:
            client = OpenAI()
            embedding = client.embeddings.create(
                input=self.name,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding


class TopicCategory(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    category = models.ForeignKey(Keyword, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)

