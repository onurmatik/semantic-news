import uuid

from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, get_language
from slugify import slugify
from openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex
from semanticnews.users.models import User
from ..utils import translate, get_relevance


def slugify_topic(name, event_date=None):
    if event_date:
        slug = slugify(
            f'{name} '
            f'{event_date.strftime("%-d")} '
            f'{_(event_date.strftime("%B"))} '
            f'{event_date.strftime("%Y")}'
        )
    else:
        slug = slugify(name)
    return slug


class Topic(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    status = models.CharField(max_length=1, db_index=True, choices=(
        ('r', 'Removed'),
        ('d', 'Draft'),
        ('p', 'Published'),
    ), default='d')
    event_date = models.DateField(blank=True, null=True, db_index=True)

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
            text = (
                f"{self.name}\n"
                f"{', '.join(self.entities)}\n"
                f"{', '.join(self.categories)}\n"
            )
            embedding = client.embeddings.create(
                input=text,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding

    @cached_property
    def category_objects(self):
        slugs = [slugify(kw) for kw in self.categories]
        return Keyword.objects.filter(slug__in=slugs, ignore=False)

    @cached_property
    def get_similar_topics(self, limit=5):
        return Topic.objects\
                   .exclude(id=self.id)\
                   .exclude(embedding__isnull=True)\
                   .exclude(status='r')\
                   .order_by(L2Distance('embedding', self.embedding))[:limit]

    @cached_property
    def get_timeline(self, limit=5):
        # Related topics with event_date
        max_distance = 1
        return Topic.objects\
                .exclude(event_date__isnull=True)\
                .exclude(embedding__isnull=True)\
                .exclude(status='r')\
                .annotate(distance=L2Distance('embedding', self.embedding))\
                .filter(distance__lte=max_distance)\
                .order_by('event_date')[:limit]

    @cached_property
    def contributors(self):
        users = User.objects.filter(topiccontent__topic=self).exclude(topiccontent__added_by__isnull=True)
        if self.created_by:
            users |= User.objects.filter(id=self.created_by.id)
        return users.distinct()


class TopicContent(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    content = models.ForeignKey('contents.Content', on_delete=models.CASCADE)

    added_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
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
    name_en = models.CharField(max_length=200, blank=True, null=True)

    slug = models.CharField(max_length=100, blank=True, unique=True)
    slug_en = models.CharField(max_length=100, blank=True, null=True)

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
        if self.name_en and not self.slug_en:
            self.slug_en = slugify(self.name_en)

        if self.embedding is None or len(self.embedding) == 0:
            self.embedding = self.get_embedding()

        super().save(**kwargs)

        # If English name is missing, enqueue translation
        if not self.name_en:
            from .tasks import translate_keyword  # lazy import
            translate_keyword.delay_on_commit(self.pk)

    def get_embedding(self):
        if self.embedding is None or len(self.embedding) == 0:
            client = OpenAI()
            embedding = client.embeddings.create(
                input=self.name,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding
