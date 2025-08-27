from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from typing import Optional
from .models import Topic

api = NinjaAPI(title="Topics API")


class TopicCreateRequest(Schema):
    """Request body for creating a topic.

    Attributes:
        title (str): Title of the topic.
    """

    title: str


class TopicCreateResponse(Schema):
    """Response returned after creating a topic.

    Attributes:
        uuid (str): Unique identifier of the topic.
        title (str): Title of the topic.
        slug (str): Slug for the topic.
    """

    uuid: str
    title: str
    slug: str


@api.post("/create", response=TopicCreateResponse)
def create_topic(request, payload: TopicCreateRequest):
    """Create a new topic for the authenticated user.

    Args:
        request: The HTTP request instance.
        payload: Data including the topic title.

    Returns:
        Data for the newly created topic.
    """

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    topic = Topic.objects.create(title=payload.title, created_by=user)

    return TopicCreateResponse(uuid=str(topic.uuid), title=topic.title, slug=topic.slug)
