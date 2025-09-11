"""API endpoints for timeline event suggestions and creation."""

from datetime import date
from typing import List, Optional

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from ....agenda.models import Category, Event, Source
from .models import TopicEvent
from ....openai import OpenAI


router = Router()


class TimelineSuggestedEvent(Schema):
    """Schema representing an event suggested by the AI."""

    title: str
    date: date
    categories: List[str] = []
    sources: List[str] = []


class TimelineEventList(Schema):
    """Wrapper for a list of timeline events."""

    events: List[TimelineSuggestedEvent] = []


class TimelineSuggestRequest(Schema):
    """Request body for suggesting events for a topic timeline."""

    topic_uuid: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    locality: Optional[str] = None
    related_event: Optional[str] = None
    limit: int = 5


@router.post("/suggest", response=List[TimelineSuggestedEvent])
def suggest_topic_events(request, payload: TimelineSuggestRequest):
    """Return AI-suggested events related to a topic."""

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

    context = topic.build_context()
    if context:
        prompt += "\n\nContext:\n" + context

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
            text_format=TimelineEventList,
        )

    return response.output_parsed.events


class TimelineCreateRequest(Schema):
    """Request body for creating selected suggested events."""

    topic_uuid: str
    events: List[TimelineSuggestedEvent]


class TimelineCreatedEvent(Schema):
    """Data returned for an event created from suggestions."""

    uuid: str
    title: str
    date: date


@router.post("/create", response=List[TimelineCreatedEvent])
def create_topic_events(request, payload: TimelineCreateRequest):
    """Create events from AI suggestions and relate them to the topic."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    created: List[TimelineCreatedEvent] = []
    for ev in payload.events:
        event = Event.objects.create(
            title=ev.title,
            date=ev.date,
            status="published",
            created_by=user,
        )

        for url in ev.sources or []:
            source_obj, _ = Source.objects.get_or_create(url=url)
            event.sources.add(source_obj)

        for name in ev.categories or []:
            category, _ = Category.objects.get_or_create(name=name)
            event.categories.add(category)

        event.embedding = event.get_embedding()
        if event.embedding is not None:
            event.save(update_fields=["embedding"])

        TopicEvent.objects.create(
            topic=topic,
            event=event,
            source="agent",
            created_by=user,
        )

        created.append(
            TimelineCreatedEvent(
                uuid=str(event.uuid), title=event.title, date=event.date
            )
        )

    return created

