from typing import Dict, Callable, Optional
from datetime import datetime

from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
import yt_dlp

from ...models import Topic
from .models import TopicYoutubeVideo

router = Router()


def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract the YouTube video ID from a URL."""
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)
    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        return parsed.path.lstrip("/")
    if parsed.hostname and "youtube" in parsed.hostname:
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/")[2]
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
    return None


class TopicMediaAddRequest(Schema):
    topic_uuid: str
    media_type: str
    url: str


class TopicMediaAddResponse(Schema):
    id: int
    media_type: str
    url: str


def _add_youtube_video(topic: Topic, url: str) -> TopicYoutubeVideo:
    video_id = _extract_youtube_id(url)
    if not video_id:
        raise HttpError(400, "Invalid YouTube URL")

    try:
        ydl = yt_dlp.YoutubeDL({"quiet": True})
        info = ydl.extract_info(url, download=False)
    except Exception as exc:  # pragma: no cover - network errors
        raise HttpError(400, "Failed to fetch video details") from exc

    published_at = timezone.now()
    timestamp = info.get("timestamp")
    if timestamp:
        published_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)

    return TopicYoutubeVideo.objects.create(
        topic=topic,
        url=url,
        video_id=video_id,
        title=info.get("title", video_id),
        description=info.get("description", ""),
        thumbnail=info.get("thumbnail"),
        published_at=published_at,
        status="finished",
    )


_HANDLERS: Dict[str, Callable[[Topic, str], TopicYoutubeVideo]] = {
    "youtube": _add_youtube_video,
}


@router.post("/add", response=TopicMediaAddResponse)
def add_media(request, payload: TopicMediaAddRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    handler = _HANDLERS.get(payload.media_type)
    if not handler:
        raise HttpError(400, "Unsupported media type")

    media = handler(topic, payload.url)
    return TopicMediaAddResponse(id=media.id, media_type=payload.media_type, url=media.url)

