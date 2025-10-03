"""Celery tasks for topic data fetch and search operations."""
from __future__ import annotations

from typing import Any, Dict, List

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from ninja import Schema
from pydantic import Field

from ....openai import OpenAI
from semanticnews.prompting import append_default_language_instruction
from .models import TopicDataRequest


_UNSET = object()


class _TopicDataResponseSchema(Schema):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    name: str | None = None


class _TopicDataSearchResponseSchema(_TopicDataResponseSchema):
    sources: List[str] = Field(default_factory=list)
    explanation: str | None = None


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
        "and optionally 'name' representing a concise title for the dataset."
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
        "keys 'headers', 'rows', 'sources' (a list of direct URLs where the tabular data "
        "appears), 'name', and optionally 'explanation' (a brief note if the data does not fully "
        "match the request). Each entry in 'sources' must point directly to a page containing the "
        "table, not to a summary or search results. Description: "
        f"{description}"
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
    result: Dict[str, Any] = {
        "headers": parsed.headers,
        "rows": parsed.rows,
        "name": parsed.name,
        "sources": sources,
        "explanation": parsed.explanation,
        "url": sources[0] if sources else None,
    }
    _update_request(
        request_id,
        status=TopicDataRequest.Status.SUCCESS,
        result=result,
        error_message=None,
    )
    return result
