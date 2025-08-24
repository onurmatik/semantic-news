from datetime import date
from typing import List

from django.db.models import F, Value
from ninja import NinjaAPI, Schema
from openai import OpenAI
from pgvector.django import CosineDistance

from .models import Event


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
    """Response containing the confidence score that the event happened."""

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

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "event_validation",
            "schema": EventValidationResponse.model_json_schema(),
        },
    }

    with OpenAI() as client:
        response = client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
            response_format=response_format,
        )

    result = response.output[0].content[0].json
    return result


class EventCreateRequest(Schema):
    """Request body for creating a new event."""

    title: str
    date: date


class EventCreateResponse(Schema):
    """Response returned after creating an event."""

    uuid: str
    title: str
    date: date
    url: str


@api.post("/create", response=EventCreateResponse)
def create_event(request, payload: EventCreateRequest):
    """Create a new agenda event."""

    event = Event.objects.create(
        title=payload.title,
        date=payload.date,
        created_by=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
    )

    return EventCreateResponse(
        uuid=str(event.uuid),
        title=event.title,
        date=event.date,
        url=event.get_absolute_url(),
    )


class AgendaEventResponse(Schema):
    """Schema for suggested agenda events."""

    title: str
    date: date


@api.get("/suggest", response=List[AgendaEventResponse])
def suggest_events(
    request,
    year: int,
    month: int | None = None,
    day: int | None = None,
    locality: str | None = None,
    limit: int = 10,
):
    """Return suggested important events for a given period."""

    if month is None:
        timeframe = f"in {year}"
    elif day is None:
        timeframe = f"in {year}-{month:02d}"
    else:
        timeframe = f"on {year}-{month:02d}-{day:02d}"

    if locality:
        timeframe += f" in {locality}"

    prompt = (
        f"List the top {limit} most significant events {timeframe}. "
        "Return a JSON array where each item has 'title' and 'date' in ISO format (YYYY-MM-DD)."
    )

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "agenda_suggestions",
            "schema": {
                "type": "array",
                "items": AgendaEventResponse.model_json_schema(),
            },
        },
    }

    with OpenAI() as client:
        response = client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
            response_format=response_format,
        )

    events = response.output[0].content[0].json
    return [AgendaEventResponse(**event) for event in events]

