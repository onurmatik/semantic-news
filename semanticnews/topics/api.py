from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from typing import Optional, List, Literal
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.db import transaction
from django.core.exceptions import ValidationError

from semanticnews.agenda.models import Event
from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

from .models import Topic, TopicModuleLayout
from .layouts import (
    ALLOWED_PLACEMENTS,
    MODULE_REGISTRY,
    get_topic_layout,
    serialize_layout,
    _split_module_key,
)
from .utils.timeline.models import TopicEvent
from .utils.timeline.api import router as timeline_router
from .utils.recaps.api import router as recaps_router
from .utils.mcps.api import router as mcps_router
from .utils.images.api import router as images_router
from .utils.embeds.api import router as embeds_router
from .utils.relations.api import router as relations_router
from .utils.data.api import router as data_router
from .utils.documents.api import router as documents_router
from .utils.text.api import router as text_router

api = NinjaAPI(title="Topics API", urls_namespace="topics")
api.add_router("/recap", recaps_router)
api.add_router("/text", text_router)
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
    text: Optional[GenerationStatus] = None
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
        text=latest(topic.texts),
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
        published_at (datetime | None): Timestamp of the most recent publication.
    """

    topic_uuid: str
    status: str
    published_at: Optional[datetime] = None


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


class TopicLayoutModule(Schema):
    """Schema describing a single module layout entry."""

    module_key: str
    placement: Literal["primary", "sidebar"]
    display_order: int


class TopicLayoutResponse(Schema):
    """Response wrapper for a topic layout."""

    modules: List[TopicLayoutModule]


class TopicLayoutUpdateRequest(Schema):
    """Payload for updating a topic's module layout."""

    modules: List[TopicLayoutModule]


class TopicMetadataResponse(Schema):
    """Metadata about a topic for editor UI consumption."""

    topic_uuid: str
    status: str
    published_at: Optional[datetime] = None


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

    if payload.status == "published":
        try:
            topic.publish()
        except ValidationError as exc:
            errors = []
            for messages in exc.message_dict.values():
                errors.extend(messages)
            detail = "; ".join(errors) if errors else "Unable to publish topic."
            raise HttpError(400, detail)

        return TopicStatusUpdateResponse(
            topic_uuid=str(topic.uuid),
            status=topic.status,
            published_at=topic.published_at,
        )

    topic.status = payload.status
    topic.save(update_fields=["status"])

    return TopicStatusUpdateResponse(
        topic_uuid=str(topic.uuid),
        status=topic.status,
        published_at=topic.published_at,
    )


@api.get("/{topic_uuid}/metadata", response=TopicMetadataResponse)
def get_topic_metadata(request, topic_uuid: str):
    """Return publication metadata for the authenticated owner's topic."""

    topic = _get_owned_topic(request, topic_uuid)
    publication = topic.current_publication
    published_at = None
    if publication is not None:
        published_at = publication.published_at or topic.published_at
    elif topic.published_at:
        published_at = topic.published_at

    return TopicMetadataResponse(
        topic_uuid=str(topic.uuid),
        status=topic.status,
        published_at=published_at,
    )


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


def _get_owned_topic(request, topic_uuid: str) -> Topic:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by != user:
        raise HttpError(403, "Forbidden")

    return topic


def _validate_layout_modules(modules: List[TopicLayoutModule]) -> List[dict]:
    validated: List[dict] = []
    seen_keys = set()

    for index, module in enumerate(modules):
        key = module.module_key
        base_key, identifier = _split_module_key(key)
        if base_key not in MODULE_REGISTRY:
            raise HttpError(400, f"Unknown module key: {key}")
        if base_key in {"text", "data_visualizations"} and not identifier:
            raise HttpError(400, f"{base_key.replace('_', ' ').title()} modules must include an identifier")
        if key in seen_keys:
            raise HttpError(400, f"Duplicate module key: {key}")
        seen_keys.add(key)

        if module.placement not in ALLOWED_PLACEMENTS:
            raise HttpError(400, f"Invalid placement: {module.placement}")

        if module.display_order < 0:
            raise HttpError(400, "Display order must be non-negative")

        validated.append(
            {
                "module_key": key,
                "placement": module.placement,
                "display_order": module.display_order if module.display_order is not None else index,
            }
        )

    return validated


@api.get("/{topic_uuid}/layout", response=TopicLayoutResponse)
def get_topic_layout_configuration(request, topic_uuid: str):
    """Return the saved module layout for the authenticated owner."""

    topic = _get_owned_topic(request, topic_uuid)
    layout = get_topic_layout(topic)
    return TopicLayoutResponse(modules=serialize_layout(layout))


@api.put("/{topic_uuid}/layout", response=TopicLayoutResponse)
def update_topic_layout_configuration(
    request, topic_uuid: str, payload: TopicLayoutUpdateRequest
):
    """Persist a custom module layout for the authenticated owner."""

    topic = _get_owned_topic(request, topic_uuid)
    validated_modules = _validate_layout_modules(payload.modules)

    with transaction.atomic():
        TopicModuleLayout.objects.filter(topic=topic).delete()
        TopicModuleLayout.objects.bulk_create(
            [
                TopicModuleLayout(
                    topic=topic,
                    module_key=module["module_key"],
                    placement=module["placement"],
                    display_order=module["display_order"],
                )
                for module in validated_modules
            ]
        )

    layout = get_topic_layout(topic)
    return TopicLayoutResponse(modules=serialize_layout(layout))


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


