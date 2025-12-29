from datetime import datetime
from typing import List, Optional

from django.db import transaction
from django.utils import timezone
from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError
from celery.result import AsyncResult

from semanticnews.topics.models import (
    Topic,
    TopicSection,
    TopicSectionSuggestion,
    TopicSectionSuggestionStatus,
)
from semanticnews.topics.tasks import TopicSectionSuggestionsPayload, _validate_suggestions
from semanticnews.topics.widgets import get_widget

from .models import Reference, TopicReference
from .tasks import generate_reference_insights, generate_reference_suggestions

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
    lead_image_url: Optional[str] = None
    content_excerpt: Optional[str] = None
    last_fetched_at: Optional[datetime] = None
    status_code: Optional[int] = None
    fetch_status: Optional[str] = None
    fetch_error: Optional[str] = None
    added_at: datetime


class ReferenceSuggestionTaskResponse(Schema):
    task_id: str


class ReferenceSuggestionStatusResponse(Schema):
    task_id: str
    state: str
    success: Optional[bool] = None
    message: Optional[str] = None
    suggestion_id: Optional[int] = None
    payload: Optional[TopicSectionSuggestionsPayload] = None


class ReferenceSuggestionLatestResponse(Schema):
    has_suggestions: bool
    suggestion_id: Optional[int] = None
    status: Optional[str] = None
    message: Optional[str] = None
    payload: Optional[TopicSectionSuggestionsPayload] = None


class ReferenceSuggestionApplyRequest(Schema):
    suggestion_id: Optional[int] = None
    payload: Optional[TopicSectionSuggestionsPayload] = None


class ReferenceSuggestionApplyResponse(Schema):
    success: bool
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


def _get_latest_section_suggestion(topic: Topic) -> Optional[TopicSectionSuggestion]:
    return (
        TopicSectionSuggestion.objects.filter(topic=topic)
        .order_by("-created_at", "-id")
        .first()
    )


def _apply_section_suggestions(
    topic: Topic, suggestions: TopicSectionSuggestionsPayload
) -> None:
    valid_section_ids = [
        section.id
        for section in topic.sections_ordered
        if not section.is_deleted and not section.is_draft_deleted
    ]
    _validate_suggestions(suggestions, valid_section_ids)

    delete_ids = set(suggestions.delete)
    reorder_ids = list(suggestions.reorder)
    create_entries = list(suggestions.create)

    for entry in create_entries:
        if entry.widget_name:
            try:
                get_widget(entry.widget_name)
            except KeyError as exc:
                raise HttpError(400, f"Unknown widget '{entry.widget_name}'.") from exc

    with transaction.atomic():
        if delete_ids:
            TopicSection.objects.filter(
                topic=topic, id__in=delete_ids, is_draft_deleted=False
            ).update(is_draft_deleted=True)

        for entry in suggestions.update:
            section = TopicSection.objects.get(topic=topic, id=entry.section_id)
            if section.is_deleted or section.is_draft_deleted:
                continue
            section.content = entry.content or {}

        for entry in create_entries:
            section = TopicSection.objects.create(
                topic=topic,
                widget_name=entry.widget_name,
                draft_display_order=entry.order,
                display_order=entry.order,
            )
            section._get_or_create_draft_record()
            section.content = entry.content or {}

        active_sections = list(
            TopicSection.objects.filter(
                topic=topic, is_deleted=False, is_draft_deleted=False
            )
        )
        desired_order: dict[int, int] = {
            section_id: index for index, section_id in enumerate(reorder_ids, start=1)
        }
        ordered_sections = sorted(
            active_sections,
            key=lambda item: (
                desired_order.get(item.id, item.draft_display_order or 0),
                item.id,
            ),
        )
        updates: list[TopicSection] = []
        for order, section in enumerate(ordered_sections, start=1):
            if section.draft_display_order != order:
                section.draft_display_order = order
                updates.append(section)

        if updates:
            TopicSection.objects.bulk_update(updates, ["draft_display_order"])


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
        lead_image_url=ref.lead_image_url or None,
        content_excerpt=ref.content_excerpt or None,
        last_fetched_at=last_fetched_at,
        status_code=ref.status_code,
        fetch_status=ref.fetch_status,
        fetch_error=ref.fetch_error or None,
        added_at=added_at or timezone.now(),
    )


