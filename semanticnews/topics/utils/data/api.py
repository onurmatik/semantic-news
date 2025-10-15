from typing import List

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from pydantic import Field

from ...models import Topic, TopicModuleLayout
from .models import (
    TopicData,
    TopicDataInsight,
    TopicDataVisualization,
    TopicDataRequest,
    TopicDataAnalysisRequest,
    TopicDataVisualizationRequest,
)
from .tasks import (
    fetch_topic_data_task,
    search_topic_data_task,
    analyze_topic_data_task,
    visualize_topic_data_task,
)
from semanticnews.prompting import append_default_language_instruction

router = Router()


class TopicDataFetchRequest(Schema):
    topic_uuid: str
    url: str


class TopicDataSearchRequest(Schema):
    topic_uuid: str
    description: str


class TopicDataResult(Schema):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    name: str | None = None
    sources: List[str] | None = None
    source: str | None = None
    explanation: str | None = None
    url: str | None = None


class TopicDataSaveRequest(Schema):
    topic_uuid: str
    url: str | None = None
    name: str | None = None
    headers: List[str]
    rows: List[List[str]]
    sources: List[str] | None = None
    explanation: str | None = None
    request_id: int | None = None


class TopicDataSaveResponse(Schema):
    success: bool


class TopicDataAnalyzeRequest(Schema):
    topic_uuid: str
    data_ids: List[int] | None = None
    insights: List[str] | None = None
    instructions: str | None = None
    request_id: int | None = None


class TopicDataAnalyzeTaskResponse(Schema):
    request_id: int
    task_id: str
    status: str
    insights: List[str] = Field(default_factory=list)
    saved: bool
    error: str | None = None


class TopicDataVisualizeRequest(Schema):
    topic_uuid: str
    insight_id: int | None = None
    insight: str | None = None
    chart_type: str | None = None
    instructions: str | None = None
    request_id: int | None = None


class TopicDataVisualizeTaskResponse(Schema):
    request_id: int
    task_id: str
    status: str
    saved: bool
    insight: str | None = None
    chart_type: str | None = None
    chart_data: dict | None = None
    error: str | None = None


class TopicDataTaskResponse(Schema):
    request_id: int
    task_id: str
    status: str
    mode: str
    saved: bool
    result: TopicDataResult | None = None
    error: str | None = None


def _build_task_response(request: TopicDataRequest) -> TopicDataTaskResponse:
    result_payload = request.result if isinstance(request.result, dict) else None
    schema_kwargs = {
        "request_id": request.id,
        "task_id": request.task_id or "",
        "status": request.status,
        "mode": request.mode,
        "saved": request.saved_data_id is not None,
        "error": request.error_message,
    }
    if result_payload is not None:
        normalized_payload = dict(result_payload)
        headers_value = normalized_payload.get("headers")
        if not isinstance(headers_value, list):
            headers_value = []
        normalized_headers = [str(item) for item in headers_value if isinstance(item, str)]
        normalized_payload["headers"] = normalized_headers

        rows_value = normalized_payload.get("rows")
        if not isinstance(rows_value, list):
            rows_value = []
        normalized_rows: List[List[str]] = []
        for row in rows_value:
            if not isinstance(row, list):
                continue
            normalized_row = [str(cell) for cell in row if isinstance(cell, str)]
            normalized_rows.append(normalized_row)
        normalized_payload["rows"] = normalized_rows

        sources_value = normalized_payload.get("sources")
        if not isinstance(sources_value, list):
            sources_value = []
        normalized_sources = [str(item) for item in sources_value if isinstance(item, str)]
        if not normalized_sources and isinstance(normalized_payload.get("source"), str):
            normalized_sources = [normalized_payload["source"]]
        if normalized_sources:
            normalized_payload["sources"] = normalized_sources
            if "source" not in normalized_payload:
                normalized_payload["source"] = normalized_sources[0]
        else:
            normalized_payload["sources"] = []
            normalized_payload.pop("source", None)
        schema_kwargs["result"] = TopicDataResult(**normalized_payload)
    else:
        schema_kwargs["result"] = None
    return TopicDataTaskResponse(**schema_kwargs)


