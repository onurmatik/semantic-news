from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from typing import Optional, List, Literal
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.db import transaction
from django.db.models import Q

from semanticnews.agenda.models import Event
from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

from .models import Topic, TopicModuleLayout, RelatedTopic
from .publishing.service import publish_topic
from .layouts import (
    ALLOWED_PLACEMENTS,
    MODULE_REGISTRY,
    REORDERABLE_BASE_MODULES,
    get_topic_layout,
    serialize_layout,
    _split_module_key,
)
from semanticnews.widgets.timeline.models import TopicEvent
from semanticnews.widgets.timeline.api import router as timeline_router
from semanticnews.widgets.recaps.api import router as recaps_router
from semanticnews.widgets.mcps.api import router as mcps_router
from semanticnews.widgets.images.api import router as images_router
from semanticnews.widgets.embeds.api import router as embeds_router
from semanticnews.widgets.relations.api import router as relations_router
from semanticnews.widgets.data.api import router as data_router
from semanticnews.widgets.documents.api import router as documents_router
from semanticnews.widgets.text.api import router as text_router
from semanticnews.widgets.data.models import (
    TopicDataRequest,
    TopicDataAnalysisRequest,
    TopicDataVisualizationRequest,
)

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


class DataGenerationStatuses(Schema):
    add: Optional[GenerationStatus] = None
    analyze: Optional[GenerationStatus] = None
    visualize: Optional[GenerationStatus] = None


