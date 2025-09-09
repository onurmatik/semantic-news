from typing import Optional

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicRecap
from ....openai import OpenAI

router = Router()


class TopicRecapCreateRequest(Schema):
    """Request body for creating or suggesting a recap."""

    topic_uuid: str
    recap: Optional[str] = None


class TopicRecapCreateResponse(Schema):
    """Response returned after creating or suggesting a recap."""

    recap: str


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

    if payload.recap:
        TopicRecap.objects.create(
            topic=topic, recap=payload.recap, status="finished"
        )
        return TopicRecapCreateResponse(recap=payload.recap)

    content_md = topic.build_context()

    prompt = (
        f"Below is a list of events and contents related to {topic.title}."
        " Provide a concise, coherent recap summarizing the essential narrative and main points. "
        "Respond in Markdown and highlight key entities by making them **bold**. "
        "Give paragraph breaks where appropriate. Do not use any other formatting such as lists, titles, etc. "
        f"\n\n{content_md}"
    )

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            input=prompt,
            text_format=_TopicRecapResponse,
        )

    return TopicRecapCreateResponse(recap=response.output_parsed.recap)
