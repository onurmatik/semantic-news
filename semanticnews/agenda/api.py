from datetime import date
from typing import List

from django.db.models import F, Value
from ninja import NinjaAPI, Schema
from openai import OpenAI
from pgvector.django import CosineDistance

from .models import Entry


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


@api.post("/check-similarity", response=List[SimilarEntryResponse])
def check_similarity(request, payload: EntryCheckRequest):
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
        Entry.objects.exclude(embedding__isnull=True)
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

