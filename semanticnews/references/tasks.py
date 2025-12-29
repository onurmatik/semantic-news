import json

from celery import shared_task
from django.conf import settings

from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

from semanticnews.topics.models import Topic
from semanticnews.topics.tasks import generate_section_suggestions

from .models import Reference, TopicReference


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


def _parse_reference_insights(response_text: str) -> tuple[str, list[str]]:
    if not response_text:
        raise ValueError("Empty response from LLM.")
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM response was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM response did not contain a JSON object.")
    summary = payload.get("summary") or ""
    key_facts = payload.get("key_facts") or []
    if not isinstance(summary, str):
        summary = ""
    if not isinstance(key_facts, list):
        key_facts = []
    cleaned_facts = []
    for fact in key_facts:
        fact_text = str(fact).strip()
        if fact_text:
            cleaned_facts.append(fact_text)
    return summary.strip(), cleaned_facts


@shared_task(name="references.generate_reference_insights")
def generate_reference_insights(link_id: int) -> dict:
    link = (
        TopicReference.objects.select_related("reference")
        .filter(id=link_id, is_deleted=False)
        .first()
    )
    if link is None:
        return {"success": False, "message": "Reference link not found."}

    reference = link.reference
    content = reference.content_excerpt or ""
    if not content.strip():
        return {"success": False, "message": "Reference content is empty."}

    input_content = content
    if len(input_content) > 12000:
        input_content = input_content[:12000]

    prompt = (
        "Summarize the reference content and extract key facts. "
        "Return JSON with keys: summary (string) and key_facts (array of strings). "
        "Keep the summary concise and key_facts as short bullet points. "
        "Respond ONLY with JSON."
    )
    prompt = append_default_language_instruction(prompt)
    prompt += "\n\nReference:\n" + input_content

    try:
        with OpenAI() as client:
            response = client.responses.create(
                model=settings.DEFAULT_AI_MODEL,
                input=prompt,
            )
        response_text = _extract_response_text(response)
        summary, key_facts = _parse_reference_insights(response_text)
    except Exception as exc:
        return {"success": False, "message": f"Unable to generate insights: {exc}"}

    link.summary = summary
    link.key_facts = key_facts
    link.save(update_fields=["summary", "key_facts"])
    return {"success": True, "message": "Reference insights saved."}


def _refresh_stale_references_for_topic(topic: Topic) -> list[Reference]:
    references = (
        Reference.objects.filter(topic_links__topic=topic, topic_links__is_deleted=False)
        .distinct()
        .order_by("id")
    )
    refreshed: list[Reference] = []
    for reference in references:
        if reference.should_refresh():
            reference.refresh_metadata()
            refreshed.append(reference)
    return refreshed


@shared_task(name="references.refresh_stale_references")
def refresh_stale_references(topic_uuid: str) -> dict:
    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return {"success": False, "message": "Topic not found.", "refreshed_count": 0}

    refreshed = _refresh_stale_references_for_topic(topic)
    return {"success": True, "refreshed_count": len(refreshed)}


def _normalize_suggestions_args(args: tuple) -> str:
    if not args:
        return ""
    if len(args) == 1:
        return str(args[0])
    if isinstance(args[0], list):
        return str(args[1])
    return str(args[0])


@shared_task(name="references.generate_reference_suggestions")
def generate_reference_suggestions(*args, simulate_failure: bool = False):
    topic_uuid = _normalize_suggestions_args(args)
    if simulate_failure:
        raise ValueError("Unable to generate reference suggestions.")

    result = generate_section_suggestions(topic_uuid)
    if result.get("success"):
        TopicReference.objects.filter(
            topic__uuid=topic_uuid, is_deleted=False
        ).update(is_suggested=True)
    return result
