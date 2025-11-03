from typing import Dict, List, Literal, Optional, Set
from datetime import date, datetime

from django.conf import settings
from django.utils import timezone
from django.utils.timezone import make_naive
from django.urls import reverse
from django.db import transaction
from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce

from slugify import slugify

from ninja import NinjaAPI, Router, Schema
from ninja.errors import HttpError

from pgvector.django import CosineDistance

from semanticnews.agenda.localities import get_locality_label, resolve_locality_code
from semanticnews.agenda.models import Category, Event, Source as AgendaSource
from semanticnews.entities.models import Entity
from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

from .models import (
    Topic,
    RelatedTopic,
    RelatedEntity,
    RelatedEvent,
    Source,
)
from .publishing import publish_topic
from .recaps.api import router as recaps_router
from semanticnews.widgets.api import router as widget_router
from semanticnews.widgets.data.models import (
    TopicDataRequest,
    TopicDataAnalysisRequest,
    TopicDataVisualizationRequest,
)

api = NinjaAPI(title="Topics API", urls_namespace="topics")
relation_router = Router()
api.add_router("/recap", recaps_router)
api.add_router("/relation", relation_router)
api.add_router("/widget", widget_router)

StatusLiteral = Literal["in_progress", "finished", "error"]


class GenerationStatus(Schema):
    status: Optional[StatusLiteral] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class DataGenerationStatuses(Schema):
    add: Optional[GenerationStatus] = None
    analyze: Optional[GenerationStatus] = None
    visualize: Optional[GenerationStatus] = None


class GenerationStatusResponse(Schema):
    current: datetime
    recap: Optional[GenerationStatus] = None
    text: Optional[GenerationStatus] = None
    relation: Optional[GenerationStatus] = None
    image: Optional[GenerationStatus] = None
    data: Optional[DataGenerationStatuses] = None


class RelatedEntityInput(Schema):
    name: str
    role: Optional[str] = None
    disambiguation: Optional[str] = None


class TopicRelatedEntityCreateRequest(Schema):
    topic_uuid: str
    entities: Optional[List[RelatedEntityInput]] = None


class TopicRelatedEntityItem(Schema):
    id: int
    entity_id: int
    entity_name: str
    entity_slug: str
    entity_disambiguation: Optional[str] = None
    role: Optional[str] = None
    source: str
    created_at: datetime


class TopicRelatedEntityCreateResponse(Schema):
    entities: List[TopicRelatedEntityItem]


class TopicRelatedEntityListResponse(Schema):
    total: int
    items: List[TopicRelatedEntityItem]


class _TopicRelatedEntitySuggestion(Schema):
    name: str
    role: Optional[str] = None
    disambiguation: Optional[str] = None


class _TopicRelatedEntitySuggestionResponse(Schema):
    entities: List[_TopicRelatedEntitySuggestion]


def _serialize_related_entity(relation: RelatedEntity) -> TopicRelatedEntityItem:
    entity = relation.entity
    created_at = relation.created_at
    if created_at is not None:
        created_at = make_naive(created_at)
    return TopicRelatedEntityItem(
        id=relation.id,
        entity_id=entity.id,
        entity_name=entity.name,
        entity_slug=entity.slug,
        entity_disambiguation=getattr(entity, "disambiguation", None),
        role=relation.role,
        source=relation.source,
        created_at=created_at or timezone.now(),
    )


def _normalize_inputs(items: List[RelatedEntityInput]) -> List[RelatedEntityInput]:
    normalized: List[RelatedEntityInput] = []
    for item in items:
        name = (item.name or "").strip()
        if not name:
            continue
        role = (item.role or "").strip() or None
        disambiguation = (item.disambiguation or "").strip() or None
        normalized.append(
            RelatedEntityInput(name=name, role=role, disambiguation=disambiguation)
        )
    return normalized


