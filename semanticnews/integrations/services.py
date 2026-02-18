from __future__ import annotations

from dataclasses import dataclass

from semanticnews.topics.models import Topic

from .models import ExternalTopicConnection
from .newsradar import NewsRadarClient


@dataclass
class ExternalConnectionResult:
    connection: ExternalTopicConnection
    created: bool


def connect_topic_to_newsradar(*, topic: Topic, query: str | None = None) -> ExternalConnectionResult:
    """Create or return a NewsRadar topic mapped to the provided semantic topic."""

    existing = ExternalTopicConnection.objects.filter(
        topic=topic,
        provider=ExternalTopicConnection.PROVIDER_NEWSRADAR,
    ).first()
    if existing is not None:
        return ExternalConnectionResult(connection=existing, created=False)

    normalized_query = (query or "").strip() or (topic.title or "").strip() or str(topic.uuid)
    normalized_title = (topic.title or "").strip() or f"Topic {topic.uuid}"

    client = NewsRadarClient()
    remote = client.create_topic(title=normalized_title, query=normalized_query)

    connection = ExternalTopicConnection.objects.create(
        provider=ExternalTopicConnection.PROVIDER_NEWSRADAR,
        topic=topic,
        external_topic_id=remote.topic_id,
        display_name=remote.title,
        query=remote.query,
        metadata=remote.raw,
    )
    return ExternalConnectionResult(connection=connection, created=True)
