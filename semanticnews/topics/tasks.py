import json
from typing import Any, Iterable, List, Optional, Sequence

from celery import shared_task
from django.conf import settings
from pydantic import BaseModel, Field

from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction
from semanticnews.references.models import TopicReference

from .models import Topic, TopicSectionSuggestion


class TopicSectionSuggestionCreate(BaseModel):
    widget_name: str = Field(min_length=1)
    content: dict[str, Any]
    order: int = Field(ge=0)

    class Config:
        extra = "forbid"


class TopicSectionSuggestionUpdate(BaseModel):
    section_id: int = Field(ge=1)
    content: dict[str, Any]

    class Config:
        extra = "forbid"


class TopicSectionSuggestionsPayload(BaseModel):
    create: List[TopicSectionSuggestionCreate] = Field(default_factory=list)
    update: List[TopicSectionSuggestionUpdate] = Field(default_factory=list)
    reorder: List[int] = Field(default_factory=list)
    delete: List[int] = Field(default_factory=list)

    class Config:
        extra = "forbid"


def _dump_model(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _serialize_section(section) -> dict:
    return {
        "id": section.id,
        "widget_name": section.widget_name,
        "draft_display_order": section.draft_display_order,
        "order": section.draft_display_order,
        "content": section.content or {},
    }


def _extract_response_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    try:
        parts = []
        for output in response.output:
            for item in output.content:
                chunk = getattr(item, "text", None)
                if chunk:
                    parts.append(chunk)
        return "".join(parts).strip()
    except Exception:
        return ""


def _parse_suggestions_response(response_text: str) -> TopicSectionSuggestionsPayload:
    if not response_text:
        raise ValueError("Empty response from LLM.")
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM response was not valid JSON.") from exc
    if isinstance(payload, str):
        raise ValueError("LLM response did not contain a JSON object.")
    return TopicSectionSuggestionsPayload(**payload)


def _serialize_reference(link: TopicReference) -> dict:
    reference = link.reference
    return {
        "id": link.id,
        "reference_uuid": str(reference.uuid),
        "url": reference.url,
        "domain": reference.domain,
        "meta_title": reference.meta_title or None,
        "meta_description": reference.meta_description or None,
        "meta_published_at": reference.meta_published_at.isoformat()
        if reference.meta_published_at
        else None,
        "lead_image_url": reference.lead_image_url or None,
        "content_excerpt": reference.content_excerpt or None,
        "last_fetched_at": reference.last_fetched_at.isoformat()
        if reference.last_fetched_at
        else None,
        "status_code": reference.status_code,
        "fetch_status": reference.fetch_status,
        "fetch_error": reference.fetch_error or None,
        "raw_payload": reference.raw_payload or None,
        "summary": link.summary or None,
        "key_facts": link.key_facts or [],
        "content_version_snapshot": link.content_version_snapshot,
    }


def _build_topic_llm_input(topic: Topic) -> dict:
    sections = [
        _serialize_section(section)
        for section in topic.sections_ordered
        if not section.is_deleted and not section.is_draft_deleted
    ]
    references = [
        _serialize_reference(link)
        for link in TopicReference.objects.filter(topic=topic, is_deleted=False)
        .select_related("reference")
        .order_by("-added_at")
    ]
    return {
        "topic": {"title": topic.title or ""},
        "sections": sections,
        "references": references,
    }


def _ensure_known_ids(ids: Sequence[int], valid_ids: set[int], label: str) -> None:
    unknown = [value for value in ids if value not in valid_ids]
    if unknown:
        raise ValueError(f"Unknown section IDs in {label}: {unknown}")


def _ensure_unique(ids: Sequence[int], label: str) -> None:
    if len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate section IDs in {label}")


def _validate_suggestions(
    suggestions: TopicSectionSuggestionsPayload,
    valid_section_ids: Iterable[int],
) -> None:
    valid_set = set(valid_section_ids)

    update_ids = [entry.section_id for entry in suggestions.update]
    delete_ids = list(suggestions.delete)
    reorder_ids = list(suggestions.reorder)

    _ensure_unique(update_ids, "update")
    _ensure_unique(delete_ids, "delete")
    _ensure_unique(reorder_ids, "reorder")

    _ensure_known_ids(update_ids, valid_set, "update")
    _ensure_known_ids(delete_ids, valid_set, "delete")
    _ensure_known_ids(reorder_ids, valid_set, "reorder")

    overlapping = set(update_ids) & set(delete_ids)
    if overlapping:
        raise ValueError(f"Sections cannot be both updated and deleted: {sorted(overlapping)}")


@shared_task(name="topics.generate_section_suggestions")
def generate_section_suggestions(topic_uuid: str) -> dict:
    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return {"success": False, "message": "Topic not found."}

    llm_input = _build_topic_llm_input(topic)
    prompt = (
        "Create/update/reorder/delete topic sections based on references. "
        "Use 1-based order values for any new sections."
    )
    prompt = append_default_language_instruction(prompt)
    prompt += "\n\nInput:\n" + json.dumps(llm_input, ensure_ascii=False)

    try:
        with OpenAI() as client:
            response = client.responses.create(
                model=settings.DEFAULT_AI_MODEL,
                input=prompt,
            )
        response_text = _extract_response_text(response)
        suggestions = _parse_suggestions_response(response_text)
        valid_section_ids = [section["id"] for section in llm_input["sections"]]
        _validate_suggestions(suggestions, valid_section_ids)
    except Exception as exc:
        return {
            "success": False,
            "message": f"Unable to generate valid section suggestions: {exc}",
        }

    suggestion = TopicSectionSuggestion.objects.create(
        topic=topic,
        created_by=topic.created_by,
        payload=_dump_model(suggestions),
    )

    return {
        "success": True,
        "message": "Section suggestions generated successfully.",
        "payload": suggestion.payload,
    }
