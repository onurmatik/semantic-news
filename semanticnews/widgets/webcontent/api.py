"""API endpoints for managing topic web content."""

from contextlib import closing
from datetime import datetime
from datetime import timezone as datetime_timezone
from html.parser import HTMLParser
import logging
import re
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests
import yt_dlp
from django.db import IntegrityError
from django.utils import timezone as django_timezone
from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError

from semanticnews.topics.models import Topic
from .models import TopicDocument, TopicTweet, TopicWebpage, TopicYoutubeVideo

logger = logging.getLogger(__name__)

router = Router()


class _PageMetadataParser(HTMLParser):
    """Extract title and description values from HTML markup."""

    _TITLE_META_KEYS = {"og:title", "twitter:title", "title"}
    _DESCRIPTION_META_KEYS = {"description", "og:description", "twitter:description"}

    def __init__(self) -> None:
        super().__init__()
        self.title: Optional[str] = None
        self.description: Optional[str] = None
        self._in_title = False
        self._title_buffer: List[str] = []

    def handle_starttag(self, tag: str, attrs: Iterable[Tuple[str, Optional[str]]]):
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
            self._title_buffer = []
            return

        if tag != "meta":
            return

        attributes: Dict[str, Optional[str]] = {key.lower(): value for key, value in attrs}
        content = attributes.get("content")
        if not content:
            return

        key = (attributes.get("name") or attributes.get("property") or "").lower()
        if not key:
            return

        if not self.title and key in self._TITLE_META_KEYS:
            content = content.strip()
            if content:
                self.title = content

        if not self.description and key in self._DESCRIPTION_META_KEYS:
            content = content.strip()
            if content:
                self.description = content

    def handle_startendtag(self, tag: str, attrs: Iterable[Tuple[str, Optional[str]]]):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str):
        if tag.lower() == "title":
            self._in_title = False
            if not self.title:
                title = "".join(self._title_buffer).strip()
                if title:
                    self.title = title

    def handle_data(self, data: str):
        if self._in_title:
            self._title_buffer.append(data)

    def handle_entityref(self, name: str):
        if self._in_title:
            self._title_buffer.append(self.unescape(f"&{name};"))

    def handle_charref(self, name: str):
        if self._in_title:
            if name.startswith("x") or name.startswith("X"):
                char = chr(int(name[1:], 16))
            else:
                char = chr(int(name))
            self._title_buffer.append(char)


class _UrlMetadataError(Exception):
    """Raised when metadata cannot be retrieved for a URL."""


def _fetch_url_metadata(url: str) -> Dict[str, Optional[str]]:
    """Fetch the URL and attempt to read its metadata."""

    headers = {
        "User-Agent": (
            "SemanticNewsBot/1.0 (+https://semantic-news.example/; contact=info@semantic-news.example)"
        )
    }
    try:
        with closing(
            requests.get(
                url,
                timeout=5,
                headers=headers,
                allow_redirects=True,
                stream=True,
            )
        ) as response:
            if response.status_code >= 400:
                raise _UrlMetadataError(
                    f"URL responded with status code {response.status_code}"
                )

            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                return {"title": None, "description": None}

            content_chunks: List[str] = []
            total_chars = 0
            for chunk in response.iter_content(chunk_size=2048, decode_unicode=True):
                if not chunk:
                    continue
                content_chunks.append(chunk)
                total_chars += len(chunk)
                if total_chars >= 100_000:
                    break

    except requests.RequestException as exc:
        logger.info("Unable to fetch URL metadata for %s: %s", url, exc)
        raise _UrlMetadataError("Unable to fetch URL") from exc

    parser = _PageMetadataParser()
    parser.feed("".join(content_chunks))
    parser.close()

    return {"title": parser.title, "description": parser.description}


class TopicDocumentCreateRequest(Schema):
    topic_uuid: str
    url: str
    title: Optional[str] = None
    description: Optional[str] = None


class TopicDocumentResponse(Schema):
    id: int
    title: Optional[str] = None
    url: str
    description: Optional[str] = None
    document_type: str
    domain: str
    created_at: datetime


class TopicDocumentListResponse(Schema):
    total: int
    items: List[TopicDocumentResponse]


