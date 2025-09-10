from typing import Optional

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicNarrative
from ....openai import OpenAI

router = Router()


class TopicNarrativeCreateRequest(Schema):
    """Request body for creating or suggesting a narrative."""

    topic_uuid: str
    narrative: Optional[str] = None


class TopicNarrativeCreateResponse(Schema):
    """Response returned after creating or suggesting a narrative."""

    narrative: str


class _TopicNarrativeResponse(Schema):
    narrative: str


@router.post("/create", response=TopicNarrativeCreateResponse)
def create_narrative(request, payload: TopicNarrativeCreateRequest):
    """Create a narrative or return an AI-generated suggestion."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if payload.narrative:
        TopicNarrative.objects.create(
            topic=topic, narrative=payload.narrative, status="finished"
        )
        return TopicNarrativeCreateResponse(narrative=payload.narrative)

    content_md = topic.build_context()

    prompt = (
        f"Below is a set of events and contents about {topic.title}. "
        "Write a detailed narrative that explains the full context and connections between them. "
        "Respond in Markdown and highlight key entities by making them **bold**. "
        "Use paragraphs where appropriate. "
        f"\n\n{content_md}"
    )

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            input=prompt,
            text_format=_TopicNarrativeResponse,
        )

    return TopicNarrativeCreateResponse(narrative=response.output_parsed.narrative)
