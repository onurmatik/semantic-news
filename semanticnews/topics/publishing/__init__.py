"""Simplified publishing workflow for topics."""

from __future__ import annotations

from typing import Optional

from django.db import transaction
from django.utils import timezone

from semanticnews.widgets.recaps.models import TopicRecap
from ..models import RelatedTopic, Topic


def _resolve_creator(topic: Topic, user) -> Optional[object]:
    if getattr(user, "is_authenticated", False):
        return user
    return topic.created_by


def _seed_related_topics(topic: Topic, user) -> None:
    if topic.last_published_at is not None:
        return

    manual_links_exist = topic.topic_related_topics.filter(
        is_deleted=False,
        source=RelatedTopic.Source.MANUAL,
    ).exists()

    if manual_links_exist:
        return

    creator = _resolve_creator(topic, user)
    seeded = 0
    for similar in topic.get_similar_topics(limit=2):
        link, created = RelatedTopic.objects.get_or_create(
            topic=topic,
            related_topic=similar,
            defaults={
                "source": RelatedTopic.Source.AUTO,
                "created_by": creator,
            },
        )

        if created:
            if link.is_deleted:
                link.is_deleted = False
                link.save(update_fields=["is_deleted"])
        else:
            update_fields = []
            if link.is_deleted:
                link.is_deleted = False
                update_fields.append("is_deleted")
            if link.source != RelatedTopic.Source.AUTO:
                link.source = RelatedTopic.Source.AUTO
                update_fields.append("source")
            if creator and link.created_by_id != getattr(creator, "id", None):
                link.created_by = creator
                update_fields.append("created_by")
            if update_fields:
                link.save(update_fields=update_fields)

        if not link.is_deleted:
            seeded += 1
        if seeded >= 2:
            break


def _update_recap_state(topic: Topic, timestamp) -> None:
    current_recap = (
        topic.recaps.filter(is_deleted=False)
        .order_by("-created_at")
        .first()
    )

    if current_recap is None:
        return

    update_fields = []
    if current_recap.status != "finished":
        current_recap.status = "finished"
        update_fields.append("status")
    if current_recap.published_at != timestamp:
        current_recap.published_at = timestamp
        update_fields.append("published_at")
    if current_recap.error_message:
        current_recap.error_message = None
        update_fields.append("error_message")
    if current_recap.error_code:
        current_recap.error_code = None
        update_fields.append("error_code")

    if update_fields:
        current_recap.save(update_fields=update_fields)

    has_unpublished = (
        topic.recaps.filter(is_deleted=False, published_at__isnull=True)
        .exclude(pk=current_recap.pk)
        .exists()
    )
    if not has_unpublished:
        TopicRecap.objects.create(
            topic=topic,
            recap=current_recap.recap,
            status="finished",
        )


def _mark_related_content_published(topic: Topic, timestamp) -> None:
    topic.texts.filter(is_deleted=False).update(published_at=timestamp)
    topic.documents.filter(is_deleted=False).update(published_at=timestamp)
    topic.webpages.filter(is_deleted=False).update(published_at=timestamp)
    topic.datas.filter(is_deleted=False).update(published_at=timestamp)
    topic.data_insights.filter(is_deleted=False).update(published_at=timestamp)
    topic.data_visualizations.filter(is_deleted=False).update(published_at=timestamp)
    topic.images.filter(is_deleted=False).update(published_at=timestamp)
    topic.tweets.filter(is_deleted=False).update(published_at=timestamp)
    topic.youtube_videos.filter(is_deleted=False).update(published_at=timestamp)
    RelatedTopic.objects.filter(topic=topic, is_deleted=False).update(
        published_at=timestamp
    )


@transaction.atomic
def publish_topic(topic: Topic, user) -> Topic:
    """Mark a topic as published and update associated content."""

    _seed_related_topics(topic, user)

    now = timezone.now()
    topic.status = "published"
    topic.last_published_at = now
    topic.save(update_fields=["status", "last_published_at"])

    _update_recap_state(topic, now)
    _mark_related_content_published(topic, now)

    return topic