class GenerationStatusResponse(Schema):
    current: datetime
    recap: Optional[GenerationStatus] = None
    text: Optional[GenerationStatus] = None
    relation: Optional[GenerationStatus] = None
    image: Optional[GenerationStatus] = None
    data: Optional[DataGenerationStatuses] = None


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

    data_status_map = {
        TopicDataRequest.Status.PENDING: "in_progress",
        TopicDataRequest.Status.STARTED: "in_progress",
        TopicDataRequest.Status.SUCCESS: "finished",
        TopicDataRequest.Status.FAILURE: "error",
        TopicDataAnalysisRequest.Status.PENDING: "in_progress",
        TopicDataAnalysisRequest.Status.STARTED: "in_progress",
        TopicDataAnalysisRequest.Status.SUCCESS: "finished",
        TopicDataAnalysisRequest.Status.FAILURE: "error",
        TopicDataVisualizationRequest.Status.PENDING: "in_progress",
        TopicDataVisualizationRequest.Status.STARTED: "in_progress",
        TopicDataVisualizationRequest.Status.SUCCESS: "finished",
        TopicDataVisualizationRequest.Status.FAILURE: "error",
    }

    def latest_data_status(qs):
        row = (
            qs.filter(user_id=user.id)
              .order_by("-updated_at")
              .values("status", "error_message", "created_at", "updated_at")
              .first()
        )
        if not row:
            return None
        mapped = data_status_map.get(row.get("status"))
        if not mapped:
            return None
        timestamp = row.get("updated_at") or row.get("created_at")
        return {
            "status": mapped,
            "error_message": row.get("error_message"),
            "created_at": timestamp,
        }

    data_statuses = {
        "add": latest_data_status(topic.data_requests),
        "analyze": latest_data_status(topic.data_analysis_requests),
        "visualize": latest_data_status(topic.data_visualization_requests),
    }

    data_payload = (
        DataGenerationStatuses(**data_statuses)
        if any(data_statuses.values())
        else None
    )

    return GenerationStatusResponse(
        current=timezone.now(),
        recap=latest(topic.recaps.filter(is_deleted=False)),
        text=latest(topic.texts.filter(is_deleted=False)),
        relation=latest(topic.entity_relations.filter(is_deleted=False)),
        image=latest(topic.images.filter(is_deleted=False)),
        data=data_payload,
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
        is_republishing_archived_topic = (
            topic.status == "archived" and topic.latest_publication_id is not None
        )

        if is_republishing_archived_topic:
            topic.status = "published"
            topic.save(update_fields=["status"])
        else:
            if not topic.title:
                raise HttpError(400, "A title is required to publish a topic.")

            has_finished_recap = topic.recaps.filter(status="finished", is_deleted=False).exists()
            if not has_finished_recap:
                raise HttpError(400, "A recap is required to publish a topic.")

            publish_topic(topic, user)
    else:
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
        if base_key not in REORDERABLE_BASE_MODULES:
            readable_name = base_key.replace("_", " ")
            raise HttpError(400, f"{readable_name.title()} modules cannot be reordered")
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

    from .signals import touch_topic

    touch_topic(topic.pk)

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

    with transaction.atomic():
        topic_event, created = TopicEvent.objects.select_for_update().get_or_create(
            topic=topic,
            event=event,
            defaults={"role": payload.role, "created_by": user},
        )

        if not created:
            if topic_event.is_deleted:
                topic_event.is_deleted = False
                topic_event.role = payload.role
                topic_event.save(update_fields=["is_deleted", "role"])
            else:
                raise HttpError(400, "Event already linked to topic")

    from .signals import touch_topic

    touch_topic(topic.pk)

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

    updated = TopicEvent.objects.filter(
        topic=topic,
        event=event,
        is_deleted=False,
    ).update(is_deleted=True)
    if updated == 0:
        raise HttpError(404, "Event not linked to topic")

    from .signals import touch_topic

    touch_topic(topic.pk)

    return TopicEventRemoveResponse(
        topic_uuid=str(topic.uuid),
        event_uuid=str(event.uuid),
    )


class RelatedTopicLinkSchema(Schema):
    id: int
    topic_uuid: str
    title: Optional[str]
    slug: Optional[str]
    username: Optional[str]
    display_name: Optional[str]
    source: str
    is_deleted: bool
    created_at: datetime
    published_at: Optional[datetime]


class RelatedTopicSearchResult(Schema):
    uuid: str
    title: Optional[str]
    slug: Optional[str]
    username: Optional[str]
    is_already_linked: bool = False


class RelatedTopicCreateRequest(Schema):
    related_topic_uuid: str


def _require_owned_topic(request, topic_uuid: str) -> Topic:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    return topic


def _serialize_related_topic_link(link: RelatedTopic) -> RelatedTopicLinkSchema:
    related_topic = link.related_topic
    created_by = getattr(related_topic, "created_by", None)
    username = getattr(created_by, "username", None)
    display_name = None
    if created_by is not None:
        if hasattr(created_by, "get_full_name"):
            display_name = created_by.get_full_name() or None
        if not display_name:
            display_name = str(created_by)
    return RelatedTopicLinkSchema(
        id=link.id,
        topic_uuid=str(getattr(related_topic, "uuid", "")),
        title=getattr(related_topic, "title", None),
        slug=getattr(related_topic, "slug", None),
        username=username,
        display_name=display_name,
        source=link.source,
        is_deleted=link.is_deleted,
        created_at=link.created_at,
        published_at=link.published_at,
    )


@api.get("/{topic_uuid}/related-topics", response=List[RelatedTopicLinkSchema])
def list_related_topics(request, topic_uuid: str):
    topic = _require_owned_topic(request, topic_uuid)
    links = (
        RelatedTopic.objects.filter(topic=topic)
        .select_related("related_topic__created_by")
        .order_by("-created_at")
    )
    return [_serialize_related_topic_link(link) for link in links]


@api.get(
    "/{topic_uuid}/related-topics/search",
    response=List[RelatedTopicSearchResult],
)
def search_related_topics(request, topic_uuid: str, query: Optional[str] = None):
    topic = _require_owned_topic(request, topic_uuid)
    existing_links = {
        link.related_topic_id: link
        for link in RelatedTopic.objects.filter(topic=topic)
    }

    qs = (
        Topic.objects.filter(status="published")
        .exclude(uuid=topic.uuid)
        .select_related("created_by")
    )

    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(created_by__username__icontains=query)
        )

    qs = qs.order_by("-updated_at", "-created_at")[:10]

    results: List[RelatedTopicSearchResult] = []
    for result in qs:
        link = existing_links.get(result.id)
        results.append(
            RelatedTopicSearchResult(
                uuid=str(result.uuid),
                title=result.title,
                slug=result.slug,
                username=getattr(result.created_by, "username", None),
                is_already_linked=link is not None and not link.is_deleted,
            )
        )

    return results


