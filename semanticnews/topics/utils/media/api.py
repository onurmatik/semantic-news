from typing import List

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicMedia

router = Router()


class TopicMediaCreateRequest(Schema):
    topic_uuid: str
    media_type: str
    url: str = None


class TopicMediaCreateResponse(Schema):
    id: int
    media_type: str
    url: str | None = None


@router.post("/add", response=TopicMediaCreateResponse)
def add_media(request, payload: TopicMediaCreateRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")
    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")
    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")
    media = TopicMedia.objects.create(
        topic=topic, media_type=payload.media_type, url=payload.url
    )
    return TopicMediaCreateResponse(id=media.id, media_type=media.media_type, url=media.url)


class TopicMediaItem(Schema):
    id: int
    media_type: str
    url: str | None = None


class TopicMediaListResponse(Schema):
    total: int
    items: List[TopicMediaItem]


@router.get("/{topic_uuid}/list", response=TopicMediaListResponse)
def list_media(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")
    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")
    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")
    media_qs = topic.media.all().values("id", "media_type", "url")
    items = [TopicMediaItem(**m) for m in media_qs]
    return TopicMediaListResponse(total=len(items), items=items)