@router.post("/document/create", response=TopicDocumentResponse)
def create_document(request, payload: TopicDocumentCreateRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    try:
        metadata = _fetch_url_metadata(payload.url)
    except _UrlMetadataError as exc:
        raise HttpError(400, str(exc)) from exc

    document = TopicDocument.objects.create(
        topic=topic,
        url=payload.url,
        title=(payload.title or metadata.get("title") or ""),
        description=(payload.description or metadata.get("description") or ""),
        created_by=user,
    )

    return TopicDocumentResponse(
        id=document.id,
        title=document.display_title,
        url=document.url,
        description=document.description or None,
        document_type=document.document_type,
        domain=document.domain,
        created_at=make_naive(document.created_at),
    )


@router.get("/document/{topic_uuid}/list", response=TopicDocumentListResponse)
def list_documents(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    documents = TopicDocument.objects.filter(topic=topic, is_deleted=False).order_by("-created_at")

    items = [
        TopicDocumentResponse(
            id=document.id,
            title=document.display_title,
            url=document.url,
            description=document.description or None,
            document_type=document.document_type,
            domain=document.domain,
            created_at=make_naive(document.created_at),
        )
        for document in documents
    ]

    return TopicDocumentListResponse(total=len(items), items=items)


@router.delete("/document/{document_id}", response={204: None})
def delete_document(request, document_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        document = TopicDocument.objects.select_related("topic").get(id=document_id)
    except TopicDocument.DoesNotExist:
        raise HttpError(404, "Document not found")

    if document.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    if document.is_deleted:
        return 204, None

    document.is_deleted = True
    document.save(update_fields=["is_deleted"])
    return 204, None


class TopicWebpageCreateRequest(Schema):
    topic_uuid: str
    url: str
    title: Optional[str] = None
    description: Optional[str] = None


class TopicWebpageResponse(Schema):
    id: int
    title: Optional[str] = None
    url: str
    description: Optional[str] = None
    domain: str
    created_at: datetime


class TopicWebpageListResponse(Schema):
    total: int
    items: List[TopicWebpageResponse]


@router.post("/webpage/create", response=TopicWebpageResponse)
def create_webpage(request, payload: TopicWebpageCreateRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    try:
        metadata = _fetch_url_metadata(payload.url)
    except _UrlMetadataError as exc:
        raise HttpError(400, str(exc)) from exc

    webpage = TopicWebpage.objects.create(
        topic=topic,
        url=payload.url,
        title=(payload.title or metadata.get("title") or ""),
        description=(payload.description or metadata.get("description") or ""),
        created_by=user,
    )

    return TopicWebpageResponse(
        id=webpage.id,
        title=webpage.title or None,
        url=webpage.url,
        description=webpage.description or None,
        domain=webpage.domain,
        created_at=make_naive(webpage.created_at),
    )


@router.get("/webpage/{topic_uuid}/list", response=TopicWebpageListResponse)
def list_webpages(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    webpages = TopicWebpage.objects.filter(topic=topic, is_deleted=False).order_by("-created_at")

    items = [
        TopicWebpageResponse(
            id=webpage.id,
            title=webpage.title or None,
            url=webpage.url,
            description=webpage.description or None,
            domain=webpage.domain,
            created_at=make_naive(webpage.created_at),
        )
        for webpage in webpages
    ]

    return TopicWebpageListResponse(total=len(items), items=items)


@router.delete("/webpage/{webpage_id}", response={204: None})
def delete_webpage(request, webpage_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        webpage = TopicWebpage.objects.select_related("topic").get(id=webpage_id)
    except TopicWebpage.DoesNotExist:
        raise HttpError(404, "Webpage not found")

    if webpage.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    if webpage.is_deleted:
        return 204, None

    webpage.is_deleted = True
    webpage.save(update_fields=["is_deleted"])
    return 204, None


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


_TWEET_HOSTS = {'twitter.com', 'mobile.twitter.com', 'x.com'}
_TWEET_PATH_RE = re.compile(r"/status(?:es)?/(?P<id>\d+)")


def _fetch_twitter_embed(url: str) -> str:
    res = requests.get('https://publish.twitter.com/oembed', params={'url': url, 'dnt': 'true'})
    res.raise_for_status()
    data = res.json()
    return data.get('html', '')


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
