from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from ..layouts import (
    MODULE_REGISTRY,
    annotate_module_content,
    get_layout_for_mode,
    _split_module_key,
)
from ..models import Topic, TopicModuleLayout
from ..utils.data.models import TopicData, TopicDataInsight, TopicDataVisualization
from ..utils.documents.models import TopicDocument, TopicWebpage
from ..utils.embeds.models import TopicTweet, TopicYoutubeVideo
from ..utils.images.models import TopicImage
from ..utils.recaps.models import TopicRecap
from ..utils.relations.models import TopicEntityRelation
from ..utils.text.models import TopicText
from ..utils.timeline.models import TopicEvent
from .models import (
    TopicPublication,
    TopicPublicationModule,
    TopicPublishedData,
    TopicPublishedDataInsight,
    TopicPublishedDataVisualization,
    TopicPublishedDocument,
    TopicPublishedEvent,
    TopicPublishedImage,
    TopicPublishedRecap,
    TopicPublishedRelation,
    TopicPublishedText,
    TopicPublishedTweet,
    TopicPublishedWebpage,
    TopicPublishedYoutubeVideo,
)


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


def _module_payload(module: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "base_module_key": module.get("base_module_key", module.get("module_key")),
        "module_identifier": module.get("module_identifier"),
        "context_keys": module.get("context_keys", []),
        "template_name": module.get("template_name"),
    }
    base_key = payload["base_module_key"]
    if base_key == "text" and module.get("text"):
        payload["text_id"] = getattr(module["text"], "id", None)
    if base_key == "data":
        data_obj = module.get("data") or module.get("context_overrides", {}).get("data")
        if data_obj is not None:
            payload["data_id"] = getattr(data_obj, "id", None)
        payload["show_data_insights"] = (
            module.get("context_overrides", {}).get("show_data_insights", False)
        )
    if base_key == "data_visualizations" and module.get("visualization"):
        payload["visualization_id"] = getattr(module["visualization"], "id", None)
    return payload


@dataclass
class LiveTopicContent:
    """Container for the draft-side content that will be snapshotted."""

    hero_image: Optional[TopicImage]
    images: List[TopicImage]
    texts: List[TopicText]
    latest_recap: Optional[TopicRecap]
    recaps: List[TopicRecap]
    latest_relation: Optional[TopicEntityRelation]
    latest_data: Optional[TopicData]
    datas: List[TopicData]
    data_insights: List[TopicDataInsight]
    data_visualizations: List[TopicDataVisualization]
    youtube_video: Optional[TopicYoutubeVideo]
    tweets: List[TopicTweet]
    documents: List[TopicDocument]
    webpages: List[TopicWebpage]
    events: List[TopicEvent]