def _should_refresh(reference: Reference) -> bool:
    return reference.should_refresh()


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

    if reference.content_excerpt and not link.summary and not link.key_facts:
        generate_reference_insights.delay(link.id)

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
    topic = _require_owned_topic(request, topic_uuid)

    result = AsyncResult(task_id)
    state = result.state
    success: Optional[bool] = None
    message: Optional[str] = None
    payload_obj: Optional[TopicSectionSuggestionsPayload] = None
    suggestion_id: Optional[int] = None

    if result.successful():
        payload = result.result or {}
        success = bool(payload.get("success", True))
        message = payload.get("message") or "Reference suggestions are ready."
        payload_data = payload.get("payload")
        if payload_data is not None:
            payload_obj = TopicSectionSuggestionsPayload(**payload_data)
    elif result.failed():
        success = False
        message = str(result.result) or "Unable to generate reference suggestions."

    latest_suggestion = _get_latest_section_suggestion(topic)
    if latest_suggestion is not None:
        suggestion_id = latest_suggestion.id
        if payload_obj is None:
            payload_obj = TopicSectionSuggestionsPayload(**latest_suggestion.payload)
        if latest_suggestion.status == TopicSectionSuggestionStatus.ERROR:
            success = False
            message = latest_suggestion.error or message
        else:
            success = True if success is None else success
            message = message or "Reference suggestions are ready."

    return ReferenceSuggestionStatusResponse(
        task_id=task_id,
        state=state,
        success=success,
        message=message,
        suggestion_id=suggestion_id,
        payload=payload_obj,
    )


@router.get(
    "/{topic_uuid}/references/suggestions/latest",
    response=ReferenceSuggestionLatestResponse,
)
def reference_suggestions_latest(request, topic_uuid: str):
    topic = _require_owned_topic(request, topic_uuid)
    latest_suggestion = _get_latest_section_suggestion(topic)
    if latest_suggestion is None:
        return ReferenceSuggestionLatestResponse(has_suggestions=False)

    payload_obj = TopicSectionSuggestionsPayload(**latest_suggestion.payload)
    message = "Reference suggestions are ready."
    if latest_suggestion.status == TopicSectionSuggestionStatus.ERROR:
        message = latest_suggestion.error or "Unable to generate reference suggestions."

    return ReferenceSuggestionLatestResponse(
        has_suggestions=True,
        suggestion_id=latest_suggestion.id,
        status=latest_suggestion.status,
        message=message,
        payload=payload_obj,
    )


@router.post(
    "/{topic_uuid}/references/suggestions/apply/",
    response=ReferenceSuggestionApplyResponse,
)
def apply_reference_suggestions(request, topic_uuid: str, payload: ReferenceSuggestionApplyRequest):
    topic = _require_owned_topic(request, topic_uuid)
    suggestion: Optional[TopicSectionSuggestion] = None
    if payload.suggestion_id:
        suggestion = TopicSectionSuggestion.objects.filter(
            topic=topic, id=payload.suggestion_id
        ).first()
    if suggestion is None:
        suggestion = _get_latest_section_suggestion(topic)
    if suggestion is None:
        raise HttpError(404, "No suggestions found.")

    suggestions = payload.payload or TopicSectionSuggestionsPayload(**suggestion.payload)
    _apply_section_suggestions(topic, suggestions)

    suggestion.status = TopicSectionSuggestionStatus.APPLIED
    suggestion.applied_at = timezone.now()
    suggestion.save(update_fields=["status", "applied_at"])

    return ReferenceSuggestionApplyResponse(
        success=True,
        message="Reference suggestions applied successfully.",
    )
