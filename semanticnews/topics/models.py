from __future__ import annotations

import copy
import json
import uuid
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext, get_supported_language_variant
from django.urls import reverse
from django.conf import settings
from slugify import slugify
from semanticnews.openai import OpenAI, AsyncOpenAI
from pgvector.django import VectorField, L2Distance, HnswIndex
from semanticnews.topics.widgets import get_widget


class Source(models.TextChoices):
    USER = "user", "User"
    AGENT = "agent", "Agent"


class Topic(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    embedding = VectorField(dimensions=1536, blank=True, null=True)
    status = models.CharField(max_length=20, db_index=True, choices=(
        ('removed', 'Removed'),
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ), default='draft')
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
        'agenda.Event', through='RelatedEvent',
        related_name='topics', blank=True
    )
    entities = models.ManyToManyField(
        'entities.Entity', through='RelatedEntity',
        related_name='topics', blank=True
    )

    related_topics = models.ManyToManyField(
        'self',
        through='RelatedTopic',
        symmetrical=False,
        related_name='related_to_topics',
        blank=True,
    )

    def _get_draft_title_record(self):
        if not self.pk:
            return None

        return (
            self.titles.filter(published_at__isnull=True)
            .order_by("-created_at", "-id")
            .first()
        )

    def _get_published_title_record(self):
        if not self.pk:
            return None

        return (
            self.titles.filter(published_at__isnull=False)
            .order_by("-published_at", "-id")
            .first()
        )

    def _get_current_title_record(self):
        draft = self._get_draft_title_record()
        if draft:
            return draft

        return self._get_published_title_record()

    @property
    def title(self):
        if not self.pk:
            return getattr(self, "_pending_title_value", None)

        record = self._get_current_title_record()
        if record:
            return record.title

        return None

    @title.setter
    def title(self, value):
        normalized = (value or "").strip() or None

        if not self.pk:
            self._pending_title_value = normalized
            return

        self._apply_title_update(normalized)

    @property
    def title_draft(self):
        return self._get_draft_title_record()

    @property
    def slug(self):
        if not self.pk:
            return getattr(self, "_pending_slug_value", None)

        record = self._get_current_title_record()
        if record:
            return record.slug

        return None

    @slug.setter
    def slug(self, value):
        normalized = (value or "").strip() or None

        if not self.pk:
            self._pending_slug_value = normalized
            return

        self._apply_slug_update(normalized)

    def _apply_title_update(self, value: Optional[str]):
        record = self._get_current_title_record()

        if value is None:
            if record:
                record.delete()
            return

        slug_value = slugify(value) or None

        if record:
            updates = []
            if record.title != value:
                record.title = value
                updates.append("title")
            if record.slug != slug_value:
                record.slug = slug_value
                updates.append("slug")
            if updates:
                record.save(update_fields=updates)
        else:
            self.titles.create(title=value, slug=slug_value)

    def _apply_slug_update(self, value: Optional[str]) -> bool:
        record = self._get_current_title_record()

        if not record:
            if value is None:
                return True

            # No title exists yet – defer applying the slug until one is set.
            self._pending_slug_value = value
            return False

        if record.slug != value:
            record.slug = value
            record.save(update_fields=["slug"])

        return True

    def save(self, *args, **kwargs):
        title_sentinel = object()
        slug_sentinel = object()
        pending_title = getattr(self, "_pending_title_value", title_sentinel)
        pending_slug = getattr(self, "_pending_slug_value", slug_sentinel)

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            cleaned = [field for field in update_fields if field not in {"title", "slug"}]
            if cleaned:
                kwargs["update_fields"] = cleaned
            else:
                kwargs.pop("update_fields")

        super().save(*args, **kwargs)

        if pending_title is not title_sentinel:
            self._apply_title_update(pending_title)
            if hasattr(self, "_pending_title_value"):
                delattr(self, "_pending_title_value")

        if pending_slug is not slug_sentinel:
            if self._apply_slug_update(pending_slug) and hasattr(self, "_pending_slug_value"):
                delattr(self, "_pending_slug_value")

    def __str__(self):
        return f"{self.title or 'Topic'}"

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
        return self.events.filter(relatedevent__is_deleted=False)

    @property
    def active_recaps(self):
        return self.recaps.filter(is_deleted=False)

    @property
    def published_recaps(self):
        return self.recaps.filter(is_deleted=False, published_at__isnull=False)

    @cached_property
    def sections_ordered(self):
        """Return an ordered list of all sections attached to the topic."""

        cache = getattr(self, "_prefetched_objects_cache", {})
        prefetched = cache.get("sections")
        if prefetched is not None:
            return list(prefetched)

        return list(
            self.sections.select_related("draft_content", "published_content")
        )

    @cached_property
    def active_sections(self):
        """Return an ordered list of published, non-deleted sections."""

        return [
            s for s in self.sections_ordered
            if not s.is_deleted and s.published_at is not None
        ]

    @cached_property
    def published_sections(self):
        """Return published sections with their frozen content and metadata."""

        published: list["TopicSection"] = []
        for section in self.sections_ordered:
            if section.is_deleted or section.published_at is None:
                continue

            snapshot = section.published_content or section.draft_content
            if snapshot is None:
                continue

            clone = copy.copy(section)
            clone._apply_content_override(snapshot)
            published.append(clone)

        return published

    @property
    def active_related_entities(self):
        return self.related_entities.filter(is_deleted=False)

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
        """Return whether the topic can be published again."""

        return self.status in {"draft", "published"}

    @cached_property
    def hero_image(self):
        # FIXME: Return the first section with a widget type IMAGE
        return

    @cached_property
    def image(self):
        hero = self.hero_image
        return hero.image if hero else None

    @cached_property
    def thumbnail(self):
        hero = self.hero_image
        return hero.thumbnail if hero else None

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

        # Events
        events_qs = self.events.filter(relatedevent__is_deleted=False).order_by("date")
        if events_qs.exists():
            event_lines = [f"- {event.title} ({event.date})" for event in events_qs]
            append_section("Events", "\n".join(event_lines))

        # Entities
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

        # Documents
        documents_rel = getattr(self, "documents", None)
        if documents_rel is not None:
            documents_qs = documents_rel.filter(is_deleted=False).order_by("created_at")
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

        # Webpages
        webpages_rel = getattr(self, "webpages", None)
        if webpages_rel is not None:
            webpages_qs = webpages_rel.filter(is_deleted=False).order_by("created_at")
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

        # Text notes
        texts_rel = getattr(self, "texts", None)
        if texts_rel is not None:
            texts_qs = texts_rel.filter(is_deleted=False).order_by("created_at")
            if texts_qs.exists():
                text_blocks = [text.content for text in texts_qs if text.content]
                append_section("Text Notes", "\n\n".join(text_blocks))

        # Recaps
        recaps_qs = self.recaps.filter(is_deleted=False, status="finished").order_by(
            "created_at"
        )
        if recaps_qs.exists():
            recap_blocks = [recap.recap for recap in recaps_qs if recap.recap]
            append_section("Recaps", "\n\n".join(recap_blocks))

        # Images
        images_rel = getattr(self, "images", None)
        if images_rel is not None:
            images_qs = images_rel.filter(is_deleted=False, status="finished").order_by(
                "created_at"
            )
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

        # Tweets
        tweets_rel = getattr(self, "tweets", None)
        if tweets_rel is not None:
            tweets_qs = tweets_rel.filter(is_deleted=False).order_by("created_at")
            if tweets_qs.exists():
                tweet_lines = []
                for tweet in tweets_qs:
                    tweet_lines.append(f"- {tweet.url}\n  {tweet.html}")
                append_section("Tweets", "\n".join(tweet_lines))

        # YouTube videos
        videos_rel = getattr(self, "youtube_videos", None)
        if videos_rel is not None:
            videos_qs = videos_rel.filter(is_deleted=False, status="finished").order_by(
                "created_at"
            )
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

        # Data
        datas_rel = getattr(self, "datas", None)
        if datas_rel is not None:
            data_qs = datas_rel.filter(is_deleted=False).order_by("created_at")
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

        # Data insights
        insights_rel = getattr(self, "data_insights", None)
        if insights_rel is not None:
            insights_qs = insights_rel.filter(is_deleted=False).order_by("created_at")
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

        # Data visualizations
        visualizations_rel = getattr(self, "data_visualizations", None)
        if visualizations_rel is not None:
            visualizations_qs = visualizations_rel.filter(is_deleted=False).select_related(
                "insight"
            ).order_by("created_at")
            if visualizations_qs.exists():
                visualization_sections = []
                for visualization in visualizations_qs:
                    try:
                        chart_payload = json.dumps(
                            visualization.chart_data, indent=2, sort_keys=True
                        )
                    except TypeError:
                        chart_payload = str(visualization.chart_data)
                    title = (
                        visualization.chart_type.title()
                        if visualization.chart_type
                        else "Visualization"
                    )
                    section_lines = [f"### {title}", chart_payload]
                    if visualization.insight_id and visualization.insight:
                        section_lines.insert(
                            1, f"Insight: {visualization.insight.insight}"
                        )
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

        for relation in RelatedEvent.objects.filter(topic=self, is_deleted=False):
            RelatedEvent.objects.create(
                topic=cloned,
                event=relation.event,
                source=relation.source,
            )

        for recap in self.recaps.filter(is_deleted=False):
            TopicRecap.objects.create(
                topic=cloned, recap=recap.recap, status="finished"
            )

        for relation in self.related_entities.filter(is_deleted=False):
            RelatedEntity.objects.create(
                topic=cloned,
                entity=relation.entity,
                role=relation.role,
                source=relation.source,
            )

        for link in self.topic_related_topics.filter(is_deleted=False):
            RelatedTopic.objects.create(
                topic=cloned,
                related_topic=link.related_topic,
                source=link.source,
                created_by=user,
            )

        return cloned


