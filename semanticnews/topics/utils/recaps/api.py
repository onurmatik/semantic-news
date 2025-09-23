from datetime import datetime
from typing import Optional, Literal, List

from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicRecap
from ....openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

router = Router()

StatusLiteral = Literal["finished", "error"]


class TopicRecapCreateRequest(Schema):
    """Request body for creating or suggesting a recap."""

    topic_uuid: str
    recap: Optional[str] = None


class TopicRecapCreateResponse(Schema):
    """Response returned after creating or suggesting a recap."""

    recap: str
    status: StatusLiteral
    error_message: Optional[str] = None
    error_code: Optional[str] = None


class _TopicRecapResponse(Schema):
    recap: str


@router.post("/create", response=TopicRecapCreateResponse)
def create_recap(request, payload: TopicRecapCreateRequest):
    """Create a recap or return an AI-generated suggestion."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if payload.recap is not None:
        recap_obj = TopicRecap.objects.create(
            topic=topic,
            recap=payload.recap,
            status="finished",
        )
        status: StatusLiteral = "finished"
        return TopicRecapCreateResponse(recap=recap_obj.recap, status=status)

    # Create immediately; default status is "in_progress"
    recap_obj = TopicRecap.objects.create(topic=topic, recap="")

    content_md = topic.build_context()

    prompt = (
        f"Below is a list of events and contents related to {topic.title}."
        " Provide a concise, coherent recap summarizing the essential narrative and main points. "
        "Respond in Markdown and highlight key entities by making them **bold**. "
        "Give paragraph breaks where appropriate. Do not use any other formatting such as lists, titles, etc. "
    )
    prompt = append_default_language_instruction(prompt)
    prompt += f"\n\n{content_md}"

    try:
        with OpenAI() as client:
            response = client.responses.parse(
                model="gpt-5",
                input=prompt,
                text_format=_TopicRecapResponse,
            )

        recap_text = response.output_parsed.recap
        recap_obj.recap = recap_text
        recap_obj.status = "finished"
        recap_obj.error_message = None
        recap_obj.error_code = None
        recap_obj.save(update_fields=["recap", "status", "error_message", "error_code"])

        status: StatusLiteral = "finished"
        return TopicRecapCreateResponse(recap=recap_text, status=status)

    except Exception as e:
        error_code = getattr(e, "code", None) or "openai_error"
        error_message = str(e)

        recap_obj.status = "error"
        recap_obj.error_message = error_message
        recap_obj.error_code = error_code
        recap_obj.save(update_fields=["status", "error_message", "error_code"])

        status: StatusLiteral = "error"
        return TopicRecapCreateResponse(recap=recap_obj.recap or "", status=status)


class TopicRecapItem(Schema):
    id: int
    recap: str
    created_at: datetime  # ISO string back to JS nicely


class TopicRecapListResponse(Schema):
    total: int
    items: List[TopicRecapItem]


@router.get("/{topic_uuid}/list", response=TopicRecapListResponse)
def list_recaps(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")
    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")
    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    recaps = (
        TopicRecap.objects
        .filter(topic=topic, status="finished")
        .order_by("created_at")
        .values("id", "recap", "created_at")
    )

    items = [
        TopicRecapItem(
            id=r["id"],
            recap=r["recap"],
            created_at=make_naive(r["created_at"]),
        )
        for r in recaps
    ]
    return TopicRecapListResponse(total=len(items), items=items)


@router.delete("/{recap_id}", response={204: None})
def delete_recap(request, recap_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        recap = TopicRecap.objects.select_related("topic").get(id=recap_id)
    except TopicRecap.DoesNotExist:
        raise HttpError(404, "Recap not found")

    if recap.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    recap.delete()
    return 204, None
