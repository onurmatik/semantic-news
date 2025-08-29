from typing import Literal, Optional

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicRecap
from ....openai import OpenAI

router = Router()


class TopicRecapResult(Schema):
    """Generate a topic recap in Turkish and English.

    Provide a 1 paragraph concise, coherent recap in Markdown summarizing the
    essential narrative and main points. Keep it brief, engaging and easy to
    scan, maintain a neutral tone and highlight key entities by making them
    **bold**.
    """

    recap_tr: str
    recap_en: str


class TopicRecapCreateRequest(Schema):
    """Request body for creating a recap for a topic."""

    topic_uuid: str
    websearch: bool = False
    length: Optional[Literal["short", "medium", "long"]] = None
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

    content_md = f"# {topic.title}\n\n"

    events = topic.events.all()
    if events:
        content_md += "## Events\n\n"
        for event in events:
            content_md += f"- {event.title} ({event.date})\n"

    contents = topic.contents.all()
    if contents:
        content_md += "\n## Contents\n\n"
        for c in contents:
            title = c.title or ""
            text = c.markdown or ""
            content_md += f"### {title}\n{text}\n\n"

    extra_instructions = []
    if payload.length:
        extra_instructions.append(f"Write a {payload.length} recap.")
    if payload.instructions:
        extra_instructions.append(payload.instructions)
    if extra_instructions:
        content_md += "\n" + "\n".join(extra_instructions)

    kwargs = {}
    if payload.websearch:
        kwargs["tools"] = [{"type": "web_search_preview"}]

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            input=content_md,
            text_format=TopicRecapResult,
            **kwargs,
        )

    recap_text = response.output_parsed["recap_en"]

    TopicRecap.objects.create(topic=topic, recap=recap_text)

    return TopicRecapCreateResponse(recap=recap_text)