#
# Topic content required for publishing: Title, recap
#

class TopicTitle(models.Model):
    topic = models.ForeignKey(Topic, related_name='titles', on_delete=models.CASCADE)

    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=500, blank=True, null=True)

    slug = models.SlugField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['slug', 'topic'], name='unique_topic_title_slug')
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.title and not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class TopicRecap(models.Model):
    topic = models.ForeignKey(Topic, related_name="recaps", on_delete=models.CASCADE)

    recap = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)

    is_deleted = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ("in_progress", "In progress"),
            ("finished", "Finished"),
            ("error", "Error"),
        ],
        default="in_progress",
    )
    error_message = models.TextField(blank=True, null=True)
    error_code = models.CharField(blank=True, null=True, max_length=20)

    def __str__(self):
        return f"Recap for {self.topic}"


#
# Topic widget content sections
#

class TopicSectionQuerySet(models.QuerySet):
    """Query helpers for topic sections."""

    def active(self):
        """Return sections that have not been soft deleted."""

        return self.filter(is_deleted=False)

    def published(self):
        """Return sections that have been published."""

        return self.active().filter(published_at__isnull=False)

    def in_language(self, language_code: Optional[str]):
        """Filter sections by their language code (if provided)."""

        if not language_code:
            return self

        return self.filter(language_code=language_code)


