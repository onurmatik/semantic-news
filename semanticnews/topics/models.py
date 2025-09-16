import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.functional import cached_property
from django.urls import reverse
from django.conf import settings
from slugify import slugify
from semanticnews.openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex

from ..utils import get_relevance
from .utils.recaps.models import TopicRecap
from .utils.narratives.models import TopicNarrative
from .utils.images.models import TopicImage
from .utils.embeds.models import TopicYoutubeVideo
from .utils.relations.models import TopicEntityRelation
from .utils.documents.models import TopicDocumentLink, TopicWebpageLink
from .utils.timeline.models import TopicEvent


class Topic(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    status = models.CharField(max_length=20, db_index=True, choices=(
        ('removed', 'Removed'),
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ), default='draft')

    based_on = models.ForeignKey(
        'Topic', related_name='derivatives',
        on_delete=models.SET_NULL, blank=True, null=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL, related_name='topics'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    events = models.ManyToManyField(
        'agenda.Event', through='TopicEvent',
        related_name='topics', blank=True
    )
    contents = models.ManyToManyField(
        'contents.Content', through='TopicContent',
        related_name='topics', blank=True
    )
    entities = models.ManyToManyField(
        'entities.Entity', through='TopicEntity',
        related_name='topics', blank=True
    )

    # Updated when the events or contents change
    updated_at = models.DateTimeField(auto_now=True)

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
        """Save the topic and refresh its embedding."""
        if not self.slug:
            self.slug = slugify(self.title)

        # Always recompute the embedding so it reflects the latest topic data
        self.embedding = self.get_embedding(force=True)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('topics_detail', kwargs={
            'slug': str(self.slug),
            'username': self.created_by.username,
        })

    @cached_property
    def image(self):
        img = self.images.last()
        if img:
            return img.image

    @cached_property
    def thumbnail(self):
        img = self.images.last()
        if img:
            return img.thumbnail

    def build_context(self):
        content_md = f"# {self.title}\n\n"

        events = self.events.all()
        if events:
            content_md += "## Events\n\n"
            for event in events:
                content_md += f"- {event.title} ({event.date})\n"

        contents = self.contents.all()
        if contents:
            content_md += "\n## Contents\n\n"
            for c in contents:
                title = c.title or ""
                text = c.markdown or ""
                content_md += f"### {title}\n{text}\n\n"

        # TODO: Add data insights to the context

        return content_md

    def get_embedding(self, force: bool = False):
        """Return an embedding vector for the topic.

        Args:
            force: If ``True``, generate a new embedding even if one already
                exists. Otherwise, reuse the current embedding when available.
        """
        if force or self.embedding is None or len(self.embedding) == 0:
            client = OpenAI()
            embedding = client.embeddings.create(
                input=self.build_context(),
                model='text-embedding-3-small'
            ).data[0].embedding
            return embedding

    @cached_property
    def get_similar_topics(self, limit=5):
        return (Topic.objects
                .exclude(id=self.id)
                .exclude(embedding__isnull=True)
                .filter(status='published')
                .order_by(L2Distance('embedding', self.embedding))[:limit])

    def clone_for_user(self, user):
        """Create a draft copy of this topic for the given user.

        The clone includes all related objects so that the user
        can continue editing independently.
        """
        cloned = Topic.objects.create(
            title=self.title,
            slug=self.slug,
            embedding=self.embedding,
            based_on=self,
            created_by=user,
            status="draft",
        )

        for te in TopicEvent.objects.filter(topic=self):
            TopicEvent.objects.create(
                topic=cloned,
                event=te.event,
                role=te.role,
                source=te.source,
                relevance=te.relevance,
                significance=te.significance,
                created_by=user,
            )

        for tc in TopicContent.objects.filter(topic=self):
            TopicContent.objects.create(
                topic=cloned,
                content=tc.content,
                role=tc.role,
                source=tc.source,
                relevance=tc.relevance,
                created_by=user,
            )

        for recap in self.recaps.all():
            TopicRecap.objects.create(
                topic=cloned, recap=recap.recap, status="finished"
            )
        for narrative in self.narratives.all():
            TopicNarrative.objects.create(
                topic=cloned, narrative=narrative.narrative, status="finished"
            )
        for relation in self.entity_relations.all():
            TopicEntityRelation.objects.create(
                topic=cloned,
                relations=relation.relations,
                status="finished",
            )
        for image in self.images.all():
            TopicImage.objects.create(
                topic=cloned,
                image=image.image,
                thumbnail=image.thumbnail,
            )

        for document_link in self.document_links.all():
            TopicDocumentLink.objects.create(
                topic=cloned,
                title=document_link.title,
                url=document_link.url,
                description=document_link.description,
                document_type=document_link.document_type,
                created_by=user,
            )

        for webpage_link in self.webpage_links.all():
            TopicWebpageLink.objects.create(
                topic=cloned,
                title=webpage_link.title,
                url=webpage_link.url,
                description=webpage_link.description,
                created_by=user,
            )

        for entity in TopicEntity.objects.filter(topic=self):
            TopicEntity.objects.create(
                topic=cloned,
                entity=entity.entity,
                relevance=entity.relevance,
                created_by=user,
            )

        return cloned
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


class TopicEntity(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    entity = models.ForeignKey('entities.Entity', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    relevance = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    def __str__(self):
        return f'{self.topic} - {self.entity}'
