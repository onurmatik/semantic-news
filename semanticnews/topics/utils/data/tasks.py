"""Celery tasks for topic data fetch and search operations."""
from __future__ import annotations

from typing import Any, Dict, List

from celery import shared_task
from django.conf import settings
from ninja import Schema

from ....openai import OpenAI
from semanticnews.prompting import append_default_language_instruction


class _TopicDataResponseSchema(Schema):
    headers: List[str]
    rows: List[List[str]]
    name: str | None = None


class _TopicDataSearchResponseSchema(_TopicDataResponseSchema):
    sources: List[str]
    explanation: str | None = None


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


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def fetch_topic_data_task(self, *, url: str, model: str | None = None) -> Dict[str, Any]:
    """Fetch structured tabular data from a URL using the LLM."""
    resolved_model = _resolve_model(model)
    prompt = (
        f"Fetch the tabular data from {url} and return it as JSON with keys 'headers', 'rows', "
        "and optionally 'name' representing a concise title for the dataset."
    )
    prompt = append_default_language_instruction(prompt)

    parsed = _call_openai(prompt, model=resolved_model, schema=_TopicDataResponseSchema)
    return {
        "headers": parsed.headers,
        "rows": parsed.rows,
        "name": parsed.name,
    }


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def search_topic_data_task(
    self,
    *,
    description: str,
    model: str | None = None,
) -> Dict[str, Any]:
    """Search for tabular data matching a description using the LLM."""
    resolved_model = _resolve_model(model)
    prompt = (
        "Find tabular data that matches the following description and return it as JSON with "
        "keys 'headers', 'rows', 'sources' (a list of URLs), 'name', and optionally 'explanation' "
        "(a brief note if the data does not fully match the request). Description: "
        f"{description}"
    )
    prompt = append_default_language_instruction(prompt)

    parsed = _call_openai(prompt, model=resolved_model, schema=_TopicDataSearchResponseSchema)

    result: Dict[str, Any] = {
        "headers": parsed.headers,
        "rows": parsed.rows,
        "name": parsed.name,
        "sources": parsed.sources,
        "explanation": parsed.explanation,
    }
    return result
