from datetime import date
from typing import List
import json

from django.db.models import F, Value
from ninja import NinjaAPI, Schema
from openai import OpenAI
from pgvector.django import CosineDistance

from .models import Event


CONFIDENCE_THRESHOLD = 0.85


api = NinjaAPI(title="Agenda API")


class EntryCheckRequest(Schema):
    """Request body for agenda entry checks."""

    title: str
    date: date
    threshold: float = 0.8


class SimilarEntryResponse(Schema):
    """Similar entry data returned by the API."""

    uuid: str
    title: str
    slug: str
    date: date
    url: str
    similarity: float


@api.post("/get-similar", response=List[SimilarEntryResponse])
def get_similar(request, payload: EntryCheckRequest):
    """Check whether an agenda entry already exists.

    The endpoint creates an embedding based on the entry's title and date
    (title + month + year) and compares it against existing agenda entries
    using cosine similarity. Entries with a similarity greater than the
    defined threshold are returned, ordered by similarity.
    """

    embedding_input = f"{payload.title} {payload.date:%B} {payload.date:%Y}"

    with OpenAI() as client:
        embedding = client.embeddings.create(
            model="text-embedding-3-small",
            input=embedding_input,
        ).data[0].embedding

    queryset = (
        Event.objects.exclude(embedding__isnull=True)
        .annotate(distance=CosineDistance("embedding", embedding))
        .annotate(similarity=Value(1.0) - F("distance"))
        .filter(similarity__gte=payload.threshold)
        .order_by("-similarity")
    )

    return [
        SimilarEntryResponse(
            uuid=str(entry.uuid),
            title=entry.title,
            slug=entry.slug,
            date=entry.date,
            url=entry.get_absolute_url(),
            similarity=entry.similarity,
        )
        for entry in queryset
    ]


class EventValidationRequest(Schema):
    """Request body for agenda event validation."""

    title: str
    date: date


class EventValidationResponse(Schema):
    """Response containing the confidence score that the event happened at the given date."""

    confidence: float


@api.post("/validate", response=EventValidationResponse)
def validate_event(request, payload: EventValidationRequest):
    """Validate that the topic describes an event that occurred on the given date."""
    prompt = (
        f"Does the following describe an event or incident that occurred on {payload.date:%Y-%m-%d}?\n"
        f"Title: {payload.title}\n"
        "Return a JSON object with a single field 'confidence' between 0 and 1 representing how confident you are that the"
        " event happened on that date."
    )

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
            text_format=EventValidationResponse,
        )

    return response.output_parsed


class EventCreateRequest(Schema):
    """Request body for creating a new event."""

    title: str
    date: date
    confidence: float | None = None


class EventCreateResponse(Schema):
    """Response returned after creating an event."""

    uuid: str
    title: str
    date: date
    url: str
    confidence: float | None


@api.post("/create", response=EventCreateResponse)
def create_event(request, payload: EventCreateRequest):
    """Create a new agenda event."""

    status = (
        "published"
        if payload.confidence is not None and payload.confidence >= CONFIDENCE_THRESHOLD
        else "draft"
    )

    event = Event.objects.create(
        title=payload.title,
        date=payload.date,
        confidence=payload.confidence,
        status=status,
        created_by=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
    )

    return EventCreateResponse(
        uuid=str(event.uuid),
        title=event.title,
        date=event.date,
        url=event.get_absolute_url(),
        confidence=event.confidence,
    )


class AgendaEventResponse(Schema):
    """Schema for suggested agenda events."""

    title: str
    date: date
    categories: List[str] = []


class AgendaEventList(Schema):
    """Schema for suggested agenda events."""

    event_list: List[AgendaEventResponse] = []


@api.get("/suggest", response=AgendaEventList)
def suggest_events(
    request,
    start_date: date | None = None,
    end_date: date | None = None,
    locality: str | None = None,
    categories: str | None = None,
    limit: int = 10,
    exclude: AgendaEventList | None = None,
):
    """Return suggested important events for a given period.

    Args:
        exclude: Optional list of events to omit from the suggestions.
        categories: Optional comma-separated list of categories to focus on.
    """

    if start_date and end_date:
        if start_date == end_date:
            timeframe = f"on {start_date:%Y-%m-%d}"
        else:
            timeframe = (
                f"between {start_date:%Y-%m-%d} and {end_date:%Y-%m-%d}"
            )
    elif start_date:
        timeframe = f"on {start_date:%Y-%m-%d}"
    elif end_date:
        timeframe = f"until {end_date:%Y-%m-%d}"
    else:
        timeframe = "recently"

    if locality:
        timeframe += f" in {locality}"
    if categories:
        timeframe += f" about {categories}"

    prompt = (
        f"List the top {limit} most significant events {timeframe}. "
        "Return a JSON array where each item has 'title', 'date' in ISO format (YYYY-MM-DD), "
        "and 'categories' as an array of 1-3 high-level categories."
    )

    if exclude:
        excluded_events = "\n".join(
            f"- {e.title} on {e.date.isoformat()}" for e in exclude
        )
        prompt += "\nExclude the following already known events:\n" + excluded_events

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
            text_format=AgendaEventList,
        )

    return response.output_parsed