def _save_related_entities(
    *,
    topic: Topic,
    entries: List[RelatedEntityInput],
    source: str,
) -> List[RelatedEntity]:
    existing_relations: Dict[int, RelatedEntity] = {
        relation.entity_id: relation
        for relation in topic.related_entities.select_related("entity")
    }

    retained_entity_ids: Set[int] = set()
    results: List[RelatedEntity] = []

    for entry in entries:
        slug_base = entry.name if not entry.disambiguation else f"{entry.name} {entry.disambiguation}"
        entity_slug = slugify(slug_base)
        defaults = {"name": entry.name}
        if entry.disambiguation:
            defaults["disambiguation"] = entry.disambiguation

        entity, _ = Entity.objects.get_or_create(slug=entity_slug, defaults=defaults)

        update_fields: List[str] = []
        if entity.name != entry.name:
            entity.name = entry.name
            update_fields.append("name")
        if entry.disambiguation is not None and entity.disambiguation != entry.disambiguation:
            entity.disambiguation = entry.disambiguation
            update_fields.append("disambiguation")
        if update_fields:
            entity.save(update_fields=update_fields)

        relation = existing_relations.get(entity.id)
        if relation is None:
            relation = RelatedEntity.objects.create(
                topic=topic,
                entity=entity,
                role=entry.role,
                source=source,
            )
        else:
            relation_update_fields: List[str] = []
            if relation.role != entry.role:
                relation.role = entry.role
                relation_update_fields.append("role")
            if relation.source != source:
                relation.source = source
                relation_update_fields.append("source")
            if relation.is_deleted:
                relation.is_deleted = False
                relation_update_fields.append("is_deleted")
            if relation_update_fields:
                relation.save(update_fields=relation_update_fields)

        if entity.id not in retained_entity_ids:
            results.append(relation)
            retained_entity_ids.add(entity.id)

    for relation in existing_relations.values():
        if relation.entity_id not in retained_entity_ids and not relation.is_deleted:
            relation.is_deleted = True
            relation.save(update_fields=["is_deleted"])

    return results


def _suggest_related_entities(topic: Topic) -> List[RelatedEntityInput]:
    content_md = topic.build_context()
    prompt = (
        f"Below is a set of events and contents about {topic.title}. "
        "Identify the key entities mentioned in connection with this topic. "
        "Respond with a JSON object containing a list 'entities' where each item "
        "has the fields 'name', optional 'role', and optional 'disambiguation'."
    )
    prompt = append_default_language_instruction(prompt)
    prompt += f"\n\n{content_md}"

    with OpenAI() as client:
        response = client.responses.parse(
            model=settings.DEFAULT_AI_MODEL,
            input=prompt,
            text_format=_TopicRelatedEntitySuggestionResponse,
        )

    suggestions = [
        RelatedEntityInput(**suggestion.dict())
        for suggestion in response.output_parsed.entities
    ]
    return suggestions


