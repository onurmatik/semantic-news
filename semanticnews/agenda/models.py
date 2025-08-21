import uuid
from django.db import models
from django.conf import settings
from pgvector.django import VectorField, HnswIndex
from slugify import slugify


class Entry(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    date = models.DateField(db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    contents = models.ManyToManyField('contents.Content', blank=True, through='EntryContent', related_name='entries')

    def __str__(self):
        return f"{self.name}"

    class Meta:
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
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)


class EntryContent(models.Model):
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE)
    content = models.ForeignKey('contents.Content', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    relevance = models.FloatField(blank=True, null=True)
