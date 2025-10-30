from typing import List, Optional
from datetime import datetime

from django.conf import settings
from ninja import Router, Schema
from ninja.errors import HttpError
from django.utils.timezone import make_naive
from semanticnews.topics.models import Topic
from .models import TopicEntityRelation
from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

router = Router()


class EntityRelation(Schema):
    source: str
    relation: str
    target: str


class TopicEntityRelationCreateRequest(Schema):
    """Request body for creating or suggesting entity relations."""

    topic_uuid: str
    relations: Optional[List[EntityRelation]] = None


class TopicEntityRelationCreateResponse(Schema):
    """Response returned after creating or suggesting entity relations."""

    relations: List[EntityRelation]


class _TopicEntityRelationResponse(Schema):
    relations: List[EntityRelation]


@router.post("/extract", response=TopicEntityRelationCreateResponse)
def extract_entity_relations(request, payload: TopicEntityRelationCreateRequest):
    """Create entity relations or return an AI-generated suggestion."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if payload.relations is not None:
        relation_obj = TopicEntityRelation.objects.create(
            topic=topic,
            relations=[r.dict() for r in payload.relations],
            status="finished",
        )
        return TopicEntityRelationCreateResponse(relations=[EntityRelation(**r) for r in relation_obj.relations])

    content_md = topic.build_context()
    prompt = (
        f"Below is a set of events and contents about {topic.title}. "
        "Identify the key entities and the relations between them. "
        "Respond with a JSON object containing a list 'relations' where each item has "
        "'source', 'relation', and 'target' fields. "
    )
    prompt = append_default_language_instruction(prompt)
    prompt += f"\n\n{content_md}"

    relation_obj = TopicEntityRelation.objects.create(topic=topic, relations=[])
    try:
        with OpenAI() as client:
            response = client.responses.parse(
                model=settings.DEFAULT_AI_MODEL,
                input=prompt,
                text_format=_TopicEntityRelationResponse,
            )
        relations = response.output_parsed.relations
        relation_obj.relations = [r.dict() for r in relations]
        relation_obj.status = "finished"
        relation_obj.error_message = None
        relation_obj.error_code = None
        relation_obj.save(update_fields=[
            "relations",
            "status",
            "error_message",
            "error_code",
        ])
        return TopicEntityRelationCreateResponse(relations=relations)
    except Exception as e:
        relation_obj.status = "error"
        relation_obj.error_message = str(e)
        relation_obj.save(update_fields=["status", "error_message"])
        return TopicEntityRelationCreateResponse(relations=[EntityRelation(**r) for r in relation_obj.relations])


class TopicEntityRelationItem(Schema):
    id: int
    relations: List[EntityRelation]
    created_at: datetime


class TopicEntityRelationListResponse(Schema):
    total: int
    items: List[TopicEntityRelationItem]


@router.get("/{topic_uuid}/list", response=TopicEntityRelationListResponse)
def list_entity_relations(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")
    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")
    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    relations = (
        TopicEntityRelation.objects
        .filter(topic=topic, status="finished", is_deleted=False)
        .order_by("created_at")
        .values("id", "relations", "created_at")
    )

    items = [
        TopicEntityRelationItem(
            id=r["id"],
            relations=[EntityRelation(**rel) for rel in r["relations"]],
            created_at=make_naive(r["created_at"]),
        )
        for r in relations
    ]
    return TopicEntityRelationListResponse(total=len(items), items=items)


@router.delete("/{relation_id}", response={204: None})
def delete_entity_relation(request, relation_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        relation = TopicEntityRelation.objects.select_related("topic").get(id=relation_id)
    except TopicEntityRelation.DoesNotExist:
        raise HttpError(404, "Relation not found")

    if relation.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    if relation.is_deleted:
        return 204, None

    relation.is_deleted = True
    relation.save(update_fields=["is_deleted"])
    return 204, None