class TopicSection(models.Model):
    topic = models.ForeignKey(Topic, related_name="sections", on_delete=models.CASCADE)
    widget_name = models.CharField(max_length=100, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    draft_content = models.ForeignKey(
        "TopicSectionContent",
        related_name="drafted_sections",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    published_content = models.ForeignKey(
        "TopicSectionContent",
        related_name="published_sections",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    published_at = models.DateTimeField(blank=True, null=True, db_index=True)
    is_deleted = models.BooleanField(default=False)
    language_code = models.CharField(max_length=12, blank=True, null=True, db_index=True)

    objects = TopicSectionQuerySet.as_manager()

    def _get_render_override(self) -> "TopicSectionContent" | None:
        return getattr(self, "_render_content_override", None)

    def _apply_content_override(self, record: "TopicSectionContent") -> None:
        self._render_content_override = record


    def _pending_draft_state(self) -> dict:
        """
        Return the in-memory draft state buffer for unsaved sections.
        """
        return getattr(self, "_pending_draft_state_data", {}) or {}

    def _queue_pending_draft_update(self, field: str, value) -> None:
        """
        Queue a change to be applied to the draft content once the section is saved.
        """
        state = getattr(self, "_pending_draft_state_data", None)
        if state is None:
            state = {}
            self._pending_draft_state_data = state
        state[field] = value

    def _get_effective_record(self) -> "TopicSectionContent" | None:
        override = self._get_render_override()
        if override is not None:
            return override
        return self.draft_content

    def _get_or_create_draft_record(self) -> "TopicSectionContent":
        record = self.draft_content
        if record is not None:
            return record

        if not self.pk:
            raise ValueError("TopicSection must be saved before setting content")

        record = TopicSectionContent.objects.create(
            section=self,
            stage=TopicSectionContent.Stage.DRAFT,
        )
        TopicSection.objects.filter(pk=self.pk).update(draft_content=record)
        self.draft_content = record
        return record

    def _update_draft_record(self, **fields) -> None:
        if not fields:
            return

        record = self._get_or_create_draft_record()
        updates: list[str] = []
        for attr, value in fields.items():
            if attr not in {"content", "metadata", "execution_state"}:
                continue
            if attr in {"metadata", "execution_state"} and value is None:
                value = {}
            if attr in {"metadata", "execution_state"}:
                payload = copy.deepcopy(value)
                setattr(record, attr, payload)
                if attr not in updates:
                    updates.append(attr)
                continue

            if getattr(record, attr) != value:
                setattr(record, attr, value)
                updates.append(attr)

        if updates:
            record.save(update_fields=updates)

    def _apply_pending_draft_updates(self) -> None:
        state = getattr(self, "_pending_draft_state_data", None)
        if not state or not self.pk:
            return

        self._update_draft_record(**state)
        delattr(self, "_pending_draft_state_data")

    def save(self, *args, **kwargs):  # pragma: no cover - exercised via integration tests
        pending = getattr(self, "_pending_draft_state_data", None)
        super().save(*args, **kwargs)
        if pending:
            self._apply_pending_draft_updates()

    class Meta:
        ordering = ("display_order", "published_at", "id")

    def __str__(self) -> str:  # pragma: no cover - trivial
        widget_name = self.widget_name or "unknown"
        return f"{self.topic_id}:{widget_name}:{self.display_order}"

    # ---- properties that use the pending draft state ----

    @property
    def content(self):
        record = self._get_effective_record()
        if record is not None:
            return record.content
        return self._pending_draft_state().get("content")

    @content.setter
    def content(self, value):
        if self._get_render_override() is not None:
            raise AttributeError("Cannot modify published section content")
        if not self.pk:
            self._queue_pending_draft_update("content", value)
            return
        self._update_draft_record(content=value)

    @property
    def metadata(self) -> dict:
        record = self._get_effective_record()
        if record is not None and record.metadata is not None:
            return record.metadata
        pending = self._pending_draft_state().get("metadata")
        return pending or {}

    @metadata.setter
    def metadata(self, value):
        payload = value or {}
        if self._get_render_override() is not None:
            raise AttributeError("Cannot modify metadata on a published snapshot")
        if not self.pk:
            self._queue_pending_draft_update("metadata", payload)
            return
        self._update_draft_record(metadata=payload)

    @property
    def execution_state(self) -> dict:
        record = self._get_effective_record()
        if record is not None and record.execution_state is not None:
            return record.execution_state
        pending = self._pending_draft_state().get("execution_state")
        return pending or {}

    @execution_state.setter
    def execution_state(self, value):
        payload = value or {}
        if self._get_render_override() is not None:
            raise AttributeError("Cannot modify execution state on a published snapshot")
        if not self.pk:
            self._queue_pending_draft_update("execution_state", payload)
            return
        self._update_draft_record(execution_state=payload)

    @property
    def widget(self):
        """Retrieve the Widget instance from the code registry"""
        if not self.widget_name:
            raise LookupError("Topic section is missing a widget name")

        try:
            return get_widget(self.widget_name)
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise LookupError(
                f"Widget '{self.widget_name}' is not registered"
            ) from exc

    @property
    def status(self) -> str:
        """Return the execution status recorded for this section."""

        state = self.execution_state or {}
        status = state.get("status")
        if status:
            return str(status)
        if self.published_at:
            return "finished"
        return "pending"

    @status.setter
    def status(self, value: str) -> None:
        state = dict(self.execution_state or {})
        state["status"] = value
        self.execution_state = state

    @property
    def error_message(self) -> Optional[str]:
        state = self.execution_state or {}
        message = state.get("error_message")
        return str(message) if message is not None else None

    @error_message.setter
    def error_message(self, value: Optional[str]) -> None:
        state = dict(self.execution_state or {})
        state["error_message"] = value
        self.execution_state = state

    @property
    def error_code(self) -> Optional[str]:
        state = self.execution_state or {}
        code = state.get("error_code")
        return str(code) if code is not None else None

    @error_code.setter
    def error_code(self, value: Optional[str]) -> None:
        state = dict(self.execution_state or {})
        state["error_code"] = value
        self.execution_state = state

    def snapshot_content(self, *, published_at) -> "TopicSectionContent":
        draft = self._get_or_create_draft_record()
        snapshot = TopicSectionContent.objects.create(
            section=self,
            stage=TopicSectionContent.Stage.SNAPSHOT,
            content=copy.deepcopy(draft.content),
            metadata=copy.deepcopy(draft.metadata or {}),
            execution_state=copy.deepcopy(draft.execution_state or {}),
            published_at=published_at,
        )
        return snapshot

    def render(self):
        """Renders the content with the widget.template"""
        from django.template import Template, Context

        widget = self.widget
        template = Template(widget.template)
        context = Context({
            'content': self.content,
            'section': self,
            'widget': widget,
        })
        return template.render(context)


#
# Section content snapshots
#

class TopicSectionContent(models.Model):
    class Stage(models.TextChoices):
        DRAFT = "draft", "Draft"
        SNAPSHOT = "snapshot", "Snapshot"

    section = models.ForeignKey(
        TopicSection,
        related_name="content_entries",
        on_delete=models.CASCADE,
    )
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.DRAFT)
    content = models.JSONField(blank=True, null=True)
    metadata = models.JSONField(blank=True, default=dict)
    execution_state = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):  # pragma: no cover - debugging helper
        return f"SectionContent<{self.stage}>:{self.section_id}:{self.uuid}"


#
# Linked content models
#

class RelatedEvent(models.Model):
    event = models.ForeignKey('agenda.Event', on_delete=models.CASCADE)

    topic = models.ForeignKey(
        "Topic",
        on_delete=models.CASCADE,
        related_name="related_event_links",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.USER,
    )
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "event"],
                name="unique_topic_related_event",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f'{self.topic} - {self.event}'


class RelatedTopic(models.Model):
    related_topic = models.ForeignKey(
        "Topic",
        on_delete=models.CASCADE,
        related_name="incoming_related_topic_links",
    )

    topic = models.ForeignKey(
        "Topic",
        on_delete=models.CASCADE,
        related_name="topic_related_topics",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.USER,
    )
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "related_topic"],
                name="unique_topic_related_topic",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.topic} → {self.related_topic}"


class RelatedEntity(models.Model):
    entity = models.ForeignKey('entities.Entity', on_delete=models.CASCADE)
    role = models.CharField(max_length=100, blank=True, null=True)

    topic = models.ForeignKey(
        "Topic",
        on_delete=models.CASCADE,
        related_name="related_entities",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.USER,
    )
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def entity_name(self) -> str:
        return getattr(self.entity, "name", "")

    @property
    def entity_disambiguation(self) -> Optional[str]:
        return getattr(self.entity, "disambiguation", None)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "entity"],
                condition=Q(is_deleted=False),
                name="unique_topic_related_entity",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f'{self.topic} - {self.entity}'