@api.post(
    "/{topic_uuid}/related-topics",
    response=RelatedTopicLinkSchema,
)
def add_related_topic(
    request, topic_uuid: str, payload: RelatedTopicCreateRequest
):
    topic = _require_owned_topic(request, topic_uuid)

    try:
        related_topic = Topic.objects.get(uuid=payload.related_topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Related topic not found")

    if related_topic == topic:
        raise HttpError(400, "Cannot relate a topic to itself")

    link, created = RelatedTopic.objects.get_or_create(
        topic=topic,
        related_topic=related_topic,
        defaults={
            "source": RelatedTopic.Source.MANUAL,
            "created_by": request.user,
        },
    )

    if not created:
        if not link.is_deleted:
            raise HttpError(400, "Related topic already linked")

        update_fields = ["is_deleted", "updated_at"]
        link.is_deleted = False
        if link.source != RelatedTopic.Source.MANUAL:
            link.source = RelatedTopic.Source.MANUAL
            update_fields.append("source")
        if link.created_by_id != request.user.id:
            link.created_by = request.user
            update_fields.append("created_by")
        link.save(update_fields=update_fields)

    from .signals import touch_topic

    touch_topic(topic.pk)

    return _serialize_related_topic_link(link)


@api.delete(
    "/{topic_uuid}/related-topics/{link_id}",
    response=RelatedTopicLinkSchema,
)
def remove_related_topic(request, topic_uuid: str, link_id: int):
    topic = _require_owned_topic(request, topic_uuid)

    try:
        link = RelatedTopic.objects.select_related("related_topic").get(
            topic=topic,
            id=link_id,
        )
    except RelatedTopic.DoesNotExist:
        raise HttpError(404, "Related topic link not found")

    if not link.is_deleted:
        link.is_deleted = True
        link.save(update_fields=["is_deleted", "updated_at"])

    from .signals import touch_topic

    touch_topic(topic.pk)

    return _serialize_related_topic_link(link)


@api.post(
    "/{topic_uuid}/related-topics/{link_id}/restore",
    response=RelatedTopicLinkSchema,
)
def restore_related_topic(request, topic_uuid: str, link_id: int):
    topic = _require_owned_topic(request, topic_uuid)

    try:
        link = RelatedTopic.objects.select_related("related_topic").get(
            topic=topic,
            id=link_id,
        )
    except RelatedTopic.DoesNotExist:
        raise HttpError(404, "Related topic link not found")

    if link.is_deleted:
        link.is_deleted = False
        link.save(update_fields=["is_deleted", "updated_at"])

    from .signals import touch_topic

    touch_topic(topic.pk)

    return _serialize_related_topic_link(link)


class TopicSuggestionList(Schema):
    """Schema representing a list of suggested topic titles."""

    topics: List[str] = []


class SuggestTopicsRequest(Schema):
    """Request body for suggesting topics based on available information.

    Attributes:
        about (Optional[str]): Description of the subject to suggest topics about.
        limit (int): Maximum number of topics to return. Defaults to ``3``.
        topic_uuid (Optional[str]): UUID of an existing topic whose context should
            be used when generating suggestions.
    """

    about: Optional[str] = None
    limit: int = 3
    topic_uuid: Optional[str] = None


def _has_meaningful_context(context: str) -> bool:
    """Return ``True`` when the provided context contains useful content."""

    if not context:
        return False

    stripped = context.strip()
    if not stripped:
        return False

    # ``Topic.build_context`` always prefixes a markdown heading. Strip heading
    # characters to detect whether any substantive text remains.
    return bool(stripped.strip("# \n\t"))


def suggest_topics(
    *, about: Optional[str] = None, limit: int = 3, topic_uuid: Optional[str] = None
) -> List[str]:
    """Return a list of suggested topics for available context."""

    description = (about or "").strip()

    topic_context = ""
    if topic_uuid:
        try:
            topic = Topic.objects.get(uuid=topic_uuid)
        except Topic.DoesNotExist:
            raise HttpError(404, "Topic not found")
        topic_context = topic.build_context()

    context_parts = []
    if description:
        context_parts.append(f"Description:\n{description}")
    if _has_meaningful_context(topic_context):
        context_parts.append(f"Existing topic context:\n{topic_context.strip()}")

    if not context_parts:
        raise HttpError(
            400,
            "Provide a description or add content to the topic before requesting suggestions.",
        )

    prompt = (
        f"Suggest {limit} topic ideas for a news topic. "
        f"Each topic should be a short, broad phrase in nominalized passive form. "
        f"Avoid overly specific or literal restatements of the subject. "
        f"Make the {limit} suggestions vary in scope, but none too specific. "
    )

    prompt += "\n\nUse the following information as context:\n\n"
    prompt += "\n\n".join(context_parts)
    prompt = append_default_language_instruction(prompt)

    with OpenAI() as client:
        response = client.responses.parse(
            model=settings.DEFAULT_AI_MODEL,
            input=prompt,
            text_format=TopicSuggestionList,
        )

    return response.output_parsed.topics


@api.get("/suggest", response=List[str])
def suggest_topics_get(
    request, about: Optional[str] = None, limit: int = 3, topic_uuid: Optional[str] = None
):
    """Return suggested topics for a description and/or context via GET."""

    return suggest_topics(about=about, limit=limit, topic_uuid=topic_uuid)


@api.post("/suggest", response=List[str])
def suggest_topics_post(request, payload: SuggestTopicsRequest):
    """Return suggested topics for a description and/or context via POST."""

    return suggest_topics(
        about=payload.about, limit=payload.limit, topic_uuid=payload.topic_uuid
    )