def _collect_live_content(topic: Topic) -> LiveTopicContent:
    texts = list(topic.texts.filter(is_deleted=False).order_by("created_at"))
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
    images = list(
        topic.images.filter(status="finished", is_deleted=False).order_by("-created_at")
    )
    events = list(
        TopicEvent.objects.filter(topic=topic, is_deleted=False)
        .select_related("event")
        .order_by("-created_at")
    )

    latest_recap = recaps[0] if recaps else None

    return LiveTopicContent(
        hero_image=images[0] if images else None,
        images=images,
        texts=texts,
        latest_recap=latest_recap,
        recaps=recaps,
        latest_relation=relations_qs.first(),
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


def _build_context_snapshot(topic: Topic, content: LiveTopicContent) -> Dict[str, Any]:
    latest_recap = content.latest_recap
    latest_relation = content.latest_relation
    recaps = content.recaps
    latest_data = content.latest_data
    datas = content.datas
    data_insights = content.data_insights
    data_visualizations = content.data_visualizations
    youtube_video = content.youtube_video
    tweets = content.tweets
    documents = content.documents
    webpages = content.webpages
    texts = content.texts
    hero_image = content.hero_image

    relations_json = ""
    relations_json_pretty = ""
    if latest_relation:
        relations_json = json.dumps(latest_relation.relations, separators=(",", ":"))
        relations_json_pretty = json.dumps(latest_relation.relations, indent=2)

    return {
        "image": asdict(_serialize_image(hero_image)) if hero_image else None,
        "texts": [asdict(text) for text in _serialize_texts(texts)],
        "latest_recap": asdict(_serialize_recap(latest_recap)) if latest_recap else None,
        "recaps": [asdict(_serialize_recap(recap)) for recap in recaps],
        "latest_relation": asdict(_serialize_relation(latest_relation))
        if latest_relation
        else None,
        "relations_json": relations_json,
        "relations_json_pretty": relations_json_pretty,
        "latest_data": asdict(_serialize_data([latest_data])[0]) if latest_data else None,
        "datas": [asdict(data) for data in _serialize_data(datas)],
        "data_insights": [
            asdict(insight) for insight in _serialize_data_insights(data_insights)
        ],
        "data_visualizations": [
            asdict(viz) for viz in _serialize_data_visualizations(data_visualizations)
        ],
        "youtube_video": asdict(_serialize_youtube_video(youtube_video))
        if youtube_video
        else None,
        "tweets": [asdict(tweet) for tweet in _serialize_tweets(tweets)],
        "documents": [asdict(doc) for doc in _serialize_documents(documents)],
        "webpages": [asdict(page) for page in _serialize_webpages(webpages)],
        "related_event_ids": [event.event_id for event in content.events],
    }


@transaction.atomic
def publish_topic(topic: Topic, user) -> TopicPublication:
    """Create a publication snapshot for ``topic`` and mark it as published."""

    publication = TopicPublication.objects.create(
        topic=topic,
        published_by=user,
    )

    content = _collect_live_content(topic)
    context_snapshot = _build_context_snapshot(topic, content)
    publication.context_snapshot = context_snapshot

    layout = get_layout_for_mode(topic, mode="detail")
    module_records: List[TopicPublicationModule] = []
    for placement, modules in layout.items():
        for module in modules:
            payload = _module_payload(module)
            module_records.append(
                TopicPublicationModule(
                    publication=publication,
                    module_key=module["module_key"],
                    placement=placement,
                    display_order=module["display_order"],
                    payload=payload,
                )
            )
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

    # Snapshot utility payloads for admin/debugging views.
    TopicPublishedText.objects.bulk_create(
        [
            TopicPublishedText(
                publication=publication,
                original_id=text.id,
                content=text.content,
                status=text.status,
                created_at=text.created_at,
                updated_at=text.updated_at,
            )
            for text in content.texts
        ]
    )

    TopicPublishedRecap.objects.bulk_create(
        [
            TopicPublishedRecap(
                publication=publication,
                original_id=recap.id,
                recap=recap.recap,
                status=recap.status,
                created_at=recap.created_at,
            )
            for recap in content.recaps
        ]
    )

    TopicPublishedDocument.objects.bulk_create(
        [
            TopicPublishedDocument(
                publication=publication,
                original_id=document.id,
                title=document.title,
                url=document.url,
                description=document.description,
                document_type=document.document_type,
                created_at=document.created_at,
            )
            for document in content.documents
        ]
    )

    TopicPublishedWebpage.objects.bulk_create(
        [
            TopicPublishedWebpage(
                publication=publication,
                original_id=page.id,
                title=page.title,
                url=page.url,
                description=page.description,
                created_at=page.created_at,
            )
            for page in content.webpages
        ]
    )

    TopicPublishedData.objects.bulk_create(
        [
            TopicPublishedData(
                publication=publication,
                original_id=data.id,
                name=data.name,
                data=data.data,
                sources=data.sources,
                explanation=data.explanation,
                created_at=data.created_at,
            )
            for data in content.datas
        ]
    )

    TopicPublishedDataInsight.objects.bulk_create(
        [
            TopicPublishedDataInsight(
                publication=publication,
                original_id=insight.id,
                insight=insight.insight,
                source_ids=list(insight.sources.values_list("id", flat=True)),
                created_at=insight.created_at,
            )
            for insight in content.data_insights
        ]
    )

    TopicPublishedDataVisualization.objects.bulk_create(
        [
            TopicPublishedDataVisualization(
                publication=publication,
                original_id=viz.id,
                chart_type=viz.chart_type,
                chart_data=viz.chart_data,
                insight_text=(viz.insight.insight if viz.insight else ""),
                created_at=viz.created_at,
            )
            for viz in content.data_visualizations
        ]
    )

    TopicPublishedRelation.objects.bulk_create(
        [
            TopicPublishedRelation(
                publication=publication,
                original_id=relation.id,
                relations=relation.relations,
                status=relation.status,
                created_at=relation.created_at,
            )
            for relation in ([content.latest_relation] if content.latest_relation else [])
        ]
    )

    TopicPublishedTweet.objects.bulk_create(
        [
            TopicPublishedTweet(
                publication=publication,
                original_id=tweet.id,
                tweet_id=tweet.tweet_id,
                url=tweet.url,
                html=tweet.html,
                created_at=tweet.created_at,
            )
            for tweet in content.tweets
        ]
    )

    if content.youtube_video:
        TopicPublishedYoutubeVideo.objects.create(
            publication=publication,
            original_id=content.youtube_video.id,
            url=content.youtube_video.url,
            video_id=content.youtube_video.video_id,
            title=content.youtube_video.title,
            description=content.youtube_video.description,
            thumbnail=content.youtube_video.thumbnail,
            published_at=content.youtube_video.video_published_at,
        )

    TopicPublishedImage.objects.bulk_create(
        [
            TopicPublishedImage(
                publication=publication,
                original_id=image.id,
                image=getattr(getattr(image, "image", None), "url", ""),
                thumbnail=getattr(getattr(image, "thumbnail", None), "url", ""),
                created_at=image.created_at,
            )
            for image in content.images
        ]
    )

    TopicPublishedEvent.objects.bulk_create(
        [
            TopicPublishedEvent(
                publication=publication,
                original_id=event.id,
                event_id=event.event_id,
                role=event.role,
                significance=event.significance,
                created_at=event.created_at,
            )
            for event in content.events
        ]
    )

    now = timezone.now()
    topic.status = "published"
    topic.latest_publication = publication
    topic.last_published_at = now
    topic.save(update_fields=["status", "latest_publication", "last_published_at"])

    # Update publish metadata on utility models
    topic.texts.update(published_at=now)
    topic.recaps.update(published_at=now)
    topic.documents.update(published_at=now)
    topic.webpages.update(published_at=now)
    topic.datas.update(published_at=now)
    topic.data_insights.update(published_at=now)
    topic.data_visualizations.update(published_at=now)
    topic.entity_relations.update(published_at=now)
    topic.images.update(published_at=now)
    topic.tweets.update(published_at=now)
    topic.youtube_videos.update(published_at=now)
    TopicEvent.objects.filter(topic=topic).update(published_at=now)

    return publication


def build_publication_context(topic: Topic, publication: TopicPublication) -> Dict[str, Any]:
    """Return a context dictionary usable by the detail template."""

    snapshot = publication.context_snapshot or {}

    def _ns(data: Optional[Dict[str, Any]]) -> Optional[SimpleNamespace]:
        if not data:
            return None
        return SimpleNamespace(**data)

    context: Dict[str, Any] = {
        "topic": topic,
        "related_events": list(
            topic.events.filter(id__in=snapshot.get("related_event_ids", []))
        ),
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
    }

    if not context["latest_recap"]:
        recaps = context.get("recaps", [])
        if recaps:
            context["latest_recap"] = recaps[0]

    image_data = snapshot.get("image")
    if image_data:
        image_obj = SimpleNamespace(
            image=SimpleNamespace(url=image_data.get("image_url")),
            thumbnail=SimpleNamespace(url=image_data.get("thumbnail_url")),
            created_at=image_data.get("created_at"),
        )

        class TopicProxy:
            def __init__(self, base: Topic, image):
                self._base = base
                self._image = image

            def __getattr__(self, item):
                return getattr(self._base, item)

            @property
            def image(self):
                return self._image

            @property
            def thumbnail(self):
                return self._image

        context["topic"] = TopicProxy(topic, image_obj)
    return context


def build_publication_modules(
    publication: TopicPublication, context: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    """Return module descriptors recreated from a publication snapshot."""

    text_map = {
        str(getattr(text, "id", "")): text for text in context.get("texts", [])
    }
    data_map = {
        str(getattr(data, "id", "")): data for data in context.get("datas", [])
    }
    visualization_map = {
        str(getattr(viz, "id", "")): viz
        for viz in context.get("data_visualizations", [])
    }

    modules: Dict[str, List[Dict[str, Any]]] = {
        TopicModuleLayout.PLACEMENT_PRIMARY: [],
        TopicModuleLayout.PLACEMENT_SIDEBAR: [],
    }

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
                text_id = payload.get("text_id") or identifier
                text_obj = text_map.get(str(text_id))
                descriptor["text"] = text_obj

            if base_key == "data":
                data_id = payload.get("data_id") or identifier
                data_obj = data_map.get(str(data_id))
                if data_obj:
                    descriptor["data"] = data_obj
                    descriptor["context_overrides"]["data"] = data_obj
                descriptor["context_overrides"]["show_data_insights"] = payload.get(
                    "show_data_insights", False
                )

            if base_key == "data_visualizations":
                viz_id = payload.get("visualization_id") or identifier
                viz_obj = visualization_map.get(str(viz_id))
                descriptor["visualization"] = viz_obj

            modules[placement].append(descriptor)

        modules[placement].sort(key=lambda module: module["display_order"])

    return modules
