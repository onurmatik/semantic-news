from datetime import date
from typing import List, Optional
import json

from django.db.models import F, Value
from ninja import NinjaAPI, Schema
from semanticnews.openai import OpenAI
from pgvector.django import CosineDistance

from .models import Event, Source, Category


CONFIDENCE_THRESHOLD = 0.85


api = NinjaAPI(title="Agenda API")


class SimilarEntryRequest(Schema):
    """Request body for agenda entry checks.

    Attributes:
        title (str): Title of the agenda entry to check.
        date (date): Date of the agenda entry.
        threshold (float): Minimum similarity score required to include an entry.
    """

    title: str
    date: date
    threshold: float = 0.8


class SimilarEntryResponse(Schema):
    """Similar entry data returned by the API.

    Attributes:
        uuid (str): Unique identifier of the existing event.
        title (str): Title of the similar event.
        slug (str): Slug of the event.
        date (date): Date of the similar event in ISO format (YYYY-MM-DD).
        url (str): Absolute URL for the event.
        similarity (float): Cosine similarity score between 0 and 1.
    """

    uuid: str
    title: str
    slug: str
    date: date
    url: str
    similarity: float


@api.post("/get-similar", response=List[SimilarEntryResponse])
def get_similar(request, payload: SimilarEntryRequest):
    """Get a list of already existing events in the DB, similar to the given event.

    The endpoint creates an embedding based on the entry's title and date
    (title + month + year) and compares it against existing agenda entries
    using cosine similarity. Entries with a similarity greater than the
    defined threshold are returned, ordered by similarity.

    Args:
        request: The HTTP request instance.
        payload: Data including the entry title, date and similarity threshold.

    Returns:
        A list of entries similar to the provided payload ordered by similarity.
    """

    embedding_input = f"{payload.title} {payload.date:%B} {payload.date:%Y}"

    with OpenAI() as client:
        embedding = (
            client.embeddings.create(
                model="text-embedding-3-small",
                input=embedding_input,
            )
            .data[0]
            .embedding
        )

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


class ExistingEntryRequest(Schema):
    """Request body for checking if an identical event exists.

    Attributes:
        title (str): Title of the agenda entry to check.
        date (date): Date of the agenda entry.
    """

    title: str
    date: date


class ExistingEntryResponse(Schema):
    """Response indicating whether an identical event exists."""

    existing: str | None


SIMILARITY_DUPLICATE_THRESHOLD = 0.95


@api.post("/get-existing", response=ExistingEntryResponse)
def get_existing(request, payload: ExistingEntryRequest):
    """Return an existing event matching by semantic similarity.

    The endpoint embeds the requested title with the month and year and
    compares it against existing events. The most similar event above the
    ``SIMILARITY_DUPLICATE_THRESHOLD`` is returned, allowing detection of
    duplicates even when titles are not identical.
    """

    embedding_input = f"{payload.title} {payload.date:%B} {payload.date:%Y}"

    with OpenAI() as client:
        embedding = client.embeddings.create(
            model="text-embedding-3-small",
            input=embedding_input,
        ).data[0].embedding

    event = (
        Event.objects.exclude(embedding__isnull=True)
        .annotate(distance=CosineDistance("embedding", embedding))
        .annotate(similarity=Value(1.0) - F("distance"))
        .filter(similarity__gte=SIMILARITY_DUPLICATE_THRESHOLD)
        .order_by("-similarity")
        .first()
    )

    return ExistingEntryResponse(existing=str(event.uuid) if event else None)


class EventValidationRequest(Schema):
    """Request body for agenda event validation.

    Attributes:
        title (str): Title describing the event.
        date (date): Date the event is claimed to have occurred.
    """

    title: str
    date: date


class EventValidationResponse(Schema):
    """Response containing details for creating an agenda event.

    Attributes:
        confidence (float): Confidence between 0 and 1 that the event occurred on the specified date.
        sources (List[str]): A few source URLs supporting the event.
        categories (List[str]): 1-3 high-level categories describing the event.
        title (str): Event title as a neutral, concise factual statement.
        date (date): Event date; might be corrected, if slightly different from the provided date.
    """
    "Generate event titles as concise factual statements. "
    "State the core fact directly and neutrally avoid newspaper-style headlines. "
    "For each event, include 1-2 source URLs as citations. "

    confidence: float
    sources: List[str] = []
    categories: List[str] = []
    title: str
    date: date


@api.post("/validate", response=EventValidationResponse)
def validate_event(request, payload: EventValidationRequest):
    """Validate that the topic describes an event that occurred on the given date."""

    prompt = (
        f"Does the following describe an event or incident that occurred on {payload.date:%Y-%m-%d}?\n"
        f"Title: {payload.title}\n"
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
    """Request body for creating a new event.

    Attributes:
        title (str): Title of the event.
        date (date): Date when the event occurred.
        confidence (float | None): Confidence score associated with the
            event.
        sources (List[str] | None): Source URLs supporting the event.
        categories (List[str] | None): Category names describing the event.
    """

    title: str
    date: date
    confidence: float | None = None
    sources: List[str] | None = None
    categories: List[str] | None = None


class EventCreateResponse(Schema):
    """Response returned after creating an event.

    Attributes:
        uuid (str): Unique identifier of the created event.
        title (str): Title of the event.
        date (date): Date when the event occurred.
        url (str): Absolute URL of the event.
        confidence (float | None): Confidence score of the event.
    """

    uuid: str
    title: str
    date: date
    url: str
    confidence: float | None


@api.post("/create", response=EventCreateResponse)
def create_event(request, payload: EventCreateRequest):
    """Create a new agenda event.

    Args:
        request: The HTTP request instance.
        payload: Event data including title, date and optional confidence.

    Returns:
        Data for the newly created event.
    """

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
        created_by=(
            request.user
            if getattr(request, "user", None) and request.user.is_authenticated
            else None
        ),
    )

    if payload.sources:
        for url in payload.sources:
            source_obj, _ = Source.objects.get_or_create(url=url)
            event.sources.add(source_obj)

    if payload.categories:
        for name in payload.categories:
            category, _ = Category.objects.get_or_create(name=name)
            event.categories.add(category)

    # Recompute embedding now that categories and sources are set
    event.embedding = event.get_embedding()
    if event.embedding is not None:
        event.save(update_fields=["embedding"])

    return EventCreateResponse(
        uuid=str(event.uuid),
        title=event.title,
        date=event.date,
        url=event.get_absolute_url(),
        confidence=event.confidence,
    )


