from datetime import datetime
from typing import List, Optional

from django.db import transaction
from django.db.models import Max
from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic, TopicModuleLayout
from .models import TopicText

router = Router()


class TopicTextCreateRequest(Schema):
    topic_uuid: str
    content: Optional[str] = ""
    placement: Optional[str] = None


class TopicTextUpdateRequest(Schema):
    content: Optional[str] = ""


class TopicTextResponse(Schema):
    id: int
    content: str
    created_at: datetime
    updated_at: datetime
    module_key: str
    placement: str
    display_order: int


class TopicTextListResponse(Schema):
    total: int
    items: List[TopicTextResponse]


def _get_owned_topic(request, topic_uuid: str) -> Topic:
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


def _serialize_text(text: TopicText, layout: Optional[TopicModuleLayout]) -> TopicTextResponse:
    module_key = f"text:{text.id}"
    placement = layout.placement if layout else TopicModuleLayout.PLACEMENT_PRIMARY
    display_order = layout.display_order if layout else 0
    return TopicTextResponse(
        id=text.id,
        content=text.content or "",
        created_at=make_naive(text.created_at),
        updated_at=make_naive(text.updated_at),
        module_key=module_key,
        placement=placement,
        display_order=display_order,
    )


@router.get("/{topic_uuid}/list", response=TopicTextListResponse)
def list_texts(request, topic_uuid: str):
    topic = _get_owned_topic(request, topic_uuid)
    texts = list(topic.texts.order_by("created_at"))
    layouts = {
        layout.module_key: layout
        for layout in topic.module_layouts.filter(module_key__startswith="text:")
    }
    items = [
        _serialize_text(text, layouts.get(f"text:{text.id}"))
        for text in texts
    ]
    return TopicTextListResponse(total=len(items), items=items)


@router.post("/create", response=TopicTextResponse)
def create_text(request, payload: TopicTextCreateRequest):
    topic = _get_owned_topic(request, payload.topic_uuid)
    valid_placements = {choice[0] for choice in TopicModuleLayout.PLACEMENT_CHOICES}
    placement = payload.placement or TopicModuleLayout.PLACEMENT_PRIMARY
    if placement not in valid_placements:
        placement = TopicModuleLayout.PLACEMENT_PRIMARY
    with transaction.atomic():
        text = TopicText.objects.create(
            topic=topic,
            content=payload.content or "",
            status="finished",
        )
        module_key = f"text:{text.id}"
        # Determine display order within placement
        max_order = (
            TopicModuleLayout.objects
            .filter(topic=topic, placement=placement)
            .aggregate(Max("display_order"))
            .get("display_order__max")
        )
        display_order = (max_order or 0) + 1
        TopicModuleLayout.objects.create(
            topic=topic,
            module_key=module_key,
            placement=placement,
            display_order=display_order,
        )
    layout = topic.module_layouts.get(module_key=module_key)
    return _serialize_text(text, layout)


@router.put("/{text_id}", response=TopicTextResponse)
def update_text(request, text_id: int, payload: TopicTextUpdateRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")
    try:
        text = TopicText.objects.select_related("topic").get(id=text_id)
    except TopicText.DoesNotExist:
        raise HttpError(404, "Text block not found")
    if text.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")
    if payload.content is not None:
        text.content = payload.content
    text.status = "finished"
    text.error_message = None
    text.error_code = None
    text.save(update_fields=["content", "status", "error_message", "error_code", "updated_at"])
    layout = text.topic.module_layouts.filter(module_key=f"text:{text.id}").first()
    return _serialize_text(text, layout)


@router.delete("/{text_id}", response={204: None})
def delete_text(request, text_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")
    try:
        text = TopicText.objects.select_related("topic").get(id=text_id)
    except TopicText.DoesNotExist:
        raise HttpError(404, "Text block not found")
    if text.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")
    topic = text.topic
    module_key = f"text:{text.id}"
    with transaction.atomic():
        TopicModuleLayout.objects.filter(topic=topic, module_key=module_key).delete()
        text.delete()
    return 204, None
