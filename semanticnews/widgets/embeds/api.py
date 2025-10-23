from datetime import datetime, timezone as datetime_timezone
from typing import Optional
from urllib.parse import urlparse
import re

import requests
import yt_dlp
from django.db import IntegrityError
from django.utils import timezone as django_timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from semanticnews.topics.models import Topic
from .models import TopicTweet, TopicYoutubeVideo

router = Router()


class TweetCreateRequest(Schema):
    topic_uuid: str
    url: str


class TweetCreateResponse(Schema):
    id: int
    tweet_id: str
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


def _fetch_twitter_embed(url: str) -> str:
    res = requests.get('https://publish.twitter.com/oembed', params={'url': url, 'dnt': 'true'})
    res.raise_for_status()
    data = res.json()
    return data.get('html', '')


_TWEET_HOSTS = {'twitter.com', 'mobile.twitter.com', 'x.com'}
_TWEET_PATH_RE = re.compile(r"/status(?:es)?/(?P<id>\d+)")


def _extract_tweet_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    hostname = (parsed.hostname or '').lower()
    if hostname.startswith('www.'):
        hostname = hostname[4:]
    if hostname not in _TWEET_HOSTS:
        return None
    match = _TWEET_PATH_RE.search(parsed.path or '')
    if not match:
        return None
    return match.group('id')


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
        video_published_at=published_at,
        status="finished",
    )


@router.post('/tweet/add', response=TweetCreateResponse)
def add_tweet_embed(request, payload: TweetCreateRequest):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        raise HttpError(401, 'Unauthorized')

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, 'Topic not found')

    if topic.created_by_id != user.id:
        raise HttpError(403, 'Forbidden')

    tweet_id = _extract_tweet_id(payload.url)
    if not tweet_id:
        raise HttpError(400, 'Invalid tweet URL')

    if TopicTweet.objects.filter(topic=topic, tweet_id=tweet_id).exists():
        raise HttpError(400, 'Tweet already added')

    try:
        html = _fetch_twitter_embed(payload.url)
    except Exception as exc:  # pragma: no cover - network errors
        raise HttpError(502, 'Embed fetch failed') from exc

    try:
        tweet = TopicTweet.objects.create(
            topic=topic,
            tweet_id=tweet_id,
            url=payload.url,
            html=html,
            published_at=django_timezone.now(),
        )
    except IntegrityError:
        raise HttpError(400, 'Tweet already added')
    return TweetCreateResponse(id=tweet.id, tweet_id=tweet.tweet_id, url=tweet.url, html=tweet.html)


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
