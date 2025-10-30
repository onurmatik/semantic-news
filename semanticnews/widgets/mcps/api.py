from ninja import Router, Schema
from ninja.errors import HttpError
import requests

from semanticnews.topics.models import Topic
from .models import MCPServer

router = Router()


class MCPContextRequest(Schema):
    """Request body for fetching context from an MCP server."""

    topic_uuid: str
    server_id: int


class MCPContextResponse(Schema):
    """Response returned after fetching context."""

    context: str


@router.post("/context", response=MCPContextResponse)
def fetch_context(request, payload: MCPContextRequest):
    """Fetch extra context for a topic from an MCP server."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    try:
        server = MCPServer.objects.get(id=payload.server_id, active=True)
    except MCPServer.DoesNotExist:
        raise HttpError(404, "Server not found")

    try:
        res = requests.post(
            server.url,
            json={"topic": topic.title, "uuid": str(topic.uuid)},
            headers=server.headers or {},
        )
        res.raise_for_status()
        data = res.json()
    except Exception as exc:  # pragma: no cover - network errors
        raise HttpError(502, "MCP server error") from exc

    return MCPContextResponse(context=data.get("context", ""))
