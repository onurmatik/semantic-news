import json
import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext
from django.urls import reverse
from django.conf import settings
from slugify import slugify
from semanticnews.openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex

from ..utils import get_relevance
from ..widgets.recaps.models import TopicRecap
from ..widgets.text.models import TopicText
from ..widgets.images.models import TopicImage
from ..widgets.embeds.models import TopicYoutubeVideo
from ..widgets.relations.models import TopicEntityRelation
from ..widgets.documents.models import TopicDocument, TopicWebpage
from ..widgets.timeline.models import TopicEvent


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

    related_topics = models.ManyToManyField(
        'self',
        through='RelatedTopic',
        symmetrical=False,
        related_name='related_to_topics',
        blank=True,
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
        # Avoid triggering full save logic again (and recursion)
        type(self).objects.filter(pk=self.pk).update(embedding=emb)
        # Keep in-memory instance consistent
        self.embedding = emb

    def get_absolute_url(self):
        if self.slug:
            return reverse(
                'topics_detail',
                kwargs={
                    'slug': str(self.slug),
                    'username': self.created_by.username,
                },
            )

        return reverse(
            'topics_detail_redirect',
            kwargs={
                'topic_uuid': str(self.uuid),
                'username': self.created_by.username,
            },
        )

    @property
    def display_title(self) -> str:
        title = (self.title or "").strip()
        return title or gettext("Untitled")

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

    @property
    def active_related_topic_links(self):
        return self.topic_related_topics.filter(is_deleted=False)

    @property
    def active_related_topics(self):
        return self.related_topics.filter(
            relatedtopic__topic=self,
            relatedtopic__is_deleted=False,
        )

    @property
    def has_unpublished_changes(self) -> bool:
        """Return whether the topic has edits not reflected in a publication."""

        if not self.last_published_at:
            return True

        if not self.updated_at:
            return False

        return self.updated_at > self.last_published_at

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
        parts = [f"# {self.title or ''}\n\n"]

        # If not saved yet, do not touch M2M relations
        if not self.pk:
            return "".join(parts)

        def append_section(title: str, body: str):
            if not body:
                return
            if not body.endswith("\n"):
                body_local = f"{body}\n"
            else:
                body_local = body
            parts.append(f"## {title}\n\n")
            parts.append(body_local)
            parts.append("\n")

        events_qs = self.events.filter(topicevent__is_deleted=False).order_by("date")
        if events_qs.exists():
            event_lines = [f"- {event.title} ({event.date})" for event in events_qs]
            append_section("Events", "\n".join(event_lines))

        contents_qs = self.contents.all().order_by("created_at")
        if contents_qs.exists():
            content_sections = []
            for content in contents_qs:
                title = content.title or "Content"
                text = content.markdown or ""
                content_sections.append(f"### {title}\n{text}".strip())
            append_section("Contents", "\n\n".join(content_sections))

        entities_qs = self.entities.all().order_by("name")
        if entities_qs.exists():
            entity_lines = []
            for entity in entities_qs:
                description = getattr(entity, "description", None) or ""
                line = entity.name
                if entity.disambiguation:
                    line = f"{line} ({entity.disambiguation})"
                if description:
                    line = f"{line}\n  Description: {description}"
                entity_lines.append(f"- {line}")
            append_section("Entities", "\n".join(entity_lines))

        documents_qs = self.documents.filter(is_deleted=False).order_by("created_at")
        if documents_qs.exists():
            document_lines = []
            for document in documents_qs:
                description = document.description or ""
                display_title = document.display_title
                line = f"- {display_title}: {document.url}"
                if description:
                    line = f"{line}\n  {description}"
                document_lines.append(line)
            append_section("Documents", "\n".join(document_lines))

        webpages_qs = self.webpages.filter(is_deleted=False).order_by("created_at")
        if webpages_qs.exists():
            webpage_lines = []
            for webpage in webpages_qs:
                description = webpage.description or ""
                title = webpage.title or webpage.url
                line = f"- {title}: {webpage.url}"
                if description:
                    line = f"{line}\n  {description}"
                webpage_lines.append(line)
            append_section("Webpages", "\n".join(webpage_lines))

        texts_qs = self.texts.filter(is_deleted=False).order_by("created_at")
        if texts_qs.exists():
            text_blocks = [text.content for text in texts_qs if text.content]
            append_section("Text Notes", "\n\n".join(text_blocks))

        recaps_qs = self.recaps.filter(is_deleted=False, status="finished").order_by("created_at")
        if recaps_qs.exists():
            recap_blocks = [recap.recap for recap in recaps_qs if recap.recap]
            append_section("Recaps", "\n\n".join(recap_blocks))

        images_qs = self.images.filter(is_deleted=False, status="finished").order_by("created_at")
        if images_qs.exists():
            image_lines = []
            for image in images_qs:
                image_name = getattr(image.image, "name", "") or ""
                thumbnail_name = getattr(image.thumbnail, "name", "") or ""
                line = f"- Image: {image_name}" if image_name else "- Image"
                if thumbnail_name:
                    line = f"{line}\n  Thumbnail: {thumbnail_name}"
                image_lines.append(line)
            append_section("Images", "\n".join(image_lines))

        tweets_qs = self.tweets.filter(is_deleted=False).order_by("created_at")
        if tweets_qs.exists():
            tweet_lines = []
            for tweet in tweets_qs:
                tweet_lines.append(f"- {tweet.url}\n  {tweet.html}")
            append_section("Tweets", "\n".join(tweet_lines))

        videos_qs = self.youtube_videos.filter(is_deleted=False, status="finished").order_by("created_at")
        if videos_qs.exists():
            video_lines = []
            for video in videos_qs:
                description = video.description or ""
                title = video.title or "Video"
                line = f"- {title}: {video.url or video.video_id}"
                if description:
                    line = f"{line}\n  {description}"
                video_lines.append(line)
            append_section("Videos", "\n".join(video_lines))

        data_qs = self.datas.filter(is_deleted=False).order_by("created_at")
        if data_qs.exists():
            data_sections = []
            for dataset in data_qs:
                name = dataset.name or "Dataset"
                explanation = dataset.explanation or ""
                try:
                    data_payload = json.dumps(dataset.data, indent=2, sort_keys=True)
                except TypeError:
                    data_payload = str(dataset.data)
                sources = dataset.sources or []
                sources_repr = ""
                if sources:
                    try:
                        sources_repr = json.dumps(sources, ensure_ascii=False)
                    except TypeError:
                        sources_repr = str(sources)
                section_lines = [f"### {name}", data_payload]
                if explanation:
                    section_lines.insert(1, explanation)
                if sources_repr:
                    section_lines.append(f"Sources: {sources_repr}")
                data_sections.append("\n\n".join(section_lines))
            append_section("Data", "\n\n".join(data_sections))

        insights_qs = self.data_insights.filter(is_deleted=False).order_by("created_at")
        if insights_qs.exists():
            insight_lines = []
            for insight in insights_qs:
                sources = insight.sources.all()
                source_names = [source.name or "Dataset" for source in sources]
                line = insight.insight
                if source_names:
                    line = f"{line}\n  Sources: {', '.join(source_names)}"
                insight_lines.append(f"- {line}")
            append_section("Data Insights", "\n".join(insight_lines))

        visualizations_qs = self.data_visualizations.filter(is_deleted=False).select_related("insight").order_by("created_at")
        if visualizations_qs.exists():
            visualization_sections = []
            for visualization in visualizations_qs:
                try:
                    chart_payload = json.dumps(visualization.chart_data, indent=2, sort_keys=True)
                except TypeError:
                    chart_payload = str(visualization.chart_data)
                title = visualization.chart_type.title() if visualization.chart_type else "Visualization"
                section_lines = [f"### {title}", chart_payload]
                if visualization.insight_id and visualization.insight:
                    section_lines.insert(1, f"Insight: {visualization.insight.insight}")
                visualization_sections.append("\n\n".join(section_lines))
            append_section("Data Visualizations", "\n\n".join(visualization_sections))

        return "".join(parts)

    def _context_has_substance(self, context: str) -> bool:
        """Return ``True`` when the provided context contains useful content."""

        if not context:
            return False

        stripped = context.strip()
        if not stripped:
            return False

        # ``build_context`` always prefixes a markdown heading. Strip heading
        # characters to detect whether any substantive text remains.
        return bool(stripped.strip("# \n\t"))

    def get_embedding(self, force: bool = False):
        """
        Return an embedding vector for the topic.
        If not forcing and we already have one, reuse it.
        """
        if not force and self.embedding is not None and len(self.embedding) > 0:
            return self.embedding

        context = self.build_context()
        if not self._context_has_substance(context):
            return None

        with OpenAI() as client:
            embedding = client.embeddings.create(
                input=context,
                model='text-embedding-3-small'
            ).data[0].embedding
        return embedding

    def get_similar_topics(self, limit=5):
        if self.embedding is None:
            return Topic.objects.none()
        return (
            Topic.objects
            .exclude(id=self.id)
            .exclude(embedding__isnull=True)
            .filter(status='published')
            .order_by(L2Distance('embedding', self.embedding))[:limit]
        )

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

        for link in self.topic_related_topics.filter(is_deleted=False):
            RelatedTopic.objects.create(
                topic=cloned,
                related_topic=link.related_topic,
                source=link.source,
                created_by=user,
            )

        return cloned


class RelatedTopic(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTO = "auto", "Automatic"

    topic = models.ForeignKey(
        "Topic",
        on_delete=models.CASCADE,
        related_name="topic_related_topics",
    )
    related_topic = models.ForeignKey(
        "Topic",
        on_delete=models.CASCADE,
        related_name="incoming_related_topic_links",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_topic_related_topics",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "related_topic"],
                name="unique_topic_related_topic",
            )
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.topic} → {self.related_topic}"


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
