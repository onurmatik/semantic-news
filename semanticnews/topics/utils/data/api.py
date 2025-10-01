from typing import List

from django.conf import settings
from ninja import Router, Schema
from ninja.errors import HttpError
from pydantic import ConfigDict

from ...models import Topic
from .models import TopicData, TopicDataInsight, TopicDataVisualization, TopicDataRequest
from ....openai import OpenAI
from .tasks import fetch_topic_data_task, search_topic_data_task
from semanticnews.prompting import append_default_language_instruction

router = Router()


class TopicDataFetchRequest(Schema):
    topic_uuid: str
    url: str



class TopicDataSearchRequest(Schema):
    topic_uuid: str
    description: str


class TopicDataResult(Schema):
    headers: List[str]
    rows: List[List[str]]
    name: str | None = None
    sources: List[str] | None = None
    explanation: str | None = None
    url: str | None = None


class TopicDataSaveRequest(Schema):
    topic_uuid: str
    url: str
    name: str | None = None
    headers: List[str]
    rows: List[List[str]]


class TopicDataSaveResponse(Schema):
    success: bool


class TopicDataAnalyzeRequest(Schema):
    topic_uuid: str
    data_ids: List[int] | None = None
    insights: List[str] | None = None
    instructions: str | None = None


class TopicDataAnalyzeResponse(Schema):
    insights: List[str]


class _TopicDataInsightsResponse(Schema):
    insights: List[str]


class TopicDataVisualizeRequest(Schema):
    topic_uuid: str
    insight_id: int | None = None
    insight: str | None = None
    chart_type: str | None = None


class _ChartDataset(Schema):
    model_config = ConfigDict(extra="forbid")

    label: str
    data: List[float]


class _ChartData(Schema):
    model_config = ConfigDict(extra="forbid")

    labels: List[str]
    datasets: List[_ChartDataset]


class _TopicDataVisualizationResponse(Schema):
    model_config = ConfigDict(extra="forbid")

    chart_type: str
    data: _ChartData


class TopicDataVisualizeResponse(Schema):
    id: int
    insight: str
    chart_type: str
    chart_data: dict


class TopicDataTaskResponse(Schema):
    task_id: str
    status: str
    mode: str
    result: TopicDataResult | None = None
    error: str | None = None


def _build_task_response(request: TopicDataRequest) -> TopicDataTaskResponse:
    result_payload = request.result if isinstance(request.result, dict) else None
    schema_kwargs = {
        "task_id": request.task_id or "",
        "status": request.status,
        "mode": request.mode,
        "error": request.error_message,
    }
    if result_payload is not None:
        schema_kwargs["result"] = TopicDataResult(**result_payload)
    else:
        schema_kwargs["result"] = None
    return TopicDataTaskResponse(**schema_kwargs)


def _get_latest_request(
    *, user_id: int, topic_uuid: str, task_id: str | None = None
) -> TopicDataRequest | None:
    qs = TopicDataRequest.objects.filter(
        user_id=user_id,
        topic__uuid=topic_uuid,
    )
    if task_id:
        qs = qs.filter(task_id=task_id)
    return qs.order_by("-created_at").first()


