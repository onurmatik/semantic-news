from typing import List

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicData
from ....openai import OpenAI

router = Router()


class TopicDataFetchRequest(Schema):
    topic_uuid: str
    url: str


class TopicDataFetchResponse(Schema):
    headers: List[str]
    rows: List[List[str]]
    name: str | None = None


class TopicDataSaveRequest(Schema):
    topic_uuid: str
    url: str
    name: str | None = None
    headers: List[str]
    rows: List[List[str]]


class TopicDataSaveResponse(Schema):
    success: bool


class _TopicDataResponse(Schema):
    headers: List[str]
    rows: List[List[str]]
    name: str | None = None


@router.post("/fetch", response=TopicDataFetchResponse)
def fetch_data(request, payload: TopicDataFetchRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    prompt = (
        f"Fetch the tabular data from {payload.url} and return it as JSON with keys 'headers', 'rows', and optionally 'name' representing a concise title for the dataset."
    )

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            input=prompt,
            text_format=_TopicDataResponse,
        )

    return TopicDataFetchResponse(
        headers=response.output_parsed.headers,
        rows=response.output_parsed.rows,
        name=response.output_parsed.name,
    )


@router.post("/create", response=TopicDataSaveResponse)
def save_data(request, payload: TopicDataSaveRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    TopicData.objects.create(
        topic=topic,
        url=payload.url,
        name=payload.name,
        data={"headers": payload.headers, "rows": payload.rows},
    )

    return TopicDataSaveResponse(success=True)
