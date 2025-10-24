from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import json
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple
from types import SimpleNamespace

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from ...agenda.models import Event

from ..layouts import (
    MODULE_REGISTRY,
    annotate_module_content,
    get_layout_for_mode,
    _split_module_key,
)
from ..models import Topic, TopicModuleLayout, RelatedTopic
from semanticnews.widgets.data.models import TopicData, TopicDataInsight, TopicDataVisualization
from semanticnews.widgets.documents.models import TopicDocument, TopicWebpage
from semanticnews.widgets.embeds.models import TopicTweet, TopicYoutubeVideo
from semanticnews.widgets.images.models import TopicImage
from semanticnews.widgets.recaps.models import TopicRecap
from semanticnews.widgets.relations.models import TopicEntityRelation
from semanticnews.widgets.text.models import TopicText
from semanticnews.widgets.timeline.models import TopicEvent
from .models import TopicPublication, TopicPublicationModule, TopicPublicationSnapshot


@dataclass
class SerializableImage:
    image_url: Optional[str]
    thumbnail_url: Optional[str]
    created_at: Optional[str]


@dataclass
class SerializableText:
    id: int
    content: str
    status: str
    created_at: str
    updated_at: str


@dataclass
class SerializableRecap:
    id: int
    recap: str
    status: str
    created_at: str


@dataclass
class SerializableRelation:
    id: int
    relations: List[dict]
    status: str
    created_at: str


@dataclass
class SerializableRelatedTopic:
    id: int
    topic_uuid: str
    title: Optional[str]
    slug: Optional[str]
    username: Optional[str]
    display_name: Optional[str]
    source: str
    is_deleted: bool
    created_at: str
    published_at: Optional[str]


@dataclass
class SerializableDocument:
    id: int
    title: str
    url: str
    description: str
    document_type: str
    created_at: str


@dataclass
class SerializableWebpage:
    id: int
    title: str
    url: str
    description: str
    created_at: str


@dataclass
class SerializableData:
    id: int
    name: Optional[str]
    data: Any
    sources: List[Any]
    explanation: Optional[str]
    created_at: str


@dataclass
class SerializableDataInsight:
    id: int
    insight: str
    source_ids: List[int]
    created_at: str


@dataclass
class SerializableDataVisualization:
    id: int
    chart_type: str
    chart_data: Any
    insight_id: Optional[int]
    created_at: str


@dataclass
class SerializableYoutubeVideo:
    id: int
    url: Optional[str]
    video_id: str
    title: str
    description: str
    thumbnail: Optional[str]
    video_published_at: Optional[str]


@dataclass
class SerializableTweet:
    id: int
    tweet_id: str
    url: str
    html: str
    created_at: str


@dataclass
class SnapshotRecord:
    payload: Dict[str, Any]
    content_object: Optional[Any] = None
    module_key: str = ""


@dataclass
class LiveTopicContent:
    """Container for the draft-side content that will be snapshotted."""

    hero_image: Optional[TopicImage]
    images: List[TopicImage]
    texts: List[TopicText]
    latest_recap: Optional[TopicRecap]
    recaps: List[TopicRecap]
    latest_relation: Optional[TopicEntityRelation]
    related_topic_links: List[RelatedTopic]
    latest_data: Optional[TopicData]
    datas: List[TopicData]
    data_insights: List[TopicDataInsight]
    data_visualizations: List[TopicDataVisualization]
    youtube_video: Optional[TopicYoutubeVideo]
    tweets: List[TopicTweet]
    documents: List[TopicDocument]
    webpages: List[TopicWebpage]
    events: List[TopicEvent]


SnapshotSerializer = Callable[[Topic, LiveTopicContent], Iterable[SnapshotRecord]]

SNAPSHOT_SERIALIZER_REGISTRY: Dict[str, SnapshotSerializer] = {}


def register_snapshot_serializer(component_type: str) -> Callable[[SnapshotSerializer], SnapshotSerializer]:
    """Decorator used by utility apps to register snapshot serializers."""

    def decorator(func: SnapshotSerializer) -> SnapshotSerializer:
        SNAPSHOT_SERIALIZER_REGISTRY[component_type] = func
        return func

    return decorator