@router.post("/fetch", response=TopicDataTaskResponse)
def fetch_data(request, payload: TopicDataFetchRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    data_request = TopicDataRequest.objects.create(
        topic=topic,
        user=user,
        mode=TopicDataRequest.Mode.URL,
        status=TopicDataRequest.Status.PENDING,
        input_payload={"url": payload.url},
    )

    async_result = fetch_topic_data_task.delay(
        request_id=data_request.id,
        url=payload.url,
        model=settings.DEFAULT_AI_MODEL,
    )

    TopicDataRequest.objects.filter(id=data_request.id).update(task_id=async_result.id)
    data_request.refresh_from_db()

    return _build_task_response(data_request)



@router.post("/search", response=TopicDataTaskResponse)
def search_data(request, payload: TopicDataSearchRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    data_request = TopicDataRequest.objects.create(
        topic=topic,
        user=user,
        mode=TopicDataRequest.Mode.SEARCH,
        status=TopicDataRequest.Status.PENDING,
        input_payload={"description": payload.description},
    )

    async_result = search_topic_data_task.delay(
        request_id=data_request.id,
        description=payload.description,
        model=settings.DEFAULT_AI_MODEL,
    )

    TopicDataRequest.objects.filter(id=data_request.id).update(task_id=async_result.id)
    data_request.refresh_from_db()

    return _build_task_response(data_request)


@router.get("/status", response=TopicDataTaskResponse)
def data_request_status(request, topic_uuid: str, task_id: str | None = None):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    data_request = _get_latest_request(
        user_id=user.id,
        topic_uuid=topic_uuid,
        task_id=task_id,
    )

    if not data_request:
        raise HttpError(404, "No data request found")

    return _build_task_response(data_request)


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
        if not payload.data_ids:
            raise HttpError(400, "No data selected")
        datas = TopicData.objects.filter(topic=topic, id__in=payload.data_ids)
        if not datas.exists():
            raise HttpError(404, "No data found")
        for insight in payload.insights:
            insight_obj = TopicDataInsight.objects.create(topic=topic, insight=insight)
            insight_obj.sources.set(datas)
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
        "Analyze the following data tables and provide up to three of the most"
        " significant insights. Return a JSON object with a key 'insights'"
        " containing a list of strings."
    )
    if payload.instructions:
        prompt += f" Please consider the following user instructions: {payload.instructions}"
    prompt = append_default_language_instruction(prompt)
    prompt += f"\n\n{tables_text}"

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            input=prompt,
            text_format=_TopicDataInsightsResponse,
        )

    insights = response.output_parsed.insights

    return TopicDataAnalyzeResponse(insights=insights[:3])


@router.post("/visualize", response=TopicDataVisualizeResponse)
def visualize_data(request, payload: TopicDataVisualizeRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if payload.insight_id is not None:
        try:
            insight_obj = TopicDataInsight.objects.get(id=payload.insight_id, topic=topic)
        except TopicDataInsight.DoesNotExist:
            raise HttpError(404, "Insight not found")
        insight_text = insight_obj.insight
        sources = insight_obj.sources.all()
    elif payload.insight:
        insight_obj = None
        insight_text = payload.insight
        sources = TopicData.objects.filter(topic=topic)
    else:
        raise HttpError(400, "Insight not provided")

    tables_text = ""
    for data in sources:
        name = data.name or "Dataset"
        headers = ", ".join(data.data.get("headers", []))
        rows = [", ".join(row) for row in data.data.get("rows", [])]
        tables_text += f"{name}\n{headers}\n" + "\n".join(rows) + "\n\n"

    tables_section = f"Insight: {insight_text}\n\n{tables_text}"
    if payload.chart_type:
        prompt = (
            "Given the following insight and data tables, provide the chart data for a "
            f"{payload.chart_type} chart in JSON with keys 'chart_type' and 'data'. "
            "The 'data' should include 'labels' and 'datasets' formatted for Chart.js."
        )
    else:
        prompt = (
            "Given the following insight and data tables, choose an appropriate basic chart "
            "type (bar, line, pie, etc.) and provide the chart data in JSON with keys "
            "'chart_type' and 'data'. The 'data' should include 'labels' and 'datasets' "
            "formatted for Chart.js."
        )
    prompt = append_default_language_instruction(prompt)
    prompt += f"\n\n{tables_section}"

    with OpenAI() as client:
        response = client.responses.parse(
            model="gpt-5",
            input=prompt,
            text_format=_TopicDataVisualizationResponse,
        )

    visualization = TopicDataVisualization.objects.create(
        topic=topic,
        insight=insight_obj,
        chart_type=payload.chart_type or response.output_parsed.chart_type,
        chart_data=response.output_parsed.data.dict(),
    )

    return TopicDataVisualizeResponse(
        id=visualization.id,
        insight=insight_text,
        chart_type=visualization.chart_type,
        chart_data=visualization.chart_data,
    )
