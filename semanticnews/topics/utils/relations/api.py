from typing import List, Optional

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicEntityRelation
from ....openai import OpenAI

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
        f"\n\n{content_md}"
    )

    relation_obj = TopicEntityRelation.objects.create(topic=topic, relations=[])
    try:
        with OpenAI() as client:
            response = client.responses.parse(
                model="gpt-5",
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
