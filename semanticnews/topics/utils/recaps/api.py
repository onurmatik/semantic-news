from ninja import Router, Schema
from ninja.errors import HttpError
from asgiref.sync import async_to_sync

from ...models import Topic
from .models import TopicRecap
from ...agents import TopicRecapAgent

router = Router()


class TopicRecapCreateRequest(Schema):
    """Request body for creating a recap for a topic."""

    topic_uuid: str
    websearch: bool = False


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

    agent = TopicRecapAgent()
    response = async_to_sync(agent.run)(content_md, websearch=payload.websearch)
    recap_text = response.recap_en

    TopicRecap.objects.create(topic=topic, recap=recap_text)

    return TopicRecapCreateResponse(recap=recap_text)