def _build_analysis_task_response(
    request: TopicDataAnalysisRequest,
) -> TopicDataAnalyzeTaskResponse:
    insights: List[str] = []
    if isinstance(request.result, dict):
        raw_insights = request.result.get("insights")
        if isinstance(raw_insights, list):
            insights = [
                str(item).strip()
                for item in raw_insights
                if isinstance(item, str) and str(item).strip()
            ]

    return TopicDataAnalyzeTaskResponse(
        request_id=request.id,
        task_id=request.task_id or "",
        status=request.status,
        insights=insights,
        saved=bool(request.saved_insight_ids),
        error=request.error_message,
    )


def _build_visualization_task_response(
    request: TopicDataVisualizationRequest,
) -> TopicDataVisualizeTaskResponse:
    insight = None
    chart_type = None
    chart_data: dict | None = None
    if isinstance(request.result, dict):
        insight_value = request.result.get("insight")
        if isinstance(insight_value, str):
            insight = insight_value
        chart_type_value = request.result.get("chart_type")
        if isinstance(chart_type_value, str):
            chart_type = chart_type_value
        chart_data_value = request.result.get("chart_data")
        if isinstance(chart_data_value, dict):
            chart_data = chart_data_value

    return TopicDataVisualizeTaskResponse(
        request_id=request.id,
        task_id=request.task_id or "",
        status=request.status,
        saved=bool(request.saved_visualization_id),
        insight=insight,
        chart_type=chart_type,
        chart_data=chart_data,
        error=request.error_message,
    )


def _get_latest_request(
    *,
    user_id: int,
    topic_uuid: str,
    task_id: str | None = None,
    request_id: int | None = None,
) -> TopicDataRequest | None:
    qs = TopicDataRequest.objects.filter(
        user_id=user_id,
        topic__uuid=topic_uuid,
        saved_data__isnull=True,
    )
    if task_id:
        qs = qs.filter(task_id=task_id)
    if request_id:
        qs = qs.filter(id=request_id)
    return qs.order_by("-created_at").first()


def _get_latest_analysis_request(
    *,
    user_id: int,
    topic_uuid: str,
    task_id: str | None = None,
    request_id: int | None = None,
) -> TopicDataAnalysisRequest | None:
    qs = TopicDataAnalysisRequest.objects.filter(
        user_id=user_id,
        topic__uuid=topic_uuid,
    )
    if task_id:
        qs = qs.filter(task_id=task_id)
    if request_id:
        qs = qs.filter(id=request_id)
    return qs.order_by("-created_at").first()


def _get_latest_visualization_request(
    *,
    user_id: int,
    topic_uuid: str,
    task_id: str | None = None,
    request_id: int | None = None,
) -> TopicDataVisualizationRequest | None:
    qs = TopicDataVisualizationRequest.objects.filter(
        user_id=user_id,
        topic__uuid=topic_uuid,
    )
    if task_id:
        qs = qs.filter(task_id=task_id)
    if request_id:
        qs = qs.filter(id=request_id)
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
def data_request_status(
    request,
    topic_uuid: str,
    task_id: str | None = None,
    request_id: int | None = None,
):
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
        request_id=request_id,
    )

    if not data_request:
        raise HttpError(404, "No data request found")

    return _build_task_response(data_request)


@router.get("/analyze/status", response=TopicDataAnalyzeTaskResponse)
def analyze_request_status(
    request,
    topic_uuid: str,
    task_id: str | None = None,
    request_id: int | None = None,
):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    analysis_request = _get_latest_analysis_request(
        user_id=user.id,
        topic_uuid=topic_uuid,
        task_id=task_id,
        request_id=request_id,
    )

    if not analysis_request:
        raise HttpError(404, "No analysis request found")

    return _build_analysis_task_response(analysis_request)


