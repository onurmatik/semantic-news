"""API endpoints for managing topic documents and webpages."""

from datetime import datetime
from typing import List, Optional

from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicDocument, TopicWebpage


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

    document = TopicDocument.objects.create(
        topic=topic,
        url=payload.url,
        title=payload.title or "",
        description=payload.description or "",
        created_by=user,
    )

    return TopicDocumentResponse(
        id=document.id,
        title=document.title or None,
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
            title=document.title or None,
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

    webpage = TopicWebpage.objects.create(
        topic=topic,
        url=payload.url,
        title=payload.title or "",
        description=payload.description or "",
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
