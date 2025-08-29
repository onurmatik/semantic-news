from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from typing import Optional

from asgiref.sync import async_to_sync

from semanticnews.agenda.models import Event

from .models import Topic, TopicEvent
from .agents import TopicRecapAgent
from .utils.recaps.models import TopicRecap

api = NinjaAPI(title="Topics API", urls_namespace="topics")


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


class TopicRecapCreateRequest(Schema):
    """Request body for creating a recap for a topic.

    Attributes:
        topic_uuid (str): UUID of the topic to recap.
    """

    topic_uuid: str


class TopicRecapCreateResponse(Schema):
    """Response returned after creating a recap."""

    recap: str


@api.post("/recap/create", response=TopicRecapCreateResponse)
def create_recap(request, payload: TopicRecapCreateRequest):
    """Generate and store a recap for a topic using OpenAI."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    # Build context from related events and contents
    content_md = f"# {topic.title}\n\n"

    events = topic.events.all()
    if events:
        content_md += "## Events\n\n"
        for event in events:
            content_md += f"- {event.title} ({event.date})\n"

    contents = topic.contents.all()
    if contents:
        content_md += "\n## Contents\n\n"
        for c in contents:
            title = c.title or ""
            text = c.markdown or ""
            content_md += f"### {title}\n{text}\n\n"

    agent = TopicRecapAgent()
    response = async_to_sync(agent.run)(content_md)
    recap_text = response.recap_en

    TopicRecap.objects.create(topic=topic, recap=recap_text)

    return TopicRecapCreateResponse(recap=recap_text)
