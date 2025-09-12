from typing import Optional

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

    if payload.narrative is not None:
        narrative_obj = TopicNarrative.objects.create(
            topic=topic, narrative=payload.narrative, status="finished"
        )
        return TopicNarrativeCreateResponse(narrative=narrative_obj.narrative)

    content_md = topic.build_context()

    prompt = (
        f"Below is a set of events and contents about {topic.title}. "
        "Write a detailed narrative that explains the full context and connections between them. "
        "Respond in Markdown and highlight key entities by making them **bold**. "
        "Use paragraphs where appropriate. "
        f"\n\n{content_md}"
    )

    narrative_obj = TopicNarrative.objects.create(topic=topic, narrative="")
    try:
        with OpenAI() as client:
            response = client.responses.parse(
                model="gpt-5",
                input=prompt,
                text_format=_TopicNarrativeResponse,
            )
        narrative_text = response.output_parsed.narrative
        narrative_obj.narrative = narrative_text
        narrative_obj.status = "finished"
        narrative_obj.error_message = None
        narrative_obj.error_code = None
        narrative_obj.save(update_fields=[
            "narrative",
            "status",
            "error_message",
            "error_code",
        ])
        return TopicNarrativeCreateResponse(narrative=narrative_text)
    except Exception as e:
        narrative_obj.status = "error"
        narrative_obj.error_message = str(e)
        narrative_obj.save(update_fields=["status", "error_message"])
        return TopicNarrativeCreateResponse(narrative=narrative_obj.narrative or "")
