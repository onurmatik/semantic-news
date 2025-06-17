import uuid
from urllib.parse import urlparse

from django.contrib.contenttypes.models import ContentType
from django.db.models import JSONField
from openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex
from polymorphic.models import PolymorphicModel
from django.utils.functional import cached_property
from django.db import models
from semanticnews.users.models import User


class Content(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(unique=True)
    title = models.CharField(max_length=500, blank=True, null=True)

    language_code = models.CharField(max_length=5, blank=True, null=True)
    time = models.DateTimeField(blank=True, null=True, db_index=True)

    summary = models.TextField(blank=True, null=True)
    keywords = models.JSONField(blank=True, default=list)

    # Generic FK to the source
    source_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, blank=True, null=True)
    source_object_id = models.PositiveIntegerField(blank=True, null=True)

    embedding = VectorField(dimensions=1536, blank=True, null=True)

    # Source specific extra information, if any
    metadata = JSONField(blank=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='content'
    )

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

    def save(self, *args, **kwargs):
        if not self.title and self.lang == 'tr':
            self.title = self.title_original
        if not self.title_en and self.lang == 'en':
            self.title_en = self.title_original

        if self.embedding is None or len(self.embedding) == 0:
            if self.title and self.summary:
                self.embedding = self.get_embedding()

        super().save(*args, **kwargs)

        # If not translated, enqueue translation
        if not self.title_en or not self.title:  # if either Turkish or English is missing, trigger translation
            from .tasks import translate_article
            translate_article.delay_on_commit(self.pk)

    @cached_property
    def source(self):
        parsed_url = urlparse(self.url)
        domain = parsed_url.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain

    def get_embedding(self):
        if self.embedding is None or len(self.embedding) == 0:
            client = OpenAI()
            text = (
                f"{self.title}\n"
                f"{self.summary}"
            )
            embedding = client.embeddings.create(
                input=text,
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding

    @cached_property
    def get_related_topics(self, limit=5):
        # Similar topics by embedding vector
        from ..topics.models import Topic
        return Topic.objects.exclude(embedding__isnull=True).exclude(
            name__isnull=True).exclude(status='r'
        ).order_by(L2Distance('embedding', self.embedding))[:limit]

    @cached_property
    def get_related_content(self, limit=5):
        # Similar content by embedding vector
        return Content.objects.exclude(embedding__isnull=True).exclude(title__isnull=True).exclude(
            summary__isnull=True
        ).order_by(L2Distance('embedding', self.embedding))[:limit]

    def translate(self, translation_model='gpt-4o-mini'):
        # Turkish => English translations
        to_translate = {
            'summary': self.summary
        }
        if not self.title_en:
            to_translate['title'] = self.title

        translation = translate(to_translate, model=translation_model)

        if not self.title_en:
            self.title_en = translation['title']

        self.summary_en = translation['summary']

        # English => Turkish title translation
        if self.title_en and not self.title:
            translation = translate({
                'title': self.title_en,
            }, from_to='en_tr', model=translation_model)
            self.title = translation['title']

        self.save()

    def get_title_i18n(self):
        if get_language() != 'tr':
            return self.title_en or self.title
        return self.title

    def get_summary_i18n(self):
        if get_language() != 'tr':
            return self.summary_en or self.summary
        return self.summary