@relation_router.post("/extract", response=TopicRelatedEntityCreateResponse)
def extract_related_entities(request, payload: TopicRelatedEntityCreateRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    entries: List[RelatedEntityInput]
    source: str
    if payload.entities is not None:
        entries = _normalize_inputs(payload.entities)
        source = Source.USER
    else:
        try:
            entries = _normalize_inputs(_suggest_related_entities(topic))
        except Exception as exc:  # pragma: no cover - surfaced to API consumer
            raise HttpError(500, str(exc))
        source = Source.AGENT

    with transaction.atomic():
        created = _save_related_entities(topic=topic, entries=entries, source=source)
    serialized = [_serialize_related_entity(rel) for rel in created]
    return TopicRelatedEntityCreateResponse(entities=serialized)


@relation_router.get("/{topic_uuid}/list", response=TopicRelatedEntityListResponse)
def list_related_entities(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    relations = (
        topic.related_entities.filter(is_deleted=False)
        .select_related("entity")
        .order_by("-created_at")
    )
    items = [_serialize_related_entity(rel) for rel in relations]
    return TopicRelatedEntityListResponse(total=len(items), items=items)


@relation_router.delete("/{relation_id}", response={204: None})
def delete_related_entity(request, relation_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        relation = RelatedEntity.objects.select_related("topic").get(id=relation_id)
    except RelatedEntity.DoesNotExist:
        raise HttpError(404, "Relation not found")

    if relation.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    if relation.is_deleted:
        return 204, None

    relation.is_deleted = True
    relation.save(update_fields=["is_deleted"])
    return 204, None


@api.get("/{topic_uuid}/generation-status", response=GenerationStatusResponse)
def generation_status(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    def latest(qs):
        row = (
            qs.order_by("-created_at")
              .values("status", "error_message", "created_at")
              .first()
        )
        return row or None

    data_status_map = {
        TopicDataRequest.Status.PENDING: "in_progress",
        TopicDataRequest.Status.STARTED: "in_progress",
        TopicDataRequest.Status.SUCCESS: "finished",
        TopicDataRequest.Status.FAILURE: "error",
        TopicDataAnalysisRequest.Status.PENDING: "in_progress",
        TopicDataAnalysisRequest.Status.STARTED: "in_progress",
        TopicDataAnalysisRequest.Status.SUCCESS: "finished",
        TopicDataAnalysisRequest.Status.FAILURE: "error",
        TopicDataVisualizationRequest.Status.PENDING: "in_progress",
        TopicDataVisualizationRequest.Status.STARTED: "in_progress",
        TopicDataVisualizationRequest.Status.SUCCESS: "finished",
        TopicDataVisualizationRequest.Status.FAILURE: "error",
    }

    def latest_data_status(qs):
        row = (
            qs.filter(user_id=user.id)
              .order_by("-updated_at")
              .values("status", "error_message", "created_at", "updated_at")
              .first()
        )
        if not row:
            return None
        mapped = data_status_map.get(row.get("status"))
        if not mapped:
            return None
        timestamp = row.get("updated_at") or row.get("created_at")
        return {
            "status": mapped,
            "error_message": row.get("error_message"),
            "created_at": timestamp,
        }

    data_statuses = {
        "add": latest_data_status(topic.data_requests),
        "analyze": latest_data_status(topic.data_analysis_requests),
        "visualize": latest_data_status(topic.data_visualization_requests),
    }

    data_payload = (
        DataGenerationStatuses(**data_statuses)
        if any(data_statuses.values())
        else None
    )

    return GenerationStatusResponse(
        current=timezone.now(),
        recap=latest(topic.recaps.filter(is_deleted=False)),
        text=latest(topic.texts.filter(is_deleted=False)),
        relation=None,
        image=latest(topic.images.filter(is_deleted=False)),
        data=data_payload,
    )


class TopicCreateResponse(Schema):
    """Response returned after creating a topic.

    Attributes:
        uuid (str): Unique identifier of the topic.
    """

    uuid: str


@api.post("/create", response=TopicCreateResponse)
def create_topic(request):
    """Create a new topic for the authenticated user.

    Args:
        request: The HTTP request instance.

    Returns:
        Data for the newly created topic.
    """

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    topic = Topic.objects.create(created_by=user)

    return TopicCreateResponse(uuid=str(topic.uuid))


class TopicStatusUpdateRequest(Schema):
    """Request body for updating a topic's status.

    Attributes:
        topic_uuid (str): UUID of the topic.
        status (str): New status for the topic.
    """

    topic_uuid: str
    status: str


class TopicStatusUpdateResponse(Schema):
    """Response returned after updating a topic's status.

    Attributes:
        topic_uuid (str): UUID of the topic.
        status (str): The topic's updated status.
    """

    topic_uuid: str
    status: str


class TopicTitleUpdateRequest(Schema):
    """Request body for updating a topic's title."""

    topic_uuid: str
    title: Optional[str] = None


class TopicTitleUpdateResponse(Schema):
    """Response returned after updating a topic's title."""

    topic_uuid: str
    title: Optional[str] = None
    slug: Optional[str] = None
    detail_url: Optional[str] = None
    edit_url: str


@api.post("/set-status", response=TopicStatusUpdateResponse)
def set_topic_status(request, payload: TopicStatusUpdateRequest):
    """Update the status of a topic owned by the authenticated user.

    Args:
        request: The HTTP request instance.
        payload: Data including the topic UUID and desired status.

    Returns:
        Data for the topic with its new status.
    """

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by != user:
        raise HttpError(403, "Forbidden")

    valid_statuses = {choice[0] for choice in Topic._meta.get_field("status").choices}
    if payload.status not in valid_statuses:
        raise HttpError(400, "Invalid status")

    if payload.status == "published":
        is_republishing_archived_topic = (
            topic.status == "archived" and topic.last_published_at is not None
        )

        if not is_republishing_archived_topic:
            if not topic.title:
                raise HttpError(400, "A title is required to publish a topic.")

            has_finished_recap = topic.recaps.filter(status="finished", is_deleted=False).exists()
            if not has_finished_recap:
                raise HttpError(400, "A recap is required to publish a topic.")

        publish_topic(topic, user)
    else:
        topic.status = payload.status
        topic.save(update_fields=["status"])

    return TopicStatusUpdateResponse(topic_uuid=str(topic.uuid), status=topic.status)


@api.post("/set-title", response=TopicTitleUpdateResponse)
def set_topic_title(request, payload: TopicTitleUpdateRequest):
    """Update the title of a topic owned by the authenticated user."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by != user:
        raise HttpError(403, "Forbidden")

    new_title = (payload.title or "").strip()
    topic.title = new_title or None
    topic.save()

    slug_value = topic.slug
    detail_url = None
    if slug_value:
        detail_url = reverse(
            "topics_detail_redirect",
            kwargs={
                "topic_uuid": str(topic.uuid),
                "username": topic.created_by.username,
            },
        )

    return TopicTitleUpdateResponse(
        topic_uuid=str(topic.uuid),
        title=topic.title,
        slug=slug_value,
        edit_url=reverse(
            "topics_detail_edit",
            kwargs={"topic_uuid": str(topic.uuid), "username": topic.created_by.username},
        ),
        detail_url=detail_url,
    )


def _get_owned_topic(request, topic_uuid: str) -> Topic:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by != user:
        raise HttpError(403, "Forbidden")

    return topic


class TopicRelatedEventAddRequest(Schema):
    """Request body for adding an agenda event to a topic.

    Attributes:
        topic_uuid (str): UUID of the topic.
        event_uuid (str): UUID of the agenda event.
    """

    topic_uuid: str
    event_uuid: str


class TopicRelatedEventAddResponse(Schema):
    """Response returned after adding an event to a topic.

    Attributes:
        topic_uuid (str): UUID of the topic.
        event_uuid (str): UUID of the agenda event.
    """

    topic_uuid: str
    event_uuid: str


@api.post("/add-event", response=TopicRelatedEventAddResponse)
def add_event_to_topic(request, payload: TopicRelatedEventAddRequest):
    """Add an agenda event to a topic for the authenticated user.

    Args:
        request: The HTTP request instance.
        payload: Data including topic/event UUIDs and optional role.

    Returns:
        Data for the created relation between topic and event.
    """

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by != user:
        topic = topic.clone_for_user(user)

    try:
        event = Event.objects.get(uuid=payload.event_uuid)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")

    with transaction.atomic():
        relation, created = RelatedEvent.objects.select_for_update().get_or_create(
            topic=topic,
            event=event,
            defaults={
                "source": Source.AGENT if topic.created_by != user else Source.USER
            },
        )

        if not created and relation.is_deleted:
            relation.is_deleted = False
            if topic.created_by != user:
                relation.source = Source.AGENT
                relation.save(update_fields=["is_deleted", "source"])
            else:
                relation.save(update_fields=["is_deleted"])
        elif not created:
            raise HttpError(400, "Event already linked to topic")

    return TopicRelatedEventAddResponse(
        topic_uuid=str(topic.uuid),
        event_uuid=str(event.uuid),
    )


class TopicRelatedEventRemoveRequest(Schema):
    """Request body for removing an agenda event from a topic.

    Attributes:
        topic_uuid (str): UUID of the topic.
        event_uuid (str): UUID of the agenda event.
    """

    topic_uuid: str
    event_uuid: str


class TopicRelatedEventRemoveResponse(Schema):
    """Response returned after removing an event from a topic.

    Attributes:
        topic_uuid (str): UUID of the topic.
        event_uuid (str): UUID of the agenda event.
    """

    topic_uuid: str
    event_uuid: str


@api.post("/remove-event", response=TopicRelatedEventRemoveResponse)
def remove_event_from_topic(request, payload: TopicRelatedEventRemoveRequest):
    """Remove an agenda event from a topic for the authenticated user.

    Args:
        request: The HTTP request instance.
        payload: Data including the topic and event UUIDs.

    Returns:
        Data confirming the removal of the relation between topic and event.
    """

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    try:
        event = Event.objects.get(uuid=payload.event_uuid)
    except Event.DoesNotExist:
        raise HttpError(404, "Event not found")

    updated = RelatedEvent.objects.filter(
        topic=topic,
        event=event,
        is_deleted=False,
    ).update(is_deleted=True)
    if updated == 0:
        raise HttpError(404, "Event not linked to topic")

    return TopicRelatedEventRemoveResponse(
        topic_uuid=str(topic.uuid),
        event_uuid=str(event.uuid),
    )


class TimelineSuggestedEvent(Schema):
    """Schema representing an event suggested by the AI."""

    title: str
    date: date
    categories: List[str] = []
    sources: List[str] = []


class TimelineSuggestedEventOut(TimelineSuggestedEvent):
    """Schema representing a suggested event with its created UUID."""

    uuid: str


class TimelineEventList(Schema):
    """Wrapper for a list of timeline events."""

    events: List[TimelineSuggestedEvent] = []


class TimelineRelatedEvent(Schema):
    """Schema for an existing event related to the topic."""

    uuid: str
    title: str
    date: date
    similarity: float


class TimelineRelatedRequest(Schema):
    """Request body for retrieving existing events related to a topic."""

    topic_uuid: str
    threshold: float = 0.5
    limit: int = 10


@api.post("/timeline/related", response=List[TimelineRelatedEvent])
def list_related_events(request, payload: TimelineRelatedRequest):
    """List existing agenda events related to the topic by embedding similarity."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.embedding is None:
        return []

    queryset = (
        Event.objects.exclude(embedding__isnull=True)
        .exclude(
            relatedevent__topic=topic,
            relatedevent__is_deleted=False,
        )
        .annotate(distance=CosineDistance("embedding", topic.embedding))
        .annotate(similarity=Value(1.0) - F("distance"))
        .filter(similarity__gte=payload.threshold)
        .order_by("-similarity")[: payload.limit]
    )

    return [
        TimelineRelatedEvent(
            uuid=str(ev.uuid),
            title=ev.title,
            date=ev.date,
            similarity=ev.similarity,
        )
        for ev in queryset
    ]


class TimelineSuggestRequest(Schema):
    """Request body for suggesting events for a topic timeline."""

    topic_uuid: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    locality: Optional[str] = None
    related_event: Optional[str] = None
    limit: int = 5


@api.post("/timeline/suggest", response=List[TimelineSuggestedEventOut])
def suggest_topic_events(request, payload: TimelineSuggestRequest):
    """Return AI-suggested events related to a topic and create Event objects."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if payload.start_date and payload.end_date:
        if payload.start_date == payload.end_date:
            timeframe = f"on {payload.start_date:%Y-%m-%d}"
        else:
            timeframe = (
                f"between {payload.start_date:%Y-%m-%d} and {payload.end_date:%Y-%m-%d}"
            )
    elif payload.start_date:
        timeframe = f"since {payload.start_date:%Y-%m-%d}"
    elif payload.end_date:
        timeframe = f"until {payload.end_date:%Y-%m-%d}"
    else:
        timeframe = "recently"

    locality_code = resolve_locality_code(payload.locality)
    locality_label = get_locality_label(locality_code) if locality_code else None

    if locality_label:
        timeframe += f" in {locality_label}"

    descriptor_parts = []
    if payload.related_event:
        descriptor_parts.append(f'related to "{payload.related_event}"')
    descriptor_parts.append(timeframe)
    descriptor = " ".join(descriptor_parts)

    prompt = (
        f"List the top {payload.limit} significant events related to the topic "
        f'"{topic.title}" {descriptor}. '
        "Generate event titles as concise factual statements. "
        "State the core fact directly and neutrally. "
        "For each event, include a few source URLs as citations."
    )
    prompt = append_default_language_instruction(prompt)

    context = topic.build_context()
    if context:
        prompt += "\n\nContext:\n" + context

    created_events: List[TimelineSuggestedEventOut] = []

    with OpenAI() as client:
        response = client.responses.parse(
            model=settings.DEFAULT_AI_MODEL,
            tools=[{"type": "web_search_preview"}],
            input=prompt,
            text_format=TimelineEventList,
        )

        existing_titles = {
            title.lower()
            for title in topic.events.filter(relatedevent__is_deleted=False)
            .values_list("title", flat=True)
        }
        suggestions = [
            ev for ev in response.output_parsed.events if ev.title.lower() not in existing_titles
        ]

        for ev in suggestions:
            text = f"{ev.title} - {ev.date}\n{', '.join(ev.categories or [])}"
            embedding = client.embeddings.create(
                input=text,
                model="text-embedding-3-small",
            ).data[0].embedding
            event, created = Event.objects.get_or_create_semantic(
                date=ev.date,
                embedding=embedding,
                defaults={
                    "title": ev.title,
                    "status": "published",
                    "created_by": user,
                    "locality": locality_code,
                },
            )

            if created:
                for url in ev.sources or []:
                    source_obj, _ = AgendaSource.objects.get_or_create(url=url)
                    event.sources.add(source_obj)

                for name in ev.categories or []:
                    category, _ = Category.objects.get_or_create(name=name)
                    event.categories.add(category)

            if not created and locality_code and not event.locality:
                event.locality = locality_code
                event.save(update_fields=["locality"])

            created_events.append(
                TimelineSuggestedEventOut(
                    uuid=str(event.uuid),
                    title=event.title,
                    date=event.date,
                    categories=ev.categories,
                    sources=ev.sources,
                )
            )

    return created_events


class TimelineCreateRequest(Schema):
    """Request body for relating selected events to the topic."""

    topic_uuid: str
    event_uuids: List[str]


class TimelineCreatedEvent(Schema):
    """Data returned for an event created from suggestions."""

    uuid: str
    title: str
    date: date


@api.post("/timeline/create", response=List[TimelineCreatedEvent])
def create_topic_events(request, payload: TimelineCreateRequest):
    """Relate selected events to the topic as RelatedEvents."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    created: List[TimelineCreatedEvent] = []
    for event_uuid in payload.event_uuids:
        try:
            event = Event.objects.get(uuid=event_uuid)
        except Event.DoesNotExist:
            raise HttpError(404, "Event not found")

        relation, relation_created = RelatedEvent.objects.get_or_create(
            topic=topic,
            event=event,
            defaults={"source": Source.AGENT},
        )

        if not relation_created and relation.is_deleted:
            relation.is_deleted = False
            relation.source = Source.AGENT
            relation.save(update_fields=["is_deleted", "source"])

        created.append(
            TimelineCreatedEvent(
                uuid=str(event.uuid), title=event.title, date=event.date
            )
        )

    return created


class RelatedTopicLinkSchema(Schema):
    id: int
    topic_uuid: str
    title: Optional[str]
    slug: Optional[str]
    username: Optional[str]
    display_name: Optional[str]
    source: str
    is_deleted: bool
    created_at: datetime
    published_at: Optional[datetime]


class RelatedTopicSearchResult(Schema):
    uuid: str
    title: Optional[str]
    slug: Optional[str]
    username: Optional[str]
    is_already_linked: bool = False


class RelatedTopicCreateRequest(Schema):
    related_topic_uuid: str


def _require_owned_topic(request, topic_uuid: str) -> Topic:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    return topic


def _serialize_related_topic_link(link: RelatedTopic) -> RelatedTopicLinkSchema:
    related_topic = link.related_topic
    created_by = getattr(related_topic, "created_by", None)
    username = getattr(created_by, "username", None)
    display_name = None
    if created_by is not None:
        if hasattr(created_by, "get_full_name"):
            display_name = created_by.get_full_name() or None
        if not display_name:
            display_name = str(created_by)
    return RelatedTopicLinkSchema(
        id=link.id,
        topic_uuid=str(getattr(related_topic, "uuid", "")),
        title=getattr(related_topic, "title", None),
        slug=getattr(related_topic, "slug", None),
        username=username,
        display_name=display_name,
        source=link.source,
        is_deleted=link.is_deleted,
        created_at=link.created_at,
        published_at=getattr(related_topic, "last_published_at", None),
    )


@api.get("/{topic_uuid}/related-topics", response=List[RelatedTopicLinkSchema])
def list_related_topics(request, topic_uuid: str):
    topic = _require_owned_topic(request, topic_uuid)
    links = (
        RelatedTopic.objects.filter(topic=topic, is_deleted=False)
        .select_related("related_topic__created_by")
        .order_by("-created_at")
    )
    return [_serialize_related_topic_link(link) for link in links]


@api.get(
    "/{topic_uuid}/related-topics/search",
    response=List[RelatedTopicSearchResult],
)
def search_related_topics(request, topic_uuid: str, query: Optional[str] = None):
    topic = _require_owned_topic(request, topic_uuid)
    existing_links = {
        link.related_topic_id: link
        for link in RelatedTopic.objects.filter(topic=topic)
    }

    qs = (
        Topic.objects.filter(status="published")
        .exclude(uuid=topic.uuid)
        .select_related("created_by")
    )

    if query:
        trimmed_query = query.strip()
        if trimmed_query:
            title_filter = Q(
                titles__published_at__isnull=False,
                titles__title__icontains=trimmed_query,
            ) | Q(
                titles__published_at__isnull=False,
                titles__slug__icontains=trimmed_query,
            )
            qs = qs.filter(title_filter | Q(created_by__username__icontains=trimmed_query)).distinct()

    qs = (
        qs.annotate(ordering_activity=Coalesce("last_published_at", "created_at"))
        .order_by("-ordering_activity", "-created_at")[:10]
    )

    results: List[RelatedTopicSearchResult] = []
    for result in qs:
        link = existing_links.get(result.id)
        results.append(
            RelatedTopicSearchResult(
                uuid=str(result.uuid),
                title=result.title,
                slug=result.slug,
                username=getattr(result.created_by, "username", None),
                is_already_linked=link is not None and not link.is_deleted,
            )
        )

    return results


@api.post(
    "/{topic_uuid}/related-topics",
    response=RelatedTopicLinkSchema,
)
def add_related_topic(
    request, topic_uuid: str, payload: RelatedTopicCreateRequest
):
    topic = _require_owned_topic(request, topic_uuid)

    try:
        related_topic = Topic.objects.get(uuid=payload.related_topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Related topic not found")

    if related_topic == topic:
        raise HttpError(400, "Cannot relate a topic to itself")

    link, created = RelatedTopic.objects.get_or_create(
        topic=topic,
        related_topic=related_topic,
        defaults={
            "source": Source.USER,
        },
    )

    if not created:
        if not link.is_deleted:
            raise HttpError(400, "Related topic already linked")

        update_fields = ["is_deleted"]
        link.is_deleted = False
        if link.source != Source.USER:
            link.source = Source.USER
            update_fields.append("source")
        link.save(update_fields=update_fields)

    return _serialize_related_topic_link(link)


@api.delete(
    "/{topic_uuid}/related-topics/{link_id}",
    response=RelatedTopicLinkSchema,
)
def remove_related_topic(request, topic_uuid: str, link_id: int):
    topic = _require_owned_topic(request, topic_uuid)

    try:
        link = RelatedTopic.objects.select_related("related_topic").get(
            topic=topic,
            id=link_id,
        )
    except RelatedTopic.DoesNotExist:
        raise HttpError(404, "Related topic link not found")

    if not link.is_deleted:
        link.is_deleted = True
        link.save(update_fields=["is_deleted"])

    return _serialize_related_topic_link(link)


@api.post(
    "/{topic_uuid}/related-topics/{link_id}/restore",
    response=RelatedTopicLinkSchema,
)
def restore_related_topic(request, topic_uuid: str, link_id: int):
    topic = _require_owned_topic(request, topic_uuid)

    try:
        link = RelatedTopic.objects.select_related("related_topic").get(
            topic=topic,
            id=link_id,
        )
    except RelatedTopic.DoesNotExist:
        raise HttpError(404, "Related topic link not found")

    if link.is_deleted:
        link.is_deleted = False
        link.save(update_fields=["is_deleted"])

    return _serialize_related_topic_link(link)


class TopicSuggestionList(Schema):
    """Schema representing a list of suggested topic titles."""

    topics: List[str] = []


class SuggestTopicsRequest(Schema):
    """Request body for suggesting topics based on available information.

    Attributes:
        about (Optional[str]): Description of the subject to suggest topics about.
        limit (int): Maximum number of topics to return. Defaults to ``3``.
        topic_uuid (Optional[str]): UUID of an existing topic whose context should
            be used when generating suggestions.
    """

    about: Optional[str] = None
    limit: int = 3
    topic_uuid: Optional[str] = None


def _has_meaningful_context(context: str) -> bool:
    """Return ``True`` when the provided context contains useful content."""

    if not context:
        return False

    stripped = context.strip()
    if not stripped:
        return False

    # ``Topic.build_context`` always prefixes a markdown heading. Strip heading
    # characters to detect whether any substantive text remains.
    return bool(stripped.strip("# \n\t"))


def suggest_topics(
    *, about: Optional[str] = None, limit: int = 3, topic_uuid: Optional[str] = None
) -> List[str]:
    """Return a list of suggested topics for available context."""

    description = (about or "").strip()

    topic_context = ""
    if topic_uuid:
        try:
            topic = Topic.objects.get(uuid=topic_uuid)
        except Topic.DoesNotExist:
            raise HttpError(404, "Topic not found")
        topic_context = topic.build_context()

    context_parts = []
    if description:
        context_parts.append(f"Description:\n{description}")
    if _has_meaningful_context(topic_context):
        context_parts.append(f"Existing topic context:\n{topic_context.strip()}")

    if not context_parts:
        raise HttpError(
            400,
            "Provide a description or add content to the topic before requesting suggestions.",
        )

    prompt = (
        f"Suggest {limit} topic ideas for a news topic. "
        f"Each topic should be a short, broad phrase in nominalized passive form. "
        f"Avoid overly specific or literal restatements of the subject. "
        f"Make the {limit} suggestions vary in scope, but none too specific. "
    )

    prompt += "\n\nUse the following information as context:\n\n"
    prompt += "\n\n".join(context_parts)
    prompt = append_default_language_instruction(prompt)

    with OpenAI() as client:
        response = client.responses.parse(
            model=settings.DEFAULT_AI_MODEL,
            input=prompt,
            text_format=TopicSuggestionList,
        )

    return response.output_parsed.topics


@api.get("/suggest", response=List[str])
def suggest_topics_get(
    request, about: Optional[str] = None, limit: int = 3, topic_uuid: Optional[str] = None
):
    """Return suggested topics for a description and/or context via GET."""

    return suggest_topics(about=about, limit=limit, topic_uuid=topic_uuid)


@api.post("/suggest", response=List[str])
def suggest_topics_post(request, payload: SuggestTopicsRequest):
    """Return suggested topics for a description and/or context via POST."""

    return suggest_topics(
        about=payload.about, limit=payload.limit, topic_uuid=payload.topic_uuid
    )


