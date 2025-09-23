"""API endpoints for timeline event suggestions and creation."""

from datetime import date
from typing import List, Optional

from ninja import Router, Schema
from ninja.errors import HttpError
from django.db.models import F, Value
from pgvector.django import CosineDistance

from ...models import Topic
from ....agenda.models import Category, Event, Source
from .models import TopicEvent
from ....openai import OpenAI
from semanticnews.prompting import append_default_language_instruction


router = Router()


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


@router.post("/related", response=List[TimelineRelatedEvent])
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
        .exclude(topics=topic)
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


@router.post("/suggest", response=List[TimelineSuggestedEventOut])
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

    if payload.locality:
        timeframe += f" in {payload.locality}"

    descriptor_parts = []
    if payload.related_event:
        descriptor_parts.append(f'related to "{payload.related_event}"')
    descriptor_parts.append(timeframe)
    descriptor = " ".join(descriptor_parts)

    prompt = (
        f"List the top {payload.limit} significant events related to the topic "
        f"\"{topic.title}\" {descriptor}."
        " Generate event titles as concise factual statements. "
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
            model="gpt-5",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
            text_format=TimelineEventList,
        )

        existing_titles = set(
            title.lower()
            for title in topic.events.values_list("title", flat=True)
        )
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
                },
            )

            if created:
                for url in ev.sources or []:
                    source_obj, _ = Source.objects.get_or_create(url=url)
                    event.sources.add(source_obj)

                for name in ev.categories or []:
                    category, _ = Category.objects.get_or_create(name=name)
                    event.categories.add(category)

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


@router.post("/create", response=List[TimelineCreatedEvent])
def create_topic_events(request, payload: TimelineCreateRequest):
    """Relate selected events to the topic as TopicEvents."""

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

        TopicEvent.objects.get_or_create(
            topic=topic,
            event=event,
            defaults={"source": "agent", "created_by": user},
        )

        created.append(
            TimelineCreatedEvent(
                uuid=str(event.uuid), title=event.title, date=event.date
            )
        )

    return created