@router.get("/visualize/status", response=TopicDataVisualizeTaskResponse)
def visualize_request_status(
    request,
    topic_uuid: str,
    task_id: str | None = None,
    request_id: int | None = None,
):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    visualization_request = _get_latest_visualization_request(
        user_id=user.id,
        topic_uuid=topic_uuid,
        task_id=task_id,
        request_id=request_id,
    )

    if not visualization_request:
        raise HttpError(404, "No visualization request found")

    return _build_visualization_task_response(visualization_request)


@router.post("/create", response=TopicDataSaveResponse)
def save_data(request, payload: TopicDataSaveRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    matching_request: TopicDataRequest | None = None
    if payload.request_id:
        try:
            matching_request = TopicDataRequest.objects.get(
                id=payload.request_id,
                topic=topic,
                user=user,
            )
        except TopicDataRequest.DoesNotExist:
            matching_request = None

    sources = payload.sources or []
    if payload.url:
        sources = list(sources) + [payload.url]
    sources = [str(url) for url in sources if isinstance(url, str) and url]
    # Remove duplicates while preserving order
    seen = set()
    unique_sources = []
    for url in sources:
        if url in seen:
            continue
        seen.add(url)
        unique_sources.append(url)

    topic_data = TopicData.objects.create(
        topic=topic,
        name=payload.name,
        data={"headers": payload.headers, "rows": payload.rows},
        sources=unique_sources,
        explanation=payload.explanation,
    )

    if matching_request and matching_request.saved_data_id is None:
        TopicDataRequest.objects.filter(id=matching_request.id).update(
            saved_data_id=topic_data.id,
            saved_at=timezone.now(),
            updated_at=timezone.now(),
        )

    return TopicDataSaveResponse(success=True)


@router.post("/analyze", response=TopicDataAnalyzeTaskResponse)
def analyze_data(request, payload: TopicDataAnalyzeRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if payload.insights:
        if not payload.request_id:
            raise HttpError(400, "Request ID required to save insights")
        try:
            analysis_request = TopicDataAnalysisRequest.objects.get(
                id=payload.request_id,
                topic=topic,
                user=user,
            )
        except TopicDataAnalysisRequest.DoesNotExist:
            raise HttpError(404, "Analysis request not found")

        if analysis_request.status != TopicDataAnalysisRequest.Status.SUCCESS:
            raise HttpError(400, "Analysis task is not complete")

        data_ids = analysis_request.input_payload.get("data_ids") if isinstance(analysis_request.input_payload, dict) else None
        if not data_ids:
            raise HttpError(400, "No data associated with this analysis request")

        datas = list(
            TopicData.objects.filter(
                topic=topic,
                id__in=data_ids,
                is_deleted=False,
            )
        )
        if not datas:
            raise HttpError(404, "No data found")

        valid_insights: list[str] = []
        seen: set[str] = set()
        for insight in payload.insights or []:
            if not isinstance(insight, str):
                continue
            normalized = insight.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            valid_insights.append(normalized)

        if not valid_insights:
            raise HttpError(400, "No insights provided")

        created_ids = list(analysis_request.saved_insight_ids or [])
        with transaction.atomic():
            for text in valid_insights:
                insight_obj = (
                    TopicDataInsight.objects.filter(
                        topic=topic,
                        insight=text,
                        is_deleted=False,
                    ).first()
                )
                if not insight_obj:
                    insight_obj = TopicDataInsight.objects.create(topic=topic, insight=text)
                    insight_obj.sources.set(datas)
                else:
                    insight_obj.sources.add(*datas)
                if insight_obj.id not in created_ids:
                    created_ids.append(insight_obj.id)

            TopicDataAnalysisRequest.objects.filter(id=analysis_request.id).update(
                saved_insight_ids=created_ids,
                saved_at=timezone.now(),
                updated_at=timezone.now(),
            )

        analysis_request.refresh_from_db()
        return _build_analysis_task_response(analysis_request)

    if not payload.data_ids:
        raise HttpError(400, "No data selected")

    datas = list(
        TopicData.objects.filter(
            topic=topic,
            id__in=payload.data_ids,
            is_deleted=False,
        )
    )
    if not datas:
        raise HttpError(404, "No data found")

    data_ids = [data.id for data in datas]
    analysis_request = TopicDataAnalysisRequest.objects.create(
        topic=topic,
        user=user,
        status=TopicDataAnalysisRequest.Status.PENDING,
        input_payload={
            "data_ids": data_ids,
            "instructions": payload.instructions or "",
        },
    )

    async_result = analyze_topic_data_task.delay(
        request_id=analysis_request.id,
        topic_id=topic.id,
        data_ids=data_ids,
        instructions=payload.instructions,
        model=settings.DEFAULT_AI_MODEL,
    )

    TopicDataAnalysisRequest.objects.filter(id=analysis_request.id).update(task_id=async_result.id)
    analysis_request.refresh_from_db()

    return _build_analysis_task_response(analysis_request)


def _ensure_visualization_layout_entry(topic: Topic, visualization: TopicDataVisualization) -> None:
    module_key = f"data_visualizations:{visualization.id}"
    exists = TopicModuleLayout.objects.filter(topic=topic, module_key=module_key).exists()
    if exists:
        return

    existing_layouts = list(
        TopicModuleLayout.objects.filter(
            topic=topic, module_key__startswith="data_visualizations:"
        )
    )
    if existing_layouts:
        placement = existing_layouts[0].placement
        placement_orders = [
            layout.display_order for layout in existing_layouts if layout.placement == placement
        ]
        max_order = max(placement_orders) if placement_orders else 0
        display_order = max_order + 1
    else:
        aggregate_layout = (
            TopicModuleLayout.objects.filter(topic=topic, module_key="data_visualizations")
            .order_by("display_order", "id")
            .first()
        )
        if aggregate_layout:
            placement = aggregate_layout.placement
            display_order = aggregate_layout.display_order
        else:
            placement = TopicModuleLayout.PLACEMENT_PRIMARY
            max_order = (
                TopicModuleLayout.objects.filter(topic=topic, placement=placement)
                .aggregate(Max("display_order"))
                .get("display_order__max")
            )
            display_order = (max_order or 0) + 1

    TopicModuleLayout.objects.create(
        topic=topic,
        module_key=module_key,
        placement=placement,
        display_order=display_order,
    )


@router.post("/visualize", response=TopicDataVisualizeTaskResponse)
def visualize_data(request, payload: TopicDataVisualizeRequest):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if payload.request_id:
        try:
            visualization_request = TopicDataVisualizationRequest.objects.get(
                id=payload.request_id,
                topic=topic,
                user=user,
            )
        except TopicDataVisualizationRequest.DoesNotExist:
            raise HttpError(404, "Visualization request not found")

        if visualization_request.status != TopicDataVisualizationRequest.Status.SUCCESS:
            raise HttpError(400, "Visualization task is not complete")

        result = visualization_request.result if isinstance(visualization_request.result, dict) else None
        if not result:
            raise HttpError(400, "Visualization result is unavailable")

        chart_type = result.get("chart_type")
        chart_data = result.get("chart_data")
        if not isinstance(chart_type, str) or not isinstance(chart_data, dict):
            raise HttpError(400, "Visualization result is invalid")

        input_payload = visualization_request.input_payload if isinstance(visualization_request.input_payload, dict) else {}
        insight_id = input_payload.get("insight_id")
        insight_text = result.get("insight") or input_payload.get("insight_text")
        data_ids = input_payload.get("data_ids") or []

        datas = list(
            TopicData.objects.filter(
                topic=topic,
                id__in=data_ids,
                is_deleted=False,
            )
        )
        if not datas:
            raise HttpError(404, "No data found")

        insight_obj = None
        if insight_id:
            insight_obj = TopicDataInsight.objects.filter(
                id=insight_id,
                topic=topic,
                is_deleted=False,
            ).first()
            if insight_obj:
                insight_obj.sources.add(*datas)

        if not insight_obj:
            if not isinstance(insight_text, str) or not insight_text.strip():
                raise HttpError(400, "Insight text is missing")
            normalized_text = insight_text.strip()
            with transaction.atomic():
                insight_obj = (
                    TopicDataInsight.objects.filter(
                        topic=topic,
                        insight=normalized_text,
                        is_deleted=False,
                    ).first()
                )
                if insight_obj:
                    insight_obj.sources.add(*datas)
                else:
                    insight_obj = TopicDataInsight.objects.create(
                        topic=topic,
                        insight=normalized_text,
                    )
                    insight_obj.sources.set(datas)

        with transaction.atomic():
            visualization = TopicDataVisualization.objects.create(
                topic=topic,
                insight=insight_obj,
                chart_type=chart_type,
                chart_data=chart_data,
            )
            _ensure_visualization_layout_entry(topic, visualization)

            TopicDataVisualizationRequest.objects.filter(id=visualization_request.id).update(
                saved_visualization=visualization,
                saved_at=timezone.now(),
                updated_at=timezone.now(),
            )

        visualization_request.refresh_from_db()
        return _build_visualization_task_response(visualization_request)

    if payload.insight_id is not None:
        try:
            insight_obj = TopicDataInsight.objects.get(
                id=payload.insight_id,
                topic=topic,
                is_deleted=False,
            )
        except TopicDataInsight.DoesNotExist:
            raise HttpError(404, "Insight not found")
        insight_text = insight_obj.insight
        data_ids = list(
            insight_obj.sources.filter(is_deleted=False).values_list("id", flat=True)
        )
    elif payload.insight:
        insight_obj = None
        insight_text = payload.insight.strip()
        data_ids = list(
            TopicData.objects.filter(topic=topic, is_deleted=False).values_list("id", flat=True)
        )
    else:
        raise HttpError(400, "Insight not provided")

    if not data_ids:
        raise HttpError(404, "No data available for visualization")

    visualization_request = TopicDataVisualizationRequest.objects.create(
        topic=topic,
        user=user,
        status=TopicDataVisualizationRequest.Status.PENDING,
        input_payload={
            "data_ids": data_ids,
            "insight_id": insight_obj.id if insight_obj else None,
            "insight_text": insight_text,
            "chart_type": payload.chart_type or "",
            "instructions": payload.instructions or "",
        },
    )

    async_result = visualize_topic_data_task.delay(
        request_id=visualization_request.id,
        topic_id=topic.id,
        data_ids=data_ids,
        insight=insight_text,
        chart_type=payload.chart_type,
        instructions=payload.instructions,
        model=settings.DEFAULT_AI_MODEL,
    )

    TopicDataVisualizationRequest.objects.filter(id=visualization_request.id).update(task_id=async_result.id)
    visualization_request.refresh_from_db()

    return _build_visualization_task_response(visualization_request)


@router.delete("/visualization/{visualization_id}", response=TopicDataSaveResponse)
def delete_visualization(request, visualization_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        visualization = TopicDataVisualization.objects.select_related("topic").get(id=visualization_id)
    except TopicDataVisualization.DoesNotExist:
        raise HttpError(404, "Visualization not found")

    if visualization.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    module_key = f"data_visualizations:{visualization.id}"
    if visualization.is_deleted:
        return TopicDataSaveResponse(success=True)

    with transaction.atomic():
        TopicModuleLayout.objects.filter(
            topic=visualization.topic, module_key=module_key
        ).delete()
        visualization.delete()
        visualization.is_deleted = True
        visualization.save(update_fields=["is_deleted"])

    return TopicDataSaveResponse(success=True)
