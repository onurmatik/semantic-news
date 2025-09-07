from typing import Literal, Optional

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicRecap
from ....openai import OpenAI

router = Router()


class TopicRecapCreateRequest(Schema):
    """Request body for creating a recap for a topic."""

    topic_uuid: str
    websearch: bool = False
    length: Optional[Literal["short", "medium", "long"]] = "medium"
    tone: Optional[Literal["neutral", "journalistic", "academic", "friendly", "sarcastic"]] = "neutral"
    instructions: Optional[str] = None


class TopicRecapCreateResponse(Schema):
    """Response returned after creating a recap."""

    recap: str


@router.post("/create", response=TopicRecapCreateResponse)
def create_recap(request, payload: TopicRecapCreateRequest):
    """Generate and store a recap for a topic using OpenAI."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    content_md = topic.build_context()

    if payload.length == "short":
        length_translated = "brief, concise"
    elif payload.length == "medium":
        length_translated = "medium-length"
    else:  # long
        length_translated = "comprehensive"

    instructions = (
        f"Below is a list of events and contents related to {topic.title}."
        f"Provide a {length_translated}, coherent recap summarizing the essential narrative and main points. "
        f"Maintain a {payload.tone} tone. Keep it engaging and easy to scan. "
        f"Do not add evaluative phrases; no commentary or interpretation. "
        f"Respond in Markdown and highlight key entities by making them **bold**. "
        f"Give paragraph breaks where appropriate. Do not use any other formatting such as lists, titles, etc. "
    )

    if payload.instructions:
        instructions += f"\n\n{payload.instructions}"

    instructions += f"\n\n{content_md}"

    kwargs = {}
    if payload.websearch:
        kwargs["tools"] = [{"type": "web_search_preview"}]

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            input=instructions,
            text_format=TopicRecapCreateResponse,
            **kwargs,
        )

    recap_text = response.output_parsed.recap

    TopicRecap.objects.create(topic=topic, recap=recap_text)

    return TopicRecapCreateResponse(recap=recap_text)
