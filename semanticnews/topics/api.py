from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from typing import Optional

from semanticnews.agenda.models import Event

from .models import Topic, TopicEvent

api = NinjaAPI(title="Topics API")


class TopicCreateRequest(Schema):
    """Request body for creating a topic.

    Attributes:
        title (str): Title of the topic.
    """

    title: str


class TopicCreateResponse(Schema):
    """Response returned after creating a topic.

    Attributes:
        uuid (str): Unique identifier of the topic.
        title (str): Title of the topic.
        slug (str): Slug for the topic.
    """

    uuid: str
    title: str
    slug: str


@api.post("/create", response=TopicCreateResponse)
def create_topic(request, payload: TopicCreateRequest):
    """Create a new topic for the authenticated user.

    Args:
        request: The HTTP request instance.
        payload: Data including the topic title.

    Returns:
        Data for the newly created topic.
    """

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    topic = Topic.objects.create(title=payload.title, created_by=user)

    return TopicCreateResponse(uuid=str(topic.uuid), title=topic.title, slug=topic.slug)


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
