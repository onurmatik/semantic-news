from datetime import datetime, timedelta
from typing import List, Optional

from django.utils import timezone
from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError
from celery.result import AsyncResult

from semanticnews.topics.models import Topic

from .models import Reference, TopicReference
from .tasks import generate_reference_suggestions

router = Router()


class ReferenceCreateRequest(Schema):
    url: str


class ReferenceDetail(Schema):
    id: int
    uuid: str
    url: str
    domain: Optional[str]
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_published_at: Optional[datetime] = None
    last_fetched_at: Optional[datetime] = None
    fetch_status: Optional[str] = None
    added_at: datetime


class ReferenceSuggestionTaskResponse(Schema):
    task_id: str


class ReferenceSuggestionStatusResponse(Schema):
    task_id: str
    state: str
    success: Optional[bool] = None
    message: Optional[str] = None


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


def _serialize_link(link: TopicReference) -> ReferenceDetail:
    ref = link.reference
    added_at = link.added_at
    if added_at is not None:
        added_at = make_naive(added_at)

    last_fetched_at = ref.last_fetched_at
    if last_fetched_at is not None:
        last_fetched_at = make_naive(last_fetched_at)

    published_at = ref.meta_published_at
    if published_at is not None:
        published_at = make_naive(published_at)

    return ReferenceDetail(
        id=link.id,
        uuid=str(ref.uuid),
        url=ref.url,
        domain=ref.domain,
        meta_title=ref.meta_title or None,
        meta_description=ref.meta_description or None,
        meta_published_at=published_at,
        last_fetched_at=last_fetched_at,
        fetch_status=ref.fetch_status,
        added_at=added_at or timezone.now(),
    )


def _should_refresh(reference: Reference) -> bool:
    if reference.fetch_status == Reference.STATUS_PENDING:
        return True
    if reference.last_fetched_at is None:
        return True
    return reference.last_fetched_at < timezone.now() - timedelta(hours=6)


@router.get("/{topic_uuid}/references", response=List[ReferenceDetail])
def list_topic_references(request, topic_uuid: str):
    topic = _require_owned_topic(request, topic_uuid)

    links = (
        TopicReference.objects.filter(topic=topic, is_deleted=False)
        .select_related("reference")
        .order_by("-added_at")
    )
    return [_serialize_link(link) for link in links]


@router.post("/{topic_uuid}/references", response=ReferenceDetail)
def add_topic_reference(request, topic_uuid: str, payload: ReferenceCreateRequest):
    topic = _require_owned_topic(request, topic_uuid)
    user = getattr(request, "user", None)

    normalized = Reference.normalize_url(payload.url)
    defaults = {"url": payload.url, "normalized_url": normalized, "domain": ""}
    reference, created = Reference.objects.get_or_create(
        normalized_url=normalized,
        defaults=defaults,
    )

    # Ensure the stored URL is fetchable (normalized with scheme).
    if created and (not reference.url or "://" not in reference.url):
        reference.url = normalized
        reference.save(update_fields=["url"])
    elif not created and reference.url and "://" not in reference.url:
        reference.url = normalized
        reference.save(update_fields=["url"])

    if _should_refresh(reference):
        reference.refresh_metadata()

    link, link_created = TopicReference.objects.get_or_create(
        topic=topic,
        reference=reference,
        defaults={
            "added_by": user,
            "content_version_snapshot": reference.content_version or 1,
        },
    )

    if not link_created and link.is_deleted:
        link.is_deleted = False
        link.added_by = link.added_by or user
        link.added_at = link.added_at or timezone.now()
        link.save(update_fields=["is_deleted", "added_by", "added_at"])
    elif not link_created and link.added_by is None and user:
        link.added_by = user
        link.save(update_fields=["added_by"])

    return _serialize_link(link)


@router.delete("/{topic_uuid}/references/{link_id}", response={204: None})
def delete_topic_reference(request, topic_uuid: str, link_id: int):
    topic = _require_owned_topic(request, topic_uuid)

    try:
        link = TopicReference.objects.get(id=link_id, topic=topic)
    except TopicReference.DoesNotExist:
        raise HttpError(404, "Reference not found")

    if link.is_deleted:
        return 204, None

    link.is_deleted = True
    link.save(update_fields=["is_deleted"])
    return 204, None


@router.post(
    "/{topic_uuid}/references/suggestions/",
    response=ReferenceSuggestionTaskResponse,
)
def request_reference_suggestions(request, topic_uuid: str):
    topic = _require_owned_topic(request, topic_uuid)

    task = generate_reference_suggestions.delay(str(topic.uuid))
    return ReferenceSuggestionTaskResponse(task_id=task.id)


@router.get(
    "/{topic_uuid}/references/suggestions/{task_id}",
    response=ReferenceSuggestionStatusResponse,
)
def reference_suggestions_status(request, topic_uuid: str, task_id: str):
    _require_owned_topic(request, topic_uuid)

    result = AsyncResult(task_id)
    state = result.state
    success: Optional[bool] = None
    message: Optional[str] = None

    if result.successful():
        payload = result.result or {}
        success = bool(payload.get("success", True))
        message = payload.get("message") or "Reference suggestions are ready."
    elif result.failed():
        success = False
        message = str(result.result) or "Unable to generate reference suggestions."

    return ReferenceSuggestionStatusResponse(
        task_id=task_id,
        state=state,
        success=success,
        message=message,
    )
