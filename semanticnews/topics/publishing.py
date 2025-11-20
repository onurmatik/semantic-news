"""Utilities for publishing topics and capturing publication metadata."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from .models import (
    Source,
    RelatedTopic,
    Topic,
    TopicRecap,
    TopicSection,
    TopicTitle,
)


@dataclass
class TopicPublication:
    """Details captured when a topic is published."""

    topic: Topic
    published_at: datetime
    context_snapshot: Dict[str, Any] = field(default_factory=dict)


def _resolve_related_topic_source(choice: str, fallback: str) -> str:
    source_enum = getattr(RelatedTopic, "Source", None)
    if source_enum is not None and hasattr(source_enum, choice):
        return getattr(source_enum, choice)
    return fallback


def _snapshot_section(section: TopicSection) -> Dict[str, Any]:
    record = section.published_content or section.draft_content
    content_snapshot: Any = None
    metadata_snapshot: Dict[str, Any] | Any = {}

    if record is not None:
        payload = record.content
        if isinstance(payload, dict):
            content_snapshot = dict(payload)
        elif isinstance(payload, list):
            content_snapshot = [
                dict(item) if isinstance(item, dict) else item for item in payload
            ]
        else:
            content_snapshot = deepcopy(payload)

        metadata_payload = record.metadata or {}
        if isinstance(metadata_payload, dict):
            metadata_snapshot = dict(metadata_payload)
        else:
            metadata_snapshot = deepcopy(metadata_payload)

    return {
        "id": section.id,
        "widget_id": getattr(section, "widget_id", None),
        "widget_name": section.widget_name,
        "language_code": section.language_code,
        "display_order": section.display_order,
        "status": section.status,
        "content": content_snapshot,
        "metadata": metadata_snapshot,
    }


def _clear_topic_caches(topic: Topic) -> None:
    for attr in [
        "sections_ordered",
        "active_sections",
        "published_sections",
        "hero_image",
        "image",
        "thumbnail",
    ]:
        if hasattr(topic, attr):
            delattr(topic, attr)


def _publish_title(topic: Topic, published_at) -> None:
    try:
        title_record = (
            topic.titles.filter(published_at__isnull=True)
            .order_by("-created_at", "-id")
            .select_for_update()
            .first()
        )
    except TopicTitle.DoesNotExist:  # pragma: no cover - defensive
        title_record = None

    if not title_record:
        return

    title_record.published_at = published_at
    title_record.save(update_fields=["published_at"])


def _publish_recaps(topic: Topic, published_at) -> Optional[TopicRecap]:
    current_recap = (
        topic.recaps.filter(is_deleted=False, status="finished")
        .order_by("-created_at", "-id")
        .select_for_update()
        .first()
    )

    if not current_recap:
        return None

    updates = []
    if current_recap.published_at is None:
        current_recap.published_at = published_at
        updates.append("published_at")
    if updates:
        current_recap.save(update_fields=updates)

    draft_exists = (
        topic.recaps.filter(is_deleted=False, published_at__isnull=True)
        .exclude(pk=current_recap.pk)
        .exists()
    )

    if not draft_exists:
        TopicRecap.objects.create(
            topic=topic,
            recap=current_recap.recap,
            status=current_recap.status,
        )

    return current_recap


def _publish_sections(topic: Topic, published_at) -> List[TopicSection]:
    queryset = (
        topic.sections.filter(is_deleted=False)
        .select_related("draft_content", "published_content")
        .order_by("display_order", "id")
    )

    sections: List[TopicSection] = []
    for section in queryset:
        if section.status != "finished":
            continue

        snapshot = section.snapshot_content(published_at=published_at)
        updates: List[str] = ["published_content"]
        section.published_content = snapshot

        if getattr(section, "published_at", None) != published_at:
            section.published_at = published_at
            updates.append("published_at")

        section.save(update_fields=updates)
        sections.append(section)

    return sections


def _publish_related_topics(topic: Topic, user, published_at) -> None:
    field_names = {field.name for field in RelatedTopic._meta.get_fields()}
    published_field = "published_at" if "published_at" in field_names else None
    created_by_field = "created_by" if "created_by" in field_names else None

    manual_value = _resolve_related_topic_source("MANUAL", Source.USER)
    auto_value = _resolve_related_topic_source("AUTO", Source.AGENT)

    active_links = topic.topic_related_topics.filter(is_deleted=False)

    for link in active_links:
        updates: List[str] = []
        if published_field and getattr(link, published_field, None) is None:
            setattr(link, published_field, published_at)
            updates.append(published_field)
        if created_by_field and getattr(link, created_by_field, None) is None and user is not None:
            setattr(link, created_by_field, user)
            updates.append(created_by_field)
        if updates:
            link.save(update_fields=updates)

    manual_links = active_links
    if "source" in field_names:
        manual_links = manual_links.filter(source=manual_value)

    if manual_links.exists():
        return

    similar_topics = topic.get_similar_topics()
    for similar in similar_topics:
        if similar.pk == topic.pk:
            continue

        defaults = {}
        if "source" in field_names:
            defaults["source"] = auto_value
        if created_by_field and user is not None:
            defaults[created_by_field] = user
        if published_field:
            defaults[published_field] = published_at

        link, created = RelatedTopic.objects.get_or_create(
            topic=topic,
            related_topic=similar,
            defaults=defaults,
        )
        updates: List[str] = []
        if not created:
            if "is_deleted" in field_names and getattr(link, "is_deleted", False):
                link.is_deleted = False
                updates.append("is_deleted")
            if "source" in field_names and getattr(link, "source", None) != defaults.get("source"):
                link.source = defaults.get("source")
                updates.append("source")
            if created_by_field and user is not None and getattr(link, created_by_field, None) != user:
                setattr(link, created_by_field, user)
                updates.append(created_by_field)
            if published_field and getattr(link, published_field, None) is None:
                setattr(link, published_field, published_at)
                updates.append(published_field)
            if updates:
                link.save(update_fields=updates)


@transaction.atomic
def publish_topic(topic: Topic, user=None) -> TopicPublication:
    """Publish a topic and return the captured publication record."""

    published_at = timezone.now()

    embedding = topic.get_embedding(force=True)

    topic.status = "published"
    topic.last_published_at = published_at
    topic.embedding = embedding
    topic.save(update_fields=["status", "last_published_at", "embedding"])

    _publish_title(topic, published_at)
    published_recap = _publish_recaps(topic, published_at)
    sections = _publish_sections(topic, published_at)
    # _publish_related_topics(topic, user, published_at)

    _clear_topic_caches(topic)

    context_snapshot = {
        "topic_id": topic.id,
        "title": topic.title,
        "slug": topic.slug,
        "recap": getattr(published_recap, "recap", None),
        "sections": [_snapshot_section(section) for section in sections],
    }

    return TopicPublication(
        topic=topic,
        published_at=published_at,
        context_snapshot=context_snapshot,
    )
