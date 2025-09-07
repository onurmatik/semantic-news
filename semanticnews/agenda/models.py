import uuid
from urllib.parse import urlparse

from django.db import models
from django.urls import reverse
from django.conf import settings
from semanticnews.openai import OpenAI
from pgvector.django import VectorField, HnswIndex
from slugify import slugify


class Event(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    date = models.DateField(db_index=True)

    categories = models.ManyToManyField('agenda.Category', blank=True)
    significance = models.PositiveSmallIntegerField(choices=(
        (1, 'Very low'),
        (2, 'Low'),
        (3, 'Normal'),
        (4, 'High'),
        (5, 'Very high'),
    ), default=4)
    locality = models.ForeignKey('agenda.Locality', on_delete=models.CASCADE, blank=True, null=True)

    status = models.CharField(max_length=20, choices=(
        ('draft', 'Draft'),
        ('published', 'Published'),
    ), default='draft')

    sources = models.ManyToManyField('agenda.Source', blank=True)

    confidence = models.FloatField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    embedding = VectorField(dimensions=1536, blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.date}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['title', 'date'], name='unique_entry_title_date'),
        ]
        indexes = [
            HnswIndex(
                name='entry_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_l2_ops']
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        if not self.embedding:
            self.embedding = self.get_embedding()

        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        # Use zero-padded YYYY/MM/DD to match the requested format exactly
        return reverse(
            'event_detail',
            kwargs={
                'year': f'{self.date:%Y}',
                'month': f'{self.date:%m}',
                'day': f'{self.date:%d}',
                'slug': self.slug,
            },
        )

    def get_embedding(self):
        if self.pk is None:
            return None

        if self.embedding is None or len(self.embedding) == 0:
            client = OpenAI()
            text = (
                f"{self.title} - {self.date}\n"
                f"{', '.join([c.name for c in self.categories.all()])}"
            )
            embedding = client.embeddings.create(
                input=text,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding

    @property
    def description(self):
        desc = self.descriptions.last()
        if desc:
            return desc.description


class Description(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='descriptions')
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='event_descriptions',
        blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return self.description


class Locality(models.Model):
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'localities'


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'categories'


class Source(models.Model):
    url = models.URLField(max_length=200)
    domain = models.CharField(max_length=200, db_index=True)

    def __str__(self):
        return self.url

    def save(self, *args, **kwargs):
        if not self.domain:
            self.domain = self.get_domain()
        super().save(*args, **kwargs)

    def get_domain(self):
        parsed_url = urlparse(self.url)
        domain = parsed_url.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
