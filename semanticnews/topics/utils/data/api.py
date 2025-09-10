from typing import List

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicData, TopicDataInsight
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


class TopicDataAnalyzeRequest(Schema):
    topic_uuid: str
    data_ids: List[int] | None = None
    insights: List[str] | None = None


class TopicDataAnalyzeResponse(Schema):
    insights: List[str]


class _TopicDataInsightsResponse(Schema):
    insights: List[str]


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


@router.post("/analyze", response=TopicDataAnalyzeResponse)
def analyze_data(request, payload: TopicDataAnalyzeRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if payload.insights:
        for insight in payload.insights:
            TopicDataInsight.objects.create(topic=topic, insight=insight)
        return TopicDataAnalyzeResponse(insights=payload.insights)

    if not payload.data_ids:
        raise HttpError(400, "No data selected")

    datas = TopicData.objects.filter(topic=topic, id__in=payload.data_ids)
    if not datas.exists():
        raise HttpError(404, "No data found")

    tables_text = ""
    for data in datas:
        name = data.name or "Dataset"
        headers = ", ".join(data.data.get("headers", []))
        rows = [", ".join(row) for row in data.data.get("rows", [])]
        tables_text += f"{name}\n{headers}\n" + "\n".join(rows) + "\n\n"

    prompt = (
        "Analyze the following data tables and provide a list of insights."
        " Return a JSON object with a key 'insights' containing a list of strings."
        f"\n\n{tables_text}"
    )

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            input=prompt,
            text_format=_TopicDataInsightsResponse,
        )

    return TopicDataAnalyzeResponse(
        insights=response.output_parsed.insights,
    )
