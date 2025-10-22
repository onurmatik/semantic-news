"""Celery tasks for topic data operations."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from ninja import Schema
from pydantic import Field

from ....openai import OpenAI
from semanticnews.prompting import append_default_language_instruction
from .models import (
    TopicData,
    TopicDataRequest,
    TopicDataAnalysisRequest,
    TopicDataVisualizationRequest,
)


_UNSET = object()


class _TopicDataResponseSchema(Schema):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    name: str | None = None


class _TopicDataSearchResponseSchema(_TopicDataResponseSchema):
    sources: List[str] = Field(default_factory=list)
    explanation: str | None = None


class _TopicDataInsightsResponseSchema(Schema):
    insights: List[str] = Field(default_factory=list)


class _ChartDatasetSchema(Schema):
    label: str
    data: List[float]


class _ChartDataSchema(Schema):
    labels: List[str]
    datasets: List[_ChartDatasetSchema]


class _TopicDataVisualizationResponseSchema(Schema):
    chart_type: str
    data: _ChartDataSchema


def _update_request(
    request_id: int,
    *,
    status: TopicDataRequest.Status | None = None,
    result: Dict[str, Any] | None | object = _UNSET,
    error_message: str | None | object = _UNSET,
) -> None:
    """Persist status updates for a TopicDataRequest instance."""

    updates: Dict[str, Any] = {"updated_at": timezone.now()}
    if status is not None:
        updates["status"] = status
    if result is not _UNSET:
        updates["result"] = result
    if error_message is not _UNSET:
        updates["error_message"] = error_message

    TopicDataRequest.objects.filter(id=request_id).update(**updates)


def _update_analysis_request(
    request_id: int,
    *,
    status: TopicDataAnalysisRequest.Status | None = None,
    result: Dict[str, Any] | None | object = _UNSET,
    error_message: str | None | object = _UNSET,
) -> None:
    """Persist status updates for a TopicDataAnalysisRequest instance."""

    updates: Dict[str, Any] = {"updated_at": timezone.now()}
    if status is not None:
        updates["status"] = status
    if result is not _UNSET:
        updates["result"] = result
    if error_message is not _UNSET:
        updates["error_message"] = error_message

    TopicDataAnalysisRequest.objects.filter(id=request_id).update(**updates)


def _update_visualization_request(
    request_id: int,
    *,
    status: TopicDataVisualizationRequest.Status | None = None,
    result: Dict[str, Any] | None | object = _UNSET,
    error_message: str | None | object = _UNSET,
) -> None:
    """Persist status updates for a TopicDataVisualizationRequest instance."""

    updates: Dict[str, Any] = {"updated_at": timezone.now()}
    if status is not None:
        updates["status"] = status
    if result is not _UNSET:
        updates["result"] = result
    if error_message is not _UNSET:
        updates["error_message"] = error_message

    TopicDataVisualizationRequest.objects.filter(id=request_id).update(**updates)


def _call_openai(prompt: str, *, model: str, schema: type[Schema]) -> Schema:
    """Execute the OpenAI call and return the parsed response."""
    with OpenAI() as client:
        response = client.responses.parse(
            model=model,
            input=prompt,
            tools=[{"type": "web_search_preview"}],
            text_format=schema,
        )
    return response.output_parsed


def _resolve_model(model: str | None) -> str:
    """Return the provided model or fall back to the default configured model."""
    if model:
        return model
    return settings.DEFAULT_AI_MODEL


def _build_tables_text(datas: Iterable[TopicData]) -> str:
    """Convert TopicData rows to a textual representation for prompting."""

    tables_text = ""
    for data in datas:
        name = data.name or "Dataset"
        headers = ", ".join(data.data.get("headers", []))
        rows = [", ".join(row) for row in data.data.get("rows", [])]
        tables_text += f"{name}\n{headers}\n" + "\n".join(rows) + "\n\n"
    return tables_text


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def fetch_topic_data_task(
    self, *, request_id: int, url: str, model: str | None = None
) -> Dict[str, Any]:
    """Fetch structured tabular data from a URL using the LLM."""
    _update_request(
        request_id,
        status=TopicDataRequest.Status.STARTED,
        result=None,
        error_message=None,
    )
    resolved_model = _resolve_model(model)
    prompt = (
        f"Fetch the tabular data from {url} and return it as JSON with keys 'headers', 'rows', "
        "and optionally 'name' representing a concise title for the dataset. Use concise, "
        "human-readable column headers (ideally < 15, max 20 chars). If anything about the "
        "data is ambiguous, infer the most reasonable interpretation and continue without "
        "asking for clarification."
    )
    prompt = append_default_language_instruction(prompt)

    try:
        parsed = _call_openai(prompt, model=resolved_model, schema=_TopicDataResponseSchema)
    except Exception as exc:
        _update_request(
            request_id,
            status=TopicDataRequest.Status.FAILURE,
            result=None,
            error_message=str(exc),
        )
        raise

    result: Dict[str, Any] = {
        "headers": parsed.headers,
        "rows": parsed.rows,
        "name": parsed.name,
        "sources": [url],
        "url": url,
    }
    _update_request(
        request_id,
        status=TopicDataRequest.Status.SUCCESS,
        result=result,
        error_message=None,
    )
    return result


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def search_topic_data_task(
    self,
    *,
    request_id: int,
    description: str,
    model: str | None = None,
) -> Dict[str, Any]:
    """Search for tabular data matching a description using the LLM."""
    _update_request(
        request_id,
        status=TopicDataRequest.Status.STARTED,
        result=None,
        error_message=None,
    )
    resolved_model = _resolve_model(model)
    prompt = (
        "Find tabular data that matches the following description and return it as JSON with "
        "keys 'headers', 'rows', 'sources' (a list of direct URLs where the tabular data appears), "
        "'name' (short dataset label), and optionally 'explanation' (a brief note if the data does not fully match the request). "
        "Prioritize official or primary sources maintained by the organization that produced the data "
        "(e.g., government statistical offices, regulators, or research institutes). "
        "Include only the minimum number of sources required to cover the dataset (typically one per organization) "
        "and avoid listing multiple URLs that reflect the same underlying data. "
        "Each entry in 'sources' must point directly to a page containing the data, not to a summary, news coverage, PDF download page or search results. "
        "Aim for the most up to date data from the first source. "
        "If the only available data is outdated or from a secondary source, "
        "still return it but include an 'explanation' that clearly states the limitation. "
        f"Description: {description}"
    )
    prompt = append_default_language_instruction(prompt)

    try:
        parsed = _call_openai(
            prompt, model=resolved_model, schema=_TopicDataSearchResponseSchema
        )
    except Exception as exc:
        _update_request(
            request_id,
            status=TopicDataRequest.Status.FAILURE,
            result=None,
            error_message=str(exc),
        )
        raise

    sources = [url for url in parsed.sources if isinstance(url, str) and url]
    unique_sources: list[str] = []
    seen_sources: set[str] = set()
    for source in sources:
        normalized = source.strip()
        if not normalized:
            continue
        if normalized in seen_sources:
            continue
        seen_sources.add(normalized)
        unique_sources.append(normalized)
    result: Dict[str, Any] = {
        "headers": parsed.headers,
        "rows": parsed.rows,
        "name": parsed.name,
        "sources": unique_sources,
        "explanation": parsed.explanation,
        "url": unique_sources[0] if unique_sources else None,
    }
    _update_request(
        request_id,
        status=TopicDataRequest.Status.SUCCESS,
        result=result,
        error_message=None,
    )
    return result


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def analyze_topic_data_task(
    self,
    *,
    request_id: int,
    topic_id: int,
    data_ids: List[int],
    instructions: str | None = None,
    model: str | None = None,
) -> Dict[str, Any]:
    """Analyze selected topic data tables and return insights."""

    _update_analysis_request(
        request_id,
        status=TopicDataAnalysisRequest.Status.STARTED,
        result=None,
        error_message=None,
    )

    datas = list(
        TopicData.objects.filter(
            topic_id=topic_id,
            id__in=data_ids,
            is_deleted=False,
        )
    )
    if not datas:
        message = "No data available for analysis"
        _update_analysis_request(
            request_id,
            status=TopicDataAnalysisRequest.Status.FAILURE,
            result=None,
            error_message=message,
        )
        raise ValueError(message)

    resolved_model = _resolve_model(model)
    tables_text = _build_tables_text(datas)
    prompt = (
        "Analyze the following data tables and provide up to three of the most "
        "significant insights. Return a JSON object with a key 'insights' "
        "containing a list of strings."
    )
    if instructions:
        prompt += f" Please consider the following user instructions: {instructions}"
    prompt = append_default_language_instruction(prompt)
    prompt += f"\n\n{tables_text}"

    try:
        parsed = _call_openai(
            prompt,
            model=resolved_model,
            schema=_TopicDataInsightsResponseSchema,
        )
    except Exception as exc:
        _update_analysis_request(
            request_id,
            status=TopicDataAnalysisRequest.Status.FAILURE,
            result=None,
            error_message=str(exc),
        )
        raise

    insights = [
        insight.strip()
        for insight in parsed.insights
        if isinstance(insight, str) and insight.strip()
    ][:3]
    result: Dict[str, Any] = {"insights": insights}
    _update_analysis_request(
        request_id,
        status=TopicDataAnalysisRequest.Status.SUCCESS,
        result=result,
        error_message=None,
    )
    return result


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def visualize_topic_data_task(
    self,
    *,
    request_id: int,
    topic_id: int,
    data_ids: List[int],
    insight: str,
    chart_type: str | None = None,
    instructions: str | None = None,
    model: str | None = None,
) -> Dict[str, Any]:
    """Generate chart data for a topic insight."""

    _update_visualization_request(
        request_id,
        status=TopicDataVisualizationRequest.Status.STARTED,
        result=None,
        error_message=None,
    )

    datas = list(
        TopicData.objects.filter(
            topic_id=topic_id,
            id__in=data_ids,
            is_deleted=False,
        )
    )
    if not datas:
        message = "No data available for visualization"
        _update_visualization_request(
            request_id,
            status=TopicDataVisualizationRequest.Status.FAILURE,
            result=None,
            error_message=message,
        )
        raise ValueError(message)

    resolved_model = _resolve_model(model)
    tables_section = f"Insight: {insight}\n\n{_build_tables_text(datas)}"
    if chart_type:
        prompt = (
            "Given the following insight and data tables, provide the chart data for a "
            f"{chart_type} chart in JSON with keys 'chart_type' and 'data'. "
            "The 'data' should include 'labels' and 'datasets' formatted for Chart.js."
        )
    else:
        prompt = (
            "Given the following insight and data tables, choose an appropriate basic chart "
            "type (bar, line, pie, etc.) and provide the chart data in JSON with keys "
            "'chart_type' and 'data'. The 'data' should include 'labels' and 'datasets' "
            "formatted for Chart.js."
        )
    if instructions:
        prompt += f" Please consider the following user instructions: {instructions}"
    prompt = append_default_language_instruction(prompt)
    prompt += f"\n\n{tables_section}"

    try:
        parsed = _call_openai(
            prompt,
            model=resolved_model,
            schema=_TopicDataVisualizationResponseSchema,
        )
    except Exception as exc:
        _update_visualization_request(
            request_id,
            status=TopicDataVisualizationRequest.Status.FAILURE,
            result=None,
            error_message=str(exc),
        )
        raise

    final_chart_type = chart_type or parsed.chart_type
    result: Dict[str, Any] = {
        "chart_type": final_chart_type,
        "chart_data": parsed.data.dict(),
        "insight": insight,
    }
    _update_visualization_request(
        request_id,
        status=TopicDataVisualizationRequest.Status.SUCCESS,
        result=result,
        error_message=None,
    )
    return result
