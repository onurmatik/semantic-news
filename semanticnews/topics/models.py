import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.urls import reverse
from django.conf import settings
from slugify import slugify
from semanticnews.openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex

from ..utils import get_relevance
from .utils.recaps.models import TopicRecap
from .utils.text.models import TopicText
from .utils.images.models import TopicImage
from .utils.embeds.models import TopicYoutubeVideo
from .utils.relations.models import TopicEntityRelation
from .utils.documents.models import TopicDocument, TopicWebpage
from .utils.timeline.models import TopicEvent


class TopicModuleLayout(models.Model):
    """User-configurable placement information for topic utility modules."""

    PLACEMENT_PRIMARY = "primary"
    PLACEMENT_SIDEBAR = "sidebar"
    PLACEMENT_CHOICES = (
        (PLACEMENT_PRIMARY, "Primary"),
        (PLACEMENT_SIDEBAR, "Sidebar"),
    )

    topic = models.ForeignKey(
        "Topic",
        on_delete=models.CASCADE,
        related_name="module_layouts",
    )
    module_key = models.CharField(max_length=50)
    placement = models.CharField(
        max_length=20,
        choices=PLACEMENT_CHOICES,
        default=PLACEMENT_PRIMARY,
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]
        unique_together = ("topic", "module_key")

    def __str__(self):
        return f"{self.topic} · {self.module_key} ({self.placement})"


class Topic(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    slug = models.SlugField(max_length=200, blank=True, null=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    status = models.CharField(max_length=20, db_index=True, choices=(
        ('removed', 'Removed'),
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ), default='draft')
    latest_publication = models.ForeignKey(
        'topics.TopicPublication',
        on_delete=models.SET_NULL,
        related_name='+',
        blank=True,
        null=True,
    )
    last_published_at = models.DateTimeField(blank=True, null=True)

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
        return f"{self.title or 'Topic'}"

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

    def clean(self):
        super().clean()
        if self.status == "published":
            if not self.title:
                raise ValidationError({"title": "A title is required to publish a topic."})

            has_finished_recap = False
            if self.pk:
                has_finished_recap = self.recaps.filter(status="finished").exists()

            if not has_finished_recap:
                raise ValidationError({"status": "A recap is required to publish a topic."})

    def full_clean(self, exclude=None, validate_unique=True, validate_constraints=True):
        """Run validation while skipping the embedding field.

        ``VectorField`` instances from ``pgvector`` can be backed by numpy
        arrays. Django's model validation attempts to check whether blank
        fields contain an "empty" value by evaluating ``raw_value in
        field.empty_values``. When ``raw_value`` is a numpy array this raises
        ``ValueError`` because numpy does not define a boolean truth value for
        multi-element arrays. To avoid this, exclude the embedding field from
        Django's generic ``blank`` handling while still allowing the rest of
        the model (including our custom ``clean`` method) to run.
        """

        if exclude is None:
            exclude = []
        else:
            exclude = list(exclude)
        exclude.append("embedding")

        super().full_clean(
            exclude=exclude,
            validate_unique=validate_unique,
            validate_constraints=validate_constraints,
        )

    def save(self, *args, **kwargs):
        """
        Save the topic and refresh its embedding *after* the row exists.
        """
        if kwargs.get("raw"):
            super().save(*args, **kwargs)
            return

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)

        previous_slug = self.slug

        if self.title and not self.slug:
            self.slug = slugify(self.title)

        if update_fields is not None and self.slug != previous_slug:
            update_fields.add("slug")
            kwargs["update_fields"] = list(update_fields)

        self.full_clean()

        super().save(*args, **kwargs)

        emb = self.get_embedding(force=True)
        if emb is not None:
            # Avoid triggering full save logic again (and recursion)
            type(self).objects.filter(pk=self.pk).update(embedding=emb)
            # Keep in-memory instance consistent
            self.embedding = emb

    def get_absolute_url(self):
        return reverse('topics_detail', kwargs={
            'slug': str(self.slug),
            'username': self.created_by.username,
        })

    @property
    def active_events(self):
        return self.events.filter(topicevent__is_deleted=False)

    @property
    def active_recaps(self):
        return self.recaps.filter(is_deleted=False)

    @property
    def active_texts(self):
        return self.texts.filter(is_deleted=False)

    @property
    def active_entity_relations(self):
        return self.entity_relations.filter(is_deleted=False)

    @property
    def active_images(self):
        return self.images.filter(is_deleted=False)

    @property
    def active_documents(self):
        return self.documents.filter(is_deleted=False)

    @property
    def active_webpages(self):
        return self.webpages.filter(is_deleted=False)

    @property
    def active_datas(self):
        return self.datas.filter(is_deleted=False)

    @property
    def active_data_insights(self):
        return self.data_insights.filter(is_deleted=False)

    @property
    def active_data_visualizations(self):
        return self.data_visualizations.filter(is_deleted=False)

    @property
    def active_youtube_videos(self):
        return self.youtube_videos.filter(is_deleted=False)

    @property
    def active_tweets(self):
        return self.tweets.filter(is_deleted=False)

    @cached_property
    def image(self):
        latest = (
            self.images
            .filter(status="finished")
            .order_by("-created_at")
            .first()
        )
        return latest.image if latest else None

    @cached_property
    def thumbnail(self):
        latest = (
            self.images
            .filter(status="finished")
            .order_by("-created_at")
            .first()
        )
        return latest.thumbnail if latest else None

    def build_context(self):
        content_md = f"# {self.title or ''}\n\n"

        # If not saved yet, do not touch M2M relations
        if not self.pk:
            return content_md

        events_qs = (
            self.events.filter(topicevent__is_deleted=False).order_by("date")
        )

        if events_qs.exists():
            content_md += "## Events\n\n"
            for event in events_qs:
                content_md += f"- {event.title} ({event.date})\n"

        contents_qs = self.contents.all()
        if contents_qs.exists():
            content_md += "\n## Contents\n\n"
            for c in contents_qs:
                title = c.title or ""
                text = c.markdown or ""
                content_md += f"### {title}\n{text}\n\n"

        # TODO: Add data insights to the context

        return content_md

    def get_embedding(self, force: bool = False):
        """
        Return an embedding vector for the topic.
        If not forcing and we already have one, reuse it.
        """
        if not force and self.embedding is not None and len(self.embedding) > 0:
            return self.embedding

        with OpenAI() as client:
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

        for te in TopicEvent.objects.filter(topic=self, is_deleted=False):
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

        for recap in self.recaps.filter(is_deleted=False):
            TopicRecap.objects.create(
                topic=cloned, recap=recap.recap, status="finished"
            )
        for text in self.texts.filter(is_deleted=False):
            TopicText.objects.create(
                topic=cloned, content=text.content, status="finished"
            )
        for relation in self.entity_relations.filter(is_deleted=False):
            TopicEntityRelation.objects.create(
                topic=cloned,
                relations=relation.relations,
                status="finished",
            )
        for image in self.images.filter(is_deleted=False):
            TopicImage.objects.create(
                topic=cloned,
                image=image.image,
                thumbnail=image.thumbnail,
            )

        for document in self.documents.filter(is_deleted=False):
            TopicDocument.objects.create(
                topic=cloned,
                title=document.title,
                url=document.url,
                description=document.description,
                document_type=document.document_type,
                created_by=user,
            )

        for webpage in self.webpages.filter(is_deleted=False):
            TopicWebpage.objects.create(
                topic=cloned,
                title=webpage.title,
                url=webpage.url,
                description=webpage.description,
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
