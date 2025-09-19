"""API endpoints for managing topic documents and webpages."""

from contextlib import closing
from datetime import datetime
from html.parser import HTMLParser
import logging
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicDocument, TopicWebpage


logger = logging.getLogger(__name__)


class _PageMetadataParser(HTMLParser):
    """Extract title and description values from HTML markup."""

    #: Maximum number of characters to keep when parsing the ``<title>`` tag.
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
        # HTMLParser does not automatically call handle_starttag for self-closing tags.
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
    """Fetch the URL and attempt to read its metadata.

    Returns a dictionary with optional ``title`` and ``description`` keys. Any
    network or HTTP errors result in :class:`_UrlMetadataError` being raised.
    """

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
                if total_chars >= 100_000:  # avoid downloading very large documents
                    break

    except requests.RequestException as exc:
        logger.info("Unable to fetch URL metadata for %s: %s", url, exc)
        raise _UrlMetadataError("Unable to fetch URL") from exc

    parser = _PageMetadataParser()
    parser.feed("".join(content_chunks))
    parser.close()

    return {"title": parser.title, "description": parser.description}


router = Router()


class TopicDocumentCreateRequest(Schema):
    """Payload for creating a new document link."""

    topic_uuid: str
    url: str
    title: Optional[str] = None
    description: Optional[str] = None


class TopicDocumentResponse(Schema):
    """Representation of a stored document link."""

    id: int
    title: Optional[str] = None
    url: str
    description: Optional[str] = None
    document_type: str
    domain: str
    created_at: datetime


class TopicDocumentListResponse(Schema):
    """List response for topic documents."""

    total: int
    items: List[TopicDocumentResponse]


@router.post("/create", response=TopicDocumentResponse)
def create_document(request, payload: TopicDocumentCreateRequest):
    """Add a new document link to a topic owned by the current user."""

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


@router.get("/{topic_uuid}/list", response=TopicDocumentListResponse)
def list_documents(request, topic_uuid: str):
    """Return the list of documents for a topic owned by the user."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    documents = TopicDocument.objects.filter(topic=topic).order_by("-created_at")

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


@router.delete("/{document_id}", response={204: None})
def delete_document(request, document_id: int):
    """Remove a document link from a topic owned by the user."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        document = TopicDocument.objects.select_related("topic").get(id=document_id)
    except TopicDocument.DoesNotExist:
        raise HttpError(404, "Document not found")

    if document.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    document.delete()
    return 204, None


class TopicWebpageCreateRequest(Schema):
    """Payload for creating a new webpage link."""

    topic_uuid: str
    url: str
    title: Optional[str] = None
    description: Optional[str] = None


class TopicWebpageResponse(Schema):
    """Representation of a stored webpage link."""

    id: int
    title: Optional[str] = None
    url: str
    description: Optional[str] = None
    domain: str
    created_at: datetime


class TopicWebpageListResponse(Schema):
    """List response for topic webpages."""

    total: int
    items: List[TopicWebpageResponse]


@router.post("/webpage/create", response=TopicWebpageResponse)
def create_webpage(request, payload: TopicWebpageCreateRequest):
    """Add a new webpage link to a topic owned by the current user."""

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
    """Return the list of webpages for a topic owned by the user."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    webpages = TopicWebpage.objects.filter(topic=topic).order_by("-created_at")

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
    """Remove a webpage link from a topic owned by the user."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        webpage = TopicWebpage.objects.select_related("topic").get(id=webpage_id)
    except TopicWebpage.DoesNotExist:
        raise HttpError(404, "Webpage not found")

    if webpage.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    webpage.delete()
    return 204, None