def _serialize_dt(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.isoformat()


def _serialize_image(image: Optional[TopicImage]) -> Optional[SerializableImage]:
    if not image:
        return None
    image_url = getattr(getattr(image, "image", None), "url", None)
    thumbnail_url = getattr(getattr(image, "thumbnail", None), "url", None)
    return SerializableImage(
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        created_at=_serialize_dt(image.created_at),
    )


def _serialize_texts(texts: Iterable[TopicText]) -> List[SerializableText]:
    output: List[SerializableText] = []
    for text in texts:
        output.append(
            SerializableText(
                id=text.id,
                content=text.content,
                status=text.status,
                created_at=_serialize_dt(text.created_at) or "",
                updated_at=_serialize_dt(text.updated_at) or "",
            )
        )
    return output


def _serialize_recap(recap: Optional[TopicRecap]) -> Optional[SerializableRecap]:
    if not recap:
        return None
    return SerializableRecap(
        id=recap.id,
        recap=recap.recap,
        status=recap.status,
        created_at=_serialize_dt(recap.created_at) or "",
    )


def _serialize_relation(
    relation: Optional[TopicEntityRelation],
) -> Optional[SerializableRelation]:
    if not relation:
        return None
    return SerializableRelation(
        id=relation.id,
        relations=relation.relations,
        status=relation.status,
        created_at=_serialize_dt(relation.created_at) or "",
    )


def _serialize_related_topics(
    links: Iterable[RelatedTopic],
) -> List[SerializableRelatedTopic]:
    output: List[SerializableRelatedTopic] = []
    for link in links:
        related_topic = link.related_topic
        created_by = getattr(related_topic, "created_by", None)
        username = getattr(created_by, "username", None)
        display_name = None
        if created_by is not None:
            if hasattr(created_by, "get_full_name"):
                display_name = created_by.get_full_name() or None
            if not display_name:
                display_name = str(created_by)
        output.append(
            SerializableRelatedTopic(
                id=link.id,
                topic_uuid=str(getattr(related_topic, "uuid", "")),
                title=getattr(related_topic, "title", None),
                slug=getattr(related_topic, "slug", None),
                username=username,
                display_name=display_name,
                source=link.source,
                is_deleted=link.is_deleted,
                created_at=_serialize_dt(link.created_at) or "",
                published_at=_serialize_dt(link.published_at),
            )
        )
    return output


def _serialize_documents(docs: Iterable[TopicDocument]) -> List[SerializableDocument]:
    output: List[SerializableDocument] = []
    for doc in docs:
        output.append(
            SerializableDocument(
                id=doc.id,
                title=doc.title,
                url=doc.url,
                description=doc.description,
                document_type=doc.document_type,
                created_at=_serialize_dt(doc.created_at) or "",
            )
        )
    return output


def _serialize_webpages(pages: Iterable[TopicWebpage]) -> List[SerializableWebpage]:
    output: List[SerializableWebpage] = []
    for page in pages:
        output.append(
            SerializableWebpage(
                id=page.id,
                title=page.title,
                url=page.url,
                description=page.description,
                created_at=_serialize_dt(page.created_at) or "",
            )
        )
    return output


def _serialize_data(datas: Iterable[TopicData]) -> List[SerializableData]:
    output: List[SerializableData] = []
    for data in datas:
        output.append(
            SerializableData(
                id=data.id,
                name=data.name,
                data=data.data,
                sources=data.sources,
                explanation=data.explanation,
                created_at=_serialize_dt(data.created_at) or "",
            )
        )
    return output


def _serialize_data_insights(
    insights: Iterable[TopicDataInsight],
) -> List[SerializableDataInsight]:
    output: List[SerializableDataInsight] = []
    for insight in insights:
        output.append(
            SerializableDataInsight(
                id=insight.id,
                insight=insight.insight,
                source_ids=[source.id for source in insight.sources.all()],
                created_at=_serialize_dt(insight.created_at) or "",
            )
        )
    return output


def _serialize_data_visualizations(
    visualizations: Iterable[TopicDataVisualization],
) -> List[SerializableDataVisualization]:
    output: List[SerializableDataVisualization] = []
    for viz in visualizations:
        output.append(
            SerializableDataVisualization(
                id=viz.id,
                chart_type=viz.chart_type,
                chart_data=viz.chart_data,
                insight_id=viz.insight_id,
                created_at=_serialize_dt(viz.created_at) or "",
            )
        )
    return output


def _serialize_youtube_video(
    video: Optional[TopicYoutubeVideo],
) -> Optional[SerializableYoutubeVideo]:
    if not video:
        return None
    return SerializableYoutubeVideo(
        id=video.id,
        url=video.url,
        video_id=video.video_id,
        title=video.title,
        description=video.description,
        thumbnail=video.thumbnail,
        video_published_at=_serialize_dt(video.video_published_at),
    )


def _serialize_tweets(tweets: Iterable[TopicTweet]) -> List[SerializableTweet]:
    output: List[SerializableTweet] = []
    for tweet in tweets:
        output.append(
            SerializableTweet(
                id=tweet.id,
                tweet_id=tweet.tweet_id,
                url=tweet.url,
                html=tweet.html,
                created_at=_serialize_dt(tweet.created_at) or "",
            )
        )
    return output


def _payload_with_original_id(
    payload: Dict[str, Any], original_id: Optional[int]
) -> Dict[str, Any]:
    data = dict(payload)
    if original_id is not None:
        data.setdefault("id", original_id)
        data.setdefault("original_id", original_id)
    return data


def _payload_from_snapshot(snapshot: TopicPublicationSnapshot) -> Dict[str, Any]:
    payload = _payload_with_original_id(dict(snapshot.payload or {}), snapshot.object_id)
    payload["snapshot_id"] = snapshot.id
    return payload


@register_snapshot_serializer("image")
def _snapshot_images(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    for image in content.images:
        serialized = _serialize_image(image)
        if not serialized:
            continue
        payload = _payload_with_original_id(asdict(serialized), image.id)
        payload["is_hero"] = bool(getattr(image, "is_hero", False))
        records.append(SnapshotRecord(payload=payload, content_object=image))
    return records


@register_snapshot_serializer("text")
def _snapshot_texts(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    serialized_texts = _serialize_texts(content.texts)
    for text_obj, serialized in zip(content.texts, serialized_texts):
        payload = _payload_with_original_id(asdict(serialized), text_obj.id)
        records.append(SnapshotRecord(payload=payload, content_object=text_obj))
    return records


@register_snapshot_serializer("recap")
def _snapshot_recaps(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    for recap_obj in content.recaps:
        serialized = _serialize_recap(recap_obj)
        if not serialized:
            continue
        payload = _payload_with_original_id(asdict(serialized), recap_obj.id)
        records.append(SnapshotRecord(payload=payload, content_object=recap_obj))
    return records


@register_snapshot_serializer("relation")
def _snapshot_relations(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    if not content.latest_relation:
        return []
    serialized = _serialize_relation(content.latest_relation)
    if not serialized:
        return []
    payload = _payload_with_original_id(
        asdict(serialized), content.latest_relation.id
    )
    return [SnapshotRecord(payload=payload, content_object=content.latest_relation)]


@register_snapshot_serializer("related_topic")
def _snapshot_related_topics(
    topic: Topic, content: LiveTopicContent
) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    serialized_links = _serialize_related_topics(content.related_topic_links)
    for link_obj, serialized in zip(content.related_topic_links, serialized_links):
        payload = _payload_with_original_id(asdict(serialized), link_obj.id)
        records.append(SnapshotRecord(payload=payload, content_object=link_obj))
    return records


@register_snapshot_serializer("document")
def _snapshot_documents(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    serialized_docs = _serialize_documents(content.documents)
    for document_obj, serialized in zip(content.documents, serialized_docs):
        payload = _payload_with_original_id(asdict(serialized), document_obj.id)
        records.append(SnapshotRecord(payload=payload, content_object=document_obj))
    return records


@register_snapshot_serializer("webpage")
def _snapshot_webpages(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    serialized_pages = _serialize_webpages(content.webpages)
    for page_obj, serialized in zip(content.webpages, serialized_pages):
        payload = _payload_with_original_id(asdict(serialized), page_obj.id)
        records.append(SnapshotRecord(payload=payload, content_object=page_obj))
    return records


@register_snapshot_serializer("data")
def _snapshot_data(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    serialized_data = _serialize_data(content.datas)
    for data_obj, serialized in zip(content.datas, serialized_data):
        payload = _payload_with_original_id(asdict(serialized), data_obj.id)
        records.append(SnapshotRecord(payload=payload, content_object=data_obj))
    return records


@register_snapshot_serializer("data_insight")
def _snapshot_data_insights(
    topic: Topic, content: LiveTopicContent
) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    serialized_insights = _serialize_data_insights(content.data_insights)
    for insight_obj, serialized in zip(content.data_insights, serialized_insights):
        payload = _payload_with_original_id(asdict(serialized), insight_obj.id)
        records.append(SnapshotRecord(payload=payload, content_object=insight_obj))
    return records


@register_snapshot_serializer("data_visualization")
def _snapshot_data_visualizations(
    topic: Topic, content: LiveTopicContent
) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    serialized_viz = _serialize_data_visualizations(content.data_visualizations)
    for viz_obj, serialized in zip(content.data_visualizations, serialized_viz):
        payload = _payload_with_original_id(asdict(serialized), viz_obj.id)
        payload.setdefault("insight_text", getattr(viz_obj.insight, "insight", ""))
        records.append(SnapshotRecord(payload=payload, content_object=viz_obj))
    return records


@register_snapshot_serializer("tweet")
def _snapshot_tweets(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    serialized_tweets = _serialize_tweets(content.tweets)
    for tweet_obj, serialized in zip(content.tweets, serialized_tweets):
        payload = _payload_with_original_id(asdict(serialized), tweet_obj.id)
        records.append(SnapshotRecord(payload=payload, content_object=tweet_obj))
    return records


@register_snapshot_serializer("youtube_video")
def _snapshot_youtube_videos(
    topic: Topic, content: LiveTopicContent
) -> Iterable[SnapshotRecord]:
    if not content.youtube_video:
        return []
    serialized = _serialize_youtube_video(content.youtube_video)
    if not serialized:
        return []
    payload = _payload_with_original_id(asdict(serialized), content.youtube_video.id)
    return [SnapshotRecord(payload=payload, content_object=content.youtube_video)]


@register_snapshot_serializer("event")
def _snapshot_events(topic: Topic, content: LiveTopicContent) -> Iterable[SnapshotRecord]:
    records: List[SnapshotRecord] = []
    for event in content.events:
        payload = {
            "event_id": event.event_id,
            "role": event.role,
            "significance": event.significance,
            "created_at": _serialize_dt(event.created_at) or "",
        }
        payload = _payload_with_original_id(payload, event.id)
        records.append(SnapshotRecord(payload=payload, content_object=event))
    return records


def _module_payload(
    module: Dict[str, Any],
    snapshot_lookup: Dict[Tuple[str, Optional[int]], TopicPublicationSnapshot],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "base_module_key": module.get("base_module_key", module.get("module_key")),
        "module_identifier": module.get("module_identifier"),
        "context_keys": module.get("context_keys", []),
        "template_name": module.get("template_name"),
    }
    base_key = payload["base_module_key"]
    if base_key == "text" and module.get("text"):
        text_obj = module["text"]
        text_id = getattr(text_obj, "id", None)
        payload["text_id"] = text_id
        snapshot = snapshot_lookup.get(("text", text_id)) if text_id else None
        if snapshot:
            payload["snapshot_id"] = snapshot.id
            payload["text_snapshot_id"] = snapshot.id
    if base_key == "data":
        data_obj = module.get("data") or module.get("context_overrides", {}).get("data")
        if data_obj is not None:
            data_id = getattr(data_obj, "id", None)
            payload["data_id"] = data_id
            snapshot = snapshot_lookup.get(("data", data_id)) if data_id else None
            if snapshot:
                payload["snapshot_id"] = snapshot.id
                payload["data_snapshot_id"] = snapshot.id
        payload["show_data_insights"] = (
            module.get("context_overrides", {}).get("show_data_insights", False)
        )
    if base_key == "data_visualizations" and module.get("visualization"):
        viz_obj = module["visualization"]
        viz_id = getattr(viz_obj, "id", None)
        payload["visualization_id"] = viz_id
        snapshot = snapshot_lookup.get(("data_visualization", viz_id)) if viz_id else None
        if snapshot:
            payload["snapshot_id"] = snapshot.id
            payload["visualization_snapshot_id"] = snapshot.id
    return payload


def _collect_live_content(topic: Topic) -> LiveTopicContent:
    texts = list(
        topic.texts.filter(is_deleted=False, status="finished").order_by("created_at")
    )
    recaps_qs = topic.recaps.filter(status="finished", is_deleted=False).order_by(
        "-created_at"
    )
    recaps = list(recaps_qs)
    relations_qs = topic.entity_relations.filter(
        status="finished", is_deleted=False
    ).order_by("-created_at")
    datas_qs = topic.datas.filter(is_deleted=False).order_by("-created_at")
    data_insights_qs = (
        topic.data_insights.filter(is_deleted=False)
        .prefetch_related("sources")
        .order_by("-created_at")
    )
    data_visualizations_qs = (
        topic.data_visualizations.filter(is_deleted=False)
        .select_related("insight")
        .order_by("-created_at")
    )
    youtube_video = (
        topic.youtube_videos.filter(status="finished", is_deleted=False)
        .order_by("-created_at")
        .first()
    )
    tweets = list(topic.tweets.filter(is_deleted=False).order_by("-created_at"))
    documents = list(topic.documents.filter(is_deleted=False).order_by("-created_at"))
    webpages = list(topic.webpages.filter(is_deleted=False).order_by("-created_at"))
    images_qs = topic.images.filter(status="finished", is_deleted=False).order_by(
        "-is_hero", "-created_at"
    )
    images = list(images_qs)
    events = list(
        TopicEvent.objects.filter(topic=topic, is_deleted=False)
        .select_related("event")
        .order_by("-created_at")
    )
    related_topic_links = list(
        RelatedTopic.objects.filter(topic=topic, is_deleted=False)
        .select_related("related_topic__created_by")
        .order_by("-created_at")
    )

    latest_recap = recaps[0] if recaps else None

    return LiveTopicContent(
        hero_image=images[0] if images and images[0].is_hero else None,
        images=images,
        texts=texts,
        latest_recap=latest_recap,
        recaps=recaps,
        latest_relation=relations_qs.first(),
        related_topic_links=related_topic_links,
        latest_data=datas_qs.first(),
        datas=list(datas_qs),
        data_insights=list(data_insights_qs),
        data_visualizations=list(data_visualizations_qs),
        youtube_video=youtube_video,
        tweets=tweets,
        documents=documents,
        webpages=webpages,
        events=events,
    )


def _build_context_snapshot_from_snapshots(
    snapshots_by_type: Dict[str, List[TopicPublicationSnapshot]]
) -> Dict[str, Any]:
    def _payloads(component_type: str) -> List[Dict[str, Any]]:
        return [
            _payload_from_snapshot(snapshot)
            for snapshot in snapshots_by_type.get(component_type, [])
        ]

    image_payloads = _payloads("image")
    hero_image = next((img for img in image_payloads if img.get("is_hero")), None)
    if not hero_image and image_payloads:
        legacy_images = [img for img in image_payloads if "is_hero" not in img]
        if legacy_images:
            hero_image = legacy_images[0]

    texts = _payloads("text")
    recaps = _payloads("recap")
    relation_list = _payloads("relation")
    latest_relation = relation_list[0] if relation_list else None
    datas = _payloads("data")
    data_insights = _payloads("data_insight")
    data_visualizations = _payloads("data_visualization")
    youtube_videos = _payloads("youtube_video")
    tweets = _payloads("tweet")
    documents = _payloads("document")
    webpages = _payloads("webpage")
    events = _payloads("event")
    related_topics = _payloads("related_topic")

    relations_json = ""
    relations_json_pretty = ""
    if latest_relation:
        relations = latest_relation.get("relations") or []
        if relations:
            relations_json = json.dumps(relations, separators=(",", ":"))
            relations_json_pretty = json.dumps(relations, indent=2)

    related_event_ids = [
        payload.get("event_id")
        for payload in events
        if payload.get("event_id") is not None
    ]

    return {
        "image": hero_image,
        "images": image_payloads,
        "texts": texts,
        "latest_recap": recaps[0] if recaps else None,
        "recaps": recaps,
        "latest_relation": latest_relation,
        "relations_json": relations_json,
        "relations_json_pretty": relations_json_pretty,
        "latest_data": datas[0] if datas else None,
        "datas": datas,
        "data_insights": data_insights,
        "data_visualizations": data_visualizations,
        "youtube_video": youtube_videos[0] if youtube_videos else None,
        "tweets": tweets,
        "documents": documents,
        "webpages": webpages,
        "related_event_ids": related_event_ids,
        "events": events,
        "related_topic_links": related_topics,
    }


@transaction.atomic
def publish_topic(topic: Topic, user) -> TopicPublication:
    """Create a publication snapshot for ``topic`` and mark it as published."""

    publication = TopicPublication.objects.create(
        topic=topic,
        published_by=user,
    )

    if topic.last_published_at is None:
        manual_links_exist = topic.topic_related_topics.filter(
            is_deleted=False,
            source=RelatedTopic.Source.MANUAL,
        ).exists()
        if not manual_links_exist:
            seeded = 0
            creator = user if getattr(user, "is_authenticated", False) else topic.created_by
            for similar in topic.get_similar_topics(limit=2):
                link, created = RelatedTopic.objects.get_or_create(
                    topic=topic,
                    related_topic=similar,
                    defaults={
                        "source": RelatedTopic.Source.AUTO,
                        "created_by": creator,
                    },
                )
                if not created and link.is_deleted:
                    link.is_deleted = False
                    update_fields = ["is_deleted", "updated_at"]
                    if link.source != RelatedTopic.Source.AUTO:
                        link.source = RelatedTopic.Source.AUTO
                        update_fields.append("source")
                    if creator and link.created_by_id != getattr(creator, "id", None):
                        link.created_by = creator
                        update_fields.append("created_by")
                    link.save(update_fields=update_fields)
                if not link.is_deleted:
                    seeded += 1
                if seeded >= 2:
                    break

    content = _collect_live_content(topic)
    content_type_cache: Dict[type, ContentType] = {}
    snapshot_metadata: List[Tuple[str, Optional[int]]] = []
    snapshot_rows: List[TopicPublicationSnapshot] = []

    for component_type, serializer in SNAPSHOT_SERIALIZER_REGISTRY.items():
        for record in serializer(topic, content):
            payload = dict(record.payload)
            module_key = record.module_key or ""
            content_type_obj = None
            object_id: Optional[int] = None
            if record.content_object is not None:
                model_cls = record.content_object.__class__
                if model_cls not in content_type_cache:
                    content_type_cache[model_cls] = ContentType.objects.get_for_model(
                        model_cls, for_concrete_model=False
                    )
                content_type_obj = content_type_cache[model_cls]
                object_id = getattr(record.content_object, "pk", None)

            snapshot_rows.append(
                TopicPublicationSnapshot(
                    publication=publication,
                    component_type=component_type,
                    module_key=module_key,
                    content_type=content_type_obj,
                    object_id=object_id,
                    payload=payload,
                )
            )
            snapshot_metadata.append((component_type, object_id))

    created_snapshots: List[TopicPublicationSnapshot] = []
    if snapshot_rows:
        created_snapshots = TopicPublicationSnapshot.objects.bulk_create(snapshot_rows)

    snapshots_by_type: Dict[str, List[TopicPublicationSnapshot]] = defaultdict(list)
    snapshot_lookup: Dict[Tuple[str, Optional[int]], TopicPublicationSnapshot] = {}
    for snapshot, (component_type, object_id) in zip(created_snapshots, snapshot_metadata):
        snapshots_by_type[component_type].append(snapshot)
        if object_id is not None:
            snapshot_lookup[(component_type, object_id)] = snapshot

    context_snapshot = _build_context_snapshot_from_snapshots(snapshots_by_type)
    publication.context_snapshot = context_snapshot

    layout = get_layout_for_mode(topic, mode="detail")
    module_records: List[TopicPublicationModule] = []
    for placement, modules in layout.items():
        for module in modules:
            payload = _module_payload(module, snapshot_lookup)
            module_records.append(
                TopicPublicationModule(
                    publication=publication,
                    module_key=module["module_key"],
                    placement=placement,
                    display_order=module["display_order"],
                    payload=payload,
                )
            )
    if module_records:
        TopicPublicationModule.objects.bulk_create(module_records)

    layout_snapshot = {
        TopicModuleLayout.PLACEMENT_PRIMARY: [
            {
                "module_key": module.module_key,
                "display_order": module.display_order,
                "payload": module.payload,
            }
            for module in publication.modules.filter(
                placement=TopicModuleLayout.PLACEMENT_PRIMARY
            ).order_by("display_order", "id")
        ],
        TopicModuleLayout.PLACEMENT_SIDEBAR: [
            {
                "module_key": module.module_key,
                "display_order": module.display_order,
                "payload": module.payload,
            }
            for module in publication.modules.filter(
                placement=TopicModuleLayout.PLACEMENT_SIDEBAR
            ).order_by("display_order", "id")
        ],
    }
    publication.layout_snapshot = layout_snapshot
    publication.save(update_fields=["context_snapshot", "layout_snapshot"])

    now = timezone.now()
    topic.status = "published"
    topic.latest_publication = publication
    topic.last_published_at = now
    topic.save(update_fields=["status", "latest_publication", "last_published_at"])

    # Update publish metadata on utility models
    topic.texts.filter(is_deleted=False).update(published_at=now)
    topic.recaps.filter(is_deleted=False).update(published_at=now)
    topic.documents.filter(is_deleted=False).update(published_at=now)
    topic.webpages.filter(is_deleted=False).update(published_at=now)
    topic.datas.filter(is_deleted=False).update(published_at=now)
    topic.data_insights.filter(is_deleted=False).update(published_at=now)
    topic.data_visualizations.filter(is_deleted=False).update(published_at=now)
    topic.entity_relations.filter(is_deleted=False).update(published_at=now)
    topic.images.filter(is_deleted=False).update(published_at=now)
    topic.tweets.filter(is_deleted=False).update(published_at=now)
    topic.youtube_videos.filter(is_deleted=False).update(published_at=now)
    RelatedTopic.objects.filter(topic=topic, is_deleted=False).update(
        published_at=now
    )
    TopicEvent.objects.filter(topic=topic, is_deleted=False).update(published_at=now)

    # Remove older publications to avoid retaining orphaned snapshots
    topic.publications.exclude(id=publication.id).delete()

    return publication


def build_publication_context(topic: Topic, publication: TopicPublication) -> Dict[str, Any]:
    """Return a context dictionary usable by the detail template."""

    snapshot = publication.context_snapshot or {}

    def _ns(data: Optional[Dict[str, Any]]) -> Optional[SimpleNamespace]:
        if not data:
            return None
        return SimpleNamespace(**data)

    event_payloads = snapshot.get("events")
    if event_payloads is None:
        event_payloads = [
            _payload_from_snapshot(row)
            for row in publication.snapshots.filter(component_type="event")
        ]

    event_metadata = [SimpleNamespace(**payload) for payload in event_payloads]

    related_event_ids: List[int] = snapshot.get("related_event_ids", [])
    if not related_event_ids:
        related_event_ids = [
            getattr(meta, "event_id", None)
            for meta in event_metadata
            if getattr(meta, "event_id", None) is not None
        ]

    event_map = {
        event.id: event
        for event in Event.objects.filter(id__in=related_event_ids)
    }
    event_metadata_map = {
        getattr(meta, "event_id", None): meta
        for meta in event_metadata
        if getattr(meta, "event_id", None) is not None
    }

    class PublishedEventProxy:
        __slots__ = ("event", "_metadata")

        def __init__(self, event: Event, metadata: Optional[SimpleNamespace]):
            self.event = event
            self._metadata = metadata

        def __getattr__(self, item):
            return getattr(self.event, item)

        @property
        def role(self) -> Optional[str]:
            return getattr(self._metadata, "role", None)

        @property
        def significance(self) -> Optional[int]:
            meta_value = getattr(self._metadata, "significance", None)
            if meta_value is not None:
                return meta_value
            return getattr(self.event, "significance", None)

        @property
        def event_significance(self) -> Optional[int]:
            return getattr(self.event, "significance", None)

        @property
        def topic_event_id(self) -> Optional[int]:
            return getattr(self._metadata, "original_id", None)

        @property
        def topic_event_created_at(self) -> Optional[datetime]:
            value = getattr(self._metadata, "created_at", None)
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    return None
            return value

    related_events = [
        PublishedEventProxy(event_map[event_id], event_metadata_map.get(event_id))
        for event_id in related_event_ids
        if event_id in event_map
    ]

    related_topic_payloads = snapshot.get("related_topic_links")
    if related_topic_payloads is None:
        related_topic_payloads = [
            _payload_from_snapshot(row)
            for row in publication.snapshots.filter(component_type="related_topic")
        ]

    class PublishedRelatedTopicLink:
        __slots__ = (
            "id",
            "topic_uuid",
            "title",
            "slug",
            "username",
            "display_name",
            "source",
            "is_deleted",
            "created_at",
            "published_at",
            "_related_topic",
        )

        def __init__(self, payload: Dict[str, Any]):
            self.id = payload.get("id")
            self.topic_uuid = payload.get("topic_uuid")
            self.title = payload.get("title")
            self.slug = payload.get("slug")
            self.username = payload.get("username")
            self.display_name = payload.get("display_name")
            self.source = payload.get("source")
            self.is_deleted = payload.get("is_deleted", False)
            self.created_at = payload.get("created_at")
            self.published_at = payload.get("published_at")
            self._related_topic = None

        @property
        def related_topic(self) -> SimpleNamespace:
            if self._related_topic is None:
                created_by = SimpleNamespace(
                    username=self.username,
                    display_name=self.display_name,
                )
                self._related_topic = SimpleNamespace(
                    uuid=self.topic_uuid,
                    title=self.title,
                    slug=self.slug,
                    created_by=created_by,
                )
            return self._related_topic

    context: Dict[str, Any] = {
        "topic": topic,
        "related_events": related_events,
        "latest_recap": _ns(snapshot.get("latest_recap")),
        "latest_relation": _ns(snapshot.get("latest_relation")),
        "relations_json": snapshot.get("relations_json", ""),
        "relations_json_pretty": snapshot.get("relations_json_pretty", ""),
        "latest_data": _ns(snapshot.get("latest_data")),
        "datas": [_ns(data) for data in snapshot.get("datas", [])],
        "data_insights": [_ns(data) for data in snapshot.get("data_insights", [])],
        "data_visualizations": [
            _ns(data) for data in snapshot.get("data_visualizations", [])
        ],
        "youtube_video": _ns(snapshot.get("youtube_video")),
        "tweets": [_ns(tweet) for tweet in snapshot.get("tweets", [])],
        "documents": [_ns(doc) for doc in snapshot.get("documents", [])],
        "webpages": [_ns(page) for page in snapshot.get("webpages", [])],
        "texts": [_ns(text) for text in snapshot.get("texts", [])],
        "recaps": [_ns(recap) for recap in snapshot.get("recaps", [])],
        "images": [_ns(image) for image in snapshot.get("images", [])],
        "event_snapshots": event_metadata,
        "related_topic_links": [
            PublishedRelatedTopicLink(payload)
            for payload in related_topic_payloads
        ],
    }

    if not context["latest_recap"]:
        recaps = context.get("recaps", [])
        if recaps:
            context["latest_recap"] = recaps[0]

    image_data = snapshot.get("image")
    if image_data:
        image_url = image_data.get("image_url") or ""
        thumbnail_url = image_data.get("thumbnail_url") or ""

        # ``Topic.image`` normally returns the ``ImageFieldFile`` associated with
        # the latest ``TopicImage`` record. Downstream templates expect to access
        # ``topic.image.url`` (and, in edit mode, ``topic.image.image.url``), so
        # the publication proxy needs to mimic that interface. When only a
        # thumbnail exists we still want to surface it, but avoid rendering an
        # empty ``src`` attribute if neither URL is available.
        hero_display_url = image_url or thumbnail_url
        if hero_display_url:
            image_field = SimpleNamespace(url=image_url) if image_url else None
            thumbnail_field = (
                SimpleNamespace(url=thumbnail_url) if thumbnail_url else None
            )
            image_obj = SimpleNamespace(
                url=hero_display_url,
                image=image_field or thumbnail_field,
                thumbnail=thumbnail_field,
                created_at=image_data.get("created_at"),
            )

            class TopicProxy:
                def __init__(self, base: Topic, image, thumbnail):
                    self._base = base
                    self._image = image
                    self._thumbnail = thumbnail

                def __getattr__(self, item):
                    return getattr(self._base, item)

                @property
                def image(self):
                    return self._image

                @property
                def thumbnail(self):
                    return self._thumbnail

            context["topic"] = TopicProxy(topic, image_obj, thumbnail_field)
    return context


def build_publication_modules(
    publication: TopicPublication, context: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    """Return module descriptors recreated from a publication snapshot."""

    def _index_by(objects: List[Any], attr: str) -> Dict[str, Any]:
        mapping: Dict[str, Any] = {}
        for obj in objects:
            value = getattr(obj, attr, None)
            if value is not None:
                mapping[str(value)] = obj
        return mapping

    texts = context.get("texts", [])
    datas = context.get("datas", [])
    visualizations = context.get("data_visualizations", [])
    data_insights = context.get("data_insights", [])

    data_ids_with_insights: Set[str] = set()
    has_unsourced_insight = False
    for insight in data_insights:
        source_ids = getattr(insight, "source_ids", None)
        if source_ids:
            for source_id in source_ids:
                if source_id is not None:
                    data_ids_with_insights.add(str(source_id))
        else:
            has_unsourced_insight = True

    text_by_snapshot = _index_by(texts, "snapshot_id")
    text_by_id = _index_by(texts, "id")
    data_by_snapshot = _index_by(datas, "snapshot_id")
    data_by_id = _index_by(datas, "id")
    viz_by_snapshot = _index_by(visualizations, "snapshot_id")
    viz_by_id = _index_by(visualizations, "id")

    modules: Dict[str, List[Dict[str, Any]]] = {
        TopicModuleLayout.PLACEMENT_PRIMARY: [],
        TopicModuleLayout.PLACEMENT_SIDEBAR: [],
    }

    unsourced_insights_assigned = False

    related_topic_modules: List[Dict[str, Any]] = []

    for placement in modules.keys():
        module_entries = publication.layout_snapshot.get(placement, [])
        for entry in module_entries:
            module_key = entry.get("module_key", "")
            payload = entry.get("payload", {})
            base_key, identifier = _split_module_key(module_key)
            if not base_key:
                base_key = payload.get("base_module_key", module_key)
            if not identifier:
                identifier = payload.get("module_identifier")

            registry_entry = MODULE_REGISTRY.get(base_key, {})
            templates = registry_entry.get("templates", {})
            detail_template = templates.get("detail", {})
            context_overrides = dict(detail_template.get("context", {}))

            template_name = payload.get("template_name") or detail_template.get("template")
            if not template_name:
                # Skip modules that cannot be rendered in detail mode.
                continue

            descriptor: Dict[str, Any] = {
                "module_key": module_key,
                "base_module_key": base_key,
                "module_identifier": identifier,
                "placement": placement,
                "display_order": entry.get("display_order", 0),
                "context_overrides": context_overrides,
                "context_keys": payload.get("context_keys")
                or registry_entry.get("context_keys", []),
                "template_name": template_name,
            }

            if base_key == "text":
                snapshot_id = (
                    payload.get("text_snapshot_id")
                    or payload.get("snapshot_id")
                )
                text_obj = None
                if snapshot_id is not None:
                    text_obj = text_by_snapshot.get(str(snapshot_id))
                if text_obj is None:
                    text_id = payload.get("text_id") or identifier
                    if text_id is not None:
                        key = str(text_id)
                        text_obj = text_by_snapshot.get(key) or text_by_id.get(key)
                descriptor["text"] = text_obj

            if base_key == "data":
                snapshot_id = (
                    payload.get("data_snapshot_id")
                    or payload.get("snapshot_id")
                )
                data_obj = None
                if snapshot_id is not None:
                    data_obj = data_by_snapshot.get(str(snapshot_id))
                if data_obj is None:
                    data_id = payload.get("data_id") or identifier
                    if data_id is not None:
                        key = str(data_id)
                        data_obj = data_by_snapshot.get(key) or data_by_id.get(key)
                if data_obj:
                    descriptor["data"] = data_obj
                    descriptor["context_overrides"]["data"] = data_obj
                data_identifier_value = None
                if data_obj is not None:
                    data_identifier_value = getattr(data_obj, "id", None)
                if data_identifier_value is None:
                    data_identifier_value = payload.get("data_id") or identifier
                data_identifier = (
                    str(data_identifier_value)
                    if data_identifier_value is not None
                    else None
                )
                should_show_insights = bool(
                    data_identifier and data_identifier in data_ids_with_insights
                )
                if (
                    not should_show_insights
                    and has_unsourced_insight
                    and not unsourced_insights_assigned
                ):
                    should_show_insights = True
                    unsourced_insights_assigned = True
                if payload.get("show_data_insights") is True:
                    should_show_insights = True
                descriptor["context_overrides"]["show_data_insights"] = should_show_insights

            if base_key == "data_visualizations":
                snapshot_id = (
                    payload.get("visualization_snapshot_id")
                    or payload.get("snapshot_id")
                )
                viz_obj = None
                if snapshot_id is not None:
                    viz_obj = viz_by_snapshot.get(str(snapshot_id))
                if viz_obj is None:
                    viz_id = payload.get("visualization_id") or identifier
                    if viz_id is not None:
                        key = str(viz_id)
                        viz_obj = viz_by_snapshot.get(key) or viz_by_id.get(key)
                descriptor["visualization"] = viz_obj

            if base_key == "related_topics":
                descriptor["placement"] = TopicModuleLayout.PLACEMENT_SIDEBAR
                related_topic_modules.append(descriptor)
                continue

            modules[placement].append(descriptor)

        modules[placement].sort(key=lambda module: module["display_order"])

    if related_topic_modules:
        sidebar_modules = modules.setdefault(
            TopicModuleLayout.PLACEMENT_SIDEBAR, []
        )
        base_order = max(
            (module.get("display_order", 0) for module in sidebar_modules),
            default=0,
        )
        for offset, module in enumerate(related_topic_modules, start=1):
            module["placement"] = TopicModuleLayout.PLACEMENT_SIDEBAR
            module["display_order"] = base_order + offset
            sidebar_modules.append(module)
        sidebar_modules.sort(key=lambda module: module["display_order"])

    return modules
