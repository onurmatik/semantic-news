from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from typing import Optional, List, Literal
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

from semanticnews.agenda.models import Event
from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

from .models import Topic
from .utils.timeline.models import TopicEvent
from .utils.timeline.api import router as timeline_router
from .utils.recaps.api import router as recaps_router
from .utils.narratives.api import router as narratives_router
from .utils.mcps.api import router as mcps_router
from .utils.images.api import router as images_router
from .utils.embeds.api import router as embeds_router
from .utils.relations.api import router as relations_router
from .utils.data.api import router as data_router
from .utils.documents.api import router as documents_router

api = NinjaAPI(title="Topics API", urls_namespace="topics")
api.add_router("/recap", recaps_router)
api.add_router("/narrative", narratives_router)
api.add_router("/mcp", mcps_router)
api.add_router("/image", images_router)
api.add_router("/embed", embeds_router)
api.add_router("/relation", relations_router)
api.add_router("/data", data_router)
api.add_router("/document", documents_router)
api.add_router("/timeline", timeline_router)

StatusLiteral = Literal["in_progress", "finished", "error"]


class GenerationStatus(Schema):
    status: Optional[StatusLiteral] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class GenerationStatusResponse(Schema):
    current: datetime
    recap: Optional[GenerationStatus] = None
    narrative: Optional[GenerationStatus] = None
    relation: Optional[GenerationStatus] = None
    image: Optional[GenerationStatus] = None


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

    return GenerationStatusResponse(
        current=timezone.now(),
        recap=latest(topic.recaps),
        narrative=latest(topic.narratives),
        relation=latest(topic.entity_relations),
        image=latest(topic.images),
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

    if payload.status == "published" and not topic.title:
        raise HttpError(400, "A title is required to publish a topic.")

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
    topic.save(update_fields=["title"])

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


class TopicEventAddRequest(Schema):
    """Request body for adding an agenda event to a topic.

    Attributes:
        topic_uuid (str): UUID of the topic.
        event_uuid (str): UUID of the agenda event.
        role (str): Role of the event within the topic (support, counter, context).
    """

    topic_uuid: str
    event_uuid: str
    role: Optional[str] = "support"


class TopicEventAddResponse(Schema):
    """Response returned after adding an event to a topic.

    Attributes:
        topic_uuid (str): UUID of the topic.
        event_uuid (str): UUID of the agenda event.
        role (str): Role assigned to the event within the topic.
    """

    topic_uuid: str
    event_uuid: str
    role: str


@api.post("/add-event", response=TopicEventAddResponse)
def add_event_to_topic(request, payload: TopicEventAddRequest):
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

    topic_event, created = TopicEvent.objects.get_or_create(
        topic=topic,
        event=event,
        defaults={"role": payload.role, "created_by": user},
    )

    if not created:
        raise HttpError(400, "Event already linked to topic")

    return TopicEventAddResponse(
        topic_uuid=str(topic.uuid),
        event_uuid=str(event.uuid),
        role=topic_event.role,
    )


class TopicEventRemoveRequest(Schema):
    """Request body for removing an agenda event from a topic.

    Attributes:
        topic_uuid (str): UUID of the topic.
        event_uuid (str): UUID of the agenda event.
    """

    topic_uuid: str
    event_uuid: str


class TopicEventRemoveResponse(Schema):
    """Response returned after removing an event from a topic.

    Attributes:
        topic_uuid (str): UUID of the topic.
        event_uuid (str): UUID of the agenda event.
    """

    topic_uuid: str
    event_uuid: str


@api.post("/remove-event", response=TopicEventRemoveResponse)
def remove_event_from_topic(request, payload: TopicEventRemoveRequest):
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

    deleted, _ = TopicEvent.objects.filter(topic=topic, event=event).delete()
    if deleted == 0:
        raise HttpError(404, "Event not linked to topic")

    return TopicEventRemoveResponse(
        topic_uuid=str(topic.uuid),
        event_uuid=str(event.uuid),
    )


class TopicSuggestionList(Schema):
    """Schema representing a list of suggested topic titles."""

    topics: List[str] = []


class SuggestTopicsRequest(Schema):
    """Request body for suggesting topics based on a description.

    Attributes:
        about (str): Description of the subject to suggest topics about.
        limit (int): Maximum number of topics to return. Defaults to ``3``.
    """

    about: str
    limit: int = 3


def suggest_topics(about: str, limit: int = 3) -> List[str]:
    """Return a list of suggested topics for a given description."""

    prompt = (
        f"Suggest {limit} topic ideas about {about}. "
        f"Each topic should be a short, broad phrase in nominalized passive form. "
        f"Avoid overly specific or literal restatements of the subject. "
        f"Make the {limit} suggestions vary in scope, but none too specific. "
    )
    prompt = append_default_language_instruction(prompt)

    with OpenAI() as client:
        response = client.responses.parse(
            model=settings.DEFAULT_AI_MODEL,
            input=prompt,
            text_format=TopicSuggestionList,
        )

    return response.output_parsed.topics


@api.get("/suggest", response=List[str])
def suggest_topics_get(request, about: str, limit: int = 3):
    """Return suggested topics for a description via GET."""

    return suggest_topics(about=about, limit=limit)


@api.post("/suggest", response=List[str])
def suggest_topics_post(request, payload: SuggestTopicsRequest):
    """Return suggested topics for a description via POST."""

    return suggest_topics(about=payload.about, limit=payload.limit)


