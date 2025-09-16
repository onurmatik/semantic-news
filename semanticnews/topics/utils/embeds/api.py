from datetime import datetime, timezone as datetime_timezone
from typing import Optional

import requests
import yt_dlp
from django.utils import timezone as django_timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicSocialEmbed, TopicYoutubeVideo

router = Router()


class SocialEmbedCreateRequest(Schema):
    topic_uuid: str
    url: str


class SocialEmbedCreateResponse(Schema):
    id: int
    provider: str
    url: str
    html: str


class VideoEmbedCreateRequest(Schema):
    topic_uuid: str
    url: str


class VideoEmbedCreateResponse(Schema):
    id: int
    url: str
    video_id: str
    title: str


def _detect_provider(url: str) -> str:
    if 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    return ''


def _fetch_twitter_embed(url: str) -> str:
    res = requests.get('https://publish.twitter.com/oembed', params={'url': url, 'dnt': 'true'})
    res.raise_for_status()
    data = res.json()
    return data.get('html', '')


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


def _add_youtube_video(topic: Topic, url: str) -> TopicYoutubeVideo:
    video_id = _extract_youtube_id(url)
    if not video_id:
        raise HttpError(400, "Invalid YouTube URL")

    try:
        ydl = yt_dlp.YoutubeDL({"quiet": True})
        info = ydl.extract_info(url, download=False)
    except Exception as exc:  # pragma: no cover - network errors
        raise HttpError(400, "Failed to fetch video details") from exc

    published_at = django_timezone.now()
    timestamp = info.get("timestamp")
    if timestamp:
        published_at = datetime.fromtimestamp(timestamp, tz=datetime_timezone.utc)

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


@router.post('/create', response=SocialEmbedCreateResponse)
def create_embed(request, payload: SocialEmbedCreateRequest):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        raise HttpError(401, 'Unauthorized')

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, 'Topic not found')

    if topic.created_by_id != user.id:
        raise HttpError(403, 'Forbidden')

    provider = _detect_provider(payload.url)
    if provider != 'twitter':
        raise HttpError(400, 'Unsupported provider')

    try:
        html = _fetch_twitter_embed(payload.url)
    except Exception as exc:  # pragma: no cover - network errors
        raise HttpError(502, 'Embed fetch failed') from exc

    embed = TopicSocialEmbed.objects.create(
        topic=topic,
        provider=provider,
        url=payload.url,
        html=html,
    )
    return SocialEmbedCreateResponse(id=embed.id, provider=provider, url=embed.url, html=embed.html)


@router.post('/video/add', response=VideoEmbedCreateResponse)
def add_video_embed(request, payload: VideoEmbedCreateRequest):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        raise HttpError(401, 'Unauthorized')

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, 'Topic not found')

    if topic.created_by_id != user.id:
        raise HttpError(403, 'Forbidden')

    video = _add_youtube_video(topic, payload.url)
    return VideoEmbedCreateResponse(
        id=video.id,
        url=video.url or '',
        video_id=video.video_id,
        title=video.title,
    )
