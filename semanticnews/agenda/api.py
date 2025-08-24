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
    date: date
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
            date=entry.date,
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

    result = response.output[0].content[0].model_dump_json()
    return result