class PublishEventsRequest(Schema):
    """Request body for publishing draft events."""

    uuids: List[str]


class PublishEventsResponse(Schema):
    """Response containing the number of events published."""

    updated: int


@api.post("/publish", response=PublishEventsResponse)
def publish_events(request, payload: PublishEventsRequest):
    """Set the status of the given events to published."""

    events = Event.objects.filter(uuid__in=payload.uuids)
    updated = events.update(status="published")
    return PublishEventsResponse(updated=updated)


class AgendaEventResponse(Schema):
    """Schema for suggested agenda events.

    Attributes:
        title (str): Title of the event. Avoid newspaper heading style and state the core fact directly and neutrally.
        date (date): Date of the event in ISO format (YYYY-MM-DD).
        categories (List[str]): 1-3 high-level categories describing the event.
        sources (List[str]): Source URLs supporting the event.
    """

    title: str
    date: date
    categories: List[str] = []
    sources: List[str] = []


class AgendaEventList(Schema):
    """Schema for a list of suggested agenda events.

    Attributes:
        event_list (List[AgendaEventResponse]): Suggested agenda events.
    """

    event_list: List[AgendaEventResponse] = []


class SuggestEventsRequest(Schema):
    """Request body for suggesting agenda events.

    Attributes:
        start_date (date | None): Earliest date to consider.
        end_date (date | None): Latest date to consider.
        locality (str | None): Geographic context for events.
        categories (str | None): Categories to filter events.
        related_event (str | None): Event to which suggestions should be
            related.
        limit (int): Maximum number of events to return. Defaults to ``10``.
        exclude (List[AgendaEventResponse] | None): Events to omit from
            suggestions.
    """

    start_date: date | None = None
    end_date: date | None = None
    locality: str | None = None
    categories: str | None = None
    related_event: str | None = None
    limit: int = 10
    exclude: List[AgendaEventResponse] | None = None


def suggest_events(
    start_date: date | None = None,
    end_date: date | None = None,
    locality: str | None = None,
    categories: str | None = None,
    related_event: str | None = None,
    limit: int = 10,
    exclude: List[AgendaEventResponse] | None = None,
):
    """Core logic for returning suggested important events."""

    if start_date and end_date:
        if start_date == end_date:
            timeframe = f"on {start_date:%Y-%m-%d}"
        else:
            timeframe = f"between {start_date:%Y-%m-%d} and {end_date:%Y-%m-%d}"
    elif start_date:
        timeframe = f"since {start_date:%Y-%m-%d}"
    elif end_date:
        timeframe = f"until {end_date:%Y-%m-%d}"
    else:
        timeframe = "recently"

    if locality:
        timeframe += f" in {locality}"
    if categories:
        timeframe += f" about {categories}"

    descriptor_parts = []
    if related_event:
        descriptor_parts.append(f'related to "{related_event}"')
    descriptor_parts.append(timeframe)
    descriptor = " ".join(descriptor_parts)

    prompt = f"List the top {limit} most significant events {descriptor}."

    # Style guide
    prompt += (
        "Generate event titles as concise factual statements. "
        "State the core fact directly and neutrally avoid newspaper-style headlines. "
        "For each event, include a few source URLs as citations. "
    )

    if exclude:
        excluded_events = "\n".join(
            f"- {e.title} on {e.date.isoformat()}" for e in exclude
        )
        prompt += "\nDo not include the following events:\n" + excluded_events

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
            text_format=AgendaEventList,
        )

    return response.output_parsed.event_list


@api.get("/suggest", response=List[AgendaEventResponse])
def suggest_events_get(
    request,
    start_date: date | None = None,
    end_date: date | None = None,
    locality: str | None = None,
    categories: str | None = None,
    related_event: str | None = None,
    limit: int = 10,
    exclude: List[AgendaEventResponse] | None = None,
):
    """Return suggested important events for a given period via GET.

    Args:
        request: The HTTP request instance.
        start_date: Start of the period to search.
        end_date: End of the period to search.
        locality: Geographic area to consider.
        categories: Categories to filter events.
        related_event: Event the suggestions should be related to.
        limit: Maximum number of events to return.
        exclude: Events to exclude from the results.

    Returns:
        A list of suggested events for the specified timeframe.
    """

    return suggest_events(
        start_date=start_date,
        end_date=end_date,
        locality=locality,
        categories=categories,
        related_event=related_event,
        limit=limit,
        exclude=exclude,
    )


@api.post("/suggest", response=List[AgendaEventResponse])
def suggest_events_post(request, payload: SuggestEventsRequest):
    """Return suggested important events for a given period via POST.

    Args:
        request: The HTTP request instance.
        payload: Parameters defining the event search.

    Returns:
        A list of suggested events for the specified timeframe.
    """

    return suggest_events(
        start_date=payload.start_date,
        end_date=payload.end_date,
        locality=payload.locality,
        categories=payload.categories,
        related_event=payload.related_event,
        limit=payload.limit,
        exclude=payload.exclude,
    )
