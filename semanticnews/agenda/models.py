import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.conf import settings
from pgvector.django import VectorField, HnswIndex
from slugify import slugify


class Entry(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    date = models.DateField(db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    previous_version = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='next_version'
    )

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = 'Agenda entry'
        verbose_name_plural = 'Agenda entries'
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

    def clean(self):
        super().clean()
        # prevent self-loop
        if self.previous_version and self.previous_version == self.id:
            raise ValidationError({"update_of": "An entry cannot update itself."})

    def get_absolute_url(self) -> str:
        # Use zero-padded YYYY/MM/DD to match the requested format exactly
        return reverse(
            'entry_detail',
            kwargs={
                'year': f'{self.date:%Y}',
                'month': f'{self.date:%m}',
                'day': f'{self.date:%d}',
                'slug': self.slug,
            },
        )

    @property
    def latest(self):
        node, version = self, 1
        while getattr(node, 'previous_version', None):
            node = node.previous_version
            version += 1
        return node, version
