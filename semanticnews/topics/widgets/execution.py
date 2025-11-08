"""Execution pipeline for topic widgets."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping, MutableMapping, Sequence

from django.conf import settings
from django.utils import timezone
from slugify import slugify

from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

from .base import Widget, WidgetAction

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from semanticnews.topics.models import TopicSection

logger = logging.getLogger(__name__)


class WidgetExecutionError(RuntimeError):
    """Raised when a widget execution cannot be completed."""


@dataclass
class WidgetExecutionLogEntry:
    """Serializable log entry capturing a single execution attempt."""

    status: str
    created_at: datetime
    prompt: str = ""
    model: str = ""
    tools: list[Mapping[str, Any]] = field(default_factory=list)
    raw_response: Any | None = None
    parsed_response: Any | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "prompt": self.prompt,
            "model": self.model,
            "tools": self.tools,
            "raw_response": _ensure_json_serializable(self.raw_response),
            "parsed_response": _ensure_json_serializable(self.parsed_response),
            "error_message": self.error_message,
        }


@dataclass
class WidgetExecutionRequest:
    """High level execution descriptor passed to the pipeline."""

    section: "TopicSection"
    widget: Widget
    action: WidgetAction
    metadata: MutableMapping[str, Any]
    extra_instructions: str = ""
    model: str | None = None
    tools: Sequence[str | Mapping[str, Any]] | None = None


@dataclass
class WidgetExecutionResult:
    """Result of a pipeline run."""

    content: Mapping[str, Any]
    metadata: MutableMapping[str, Any]
    context: dict[str, Any]
    prompt: str
    model: str
    tools: list[Mapping[str, Any]]
    raw_response: Any | None = None
    parsed_response: Any | None = None
    log_entry: WidgetExecutionLogEntry | None = None


def resolve_widget_action(widget: Widget, identifier: str) -> WidgetAction:
    """Return the action matching the provided identifier."""

    normalized = (identifier or "").strip()
    if not normalized:
        raise WidgetExecutionError("Widget action identifier is required")

    slug = slugify(normalized)
    for action in widget.get_actions():
        action_name = getattr(action, "name", "") or action.__class__.__name__
        if normalized == action_name:
            return action
        if slug and slugify(action_name) == slug:
            return action

    raise WidgetExecutionError(f"Widget action '{identifier}' is not registered for '{widget.name}'")


class WidgetExecutionPipeline:
    """Coordinate prompt building, OpenAI calls and post-processing."""

    def __init__(self) -> None:
        self.default_model = getattr(settings, "DEFAULT_AI_MODEL", "gpt-4.1")

    def execute(self, request: WidgetExecutionRequest) -> WidgetExecutionResult:
        context = self.build_context(request)
        prompt = self.render_prompt(request, context)
        model_name = request.model or str(request.metadata.get("model") or self.default_model)
        tools = normalise_tools(request.tools or getattr(request.action, "tools", None) or [])

        raw_response: Any | None = None
        parsed_response: Any | None = None
        if self._should_call_model(request.action):
            raw_response, parsed_response = self.call_model(
                prompt=prompt,
                model=model_name,
                tools=tools,
                schema=getattr(request.action, "schema", None),
            )
        else:
            parsed_response = request.action.run(context)
            raw_response = parsed_response

        content = self.postprocess(request, context, parsed_response)
        metadata = self.finalize_metadata(request, model_name, tools)

        log_entry = WidgetExecutionLogEntry(
            status="success",
            created_at=timezone.now(),
            prompt=prompt,
            model=model_name,
            tools=tools,
            raw_response=raw_response,
            parsed_response=parsed_response,
        )

        return WidgetExecutionResult(
            content=content,
            metadata=metadata,
            context=context,
            prompt=prompt,
            model=model_name,
            tools=tools,
            raw_response=raw_response,
            parsed_response=parsed_response,
            log_entry=log_entry,
        )

    def build_context(self, request: WidgetExecutionRequest) -> dict[str, Any]:
        section = request.section
        topic = section.topic
        metadata = dict(request.metadata or {})
        context_payload = metadata.get("context")
        context: dict[str, Any]
        if isinstance(context_payload, Mapping):
            context = dict(context_payload)
        else:
            context = dict(metadata)

        if "topic" not in context:
            context["topic"] = getattr(topic, "title", None) or str(getattr(topic, "uuid", ""))
        context.setdefault("topic_title", getattr(topic, "title", ""))
        context.setdefault("topic_uuid", str(getattr(topic, "uuid", "")))
        context.setdefault("topic_id", getattr(topic, "id", None))
        context.setdefault("section_id", section.id)
        if section.language_code:
            context.setdefault("language_code", section.language_code)
        if section.content:
            context.setdefault("content", section.content)

        return context

    def render_prompt(self, request: WidgetExecutionRequest, context: Mapping[str, Any]) -> str:
        base_prompt = request.action.build_prompt(context)
        extra = (request.extra_instructions or "").strip()
        if extra:
            if base_prompt and not base_prompt.endswith("\n"):
                base_prompt += "\n"
            base_prompt = f"{base_prompt}\n\n{extra}" if base_prompt else extra
        return append_default_language_instruction(base_prompt)

    def call_model(
        self,
        *,
        prompt: str,
        model: str,
        tools: Sequence[Mapping[str, Any]] | None,
        schema: Any | None,
    ) -> tuple[Any, Any]:
        with OpenAI() as client:
            if schema:
                response = client.responses.parse(
                    model=model,
                    input=prompt,
                    tools=list(tools) or None,
                    text_format=schema,
                )
                parsed = getattr(response, "output_parsed", None)
            else:
                response = client.responses.create(
                    model=model,
                    input=prompt,
                    tools=list(tools) or None,
                )
                parsed = _extract_response_payload(response)

        if parsed is not None:
            if hasattr(parsed, "model_dump"):
                parsed_payload = parsed.model_dump()
            elif hasattr(parsed, "dict"):
                parsed_payload = parsed.dict()
            else:
                parsed_payload = parsed
        else:
            parsed_payload = None

        raw_payload = response.model_dump() if hasattr(response, "model_dump") else _ensure_json_serializable(response)
        return raw_payload, parsed_payload

    def postprocess(
        self,
        request: WidgetExecutionRequest,
        context: Mapping[str, Any],
        parsed_response: Any,
    ) -> Mapping[str, Any]:
        action = request.action
        if hasattr(action, "postprocess") and callable(action.postprocess):
            result = action.postprocess(context=context, response=parsed_response)
            if result is not None:
                return result
        if isinstance(parsed_response, Mapping):
            return parsed_response
        return {"result": parsed_response}

    def finalize_metadata(
        self,
        request: WidgetExecutionRequest,
        model_name: str,
        tools: Sequence[Mapping[str, Any]],
    ) -> MutableMapping[str, Any]:
        metadata = dict(request.metadata or {})
        metadata.update({
            "model": model_name,
            "tools": list(tools),
        })
        return metadata

    @staticmethod
    def _should_call_model(action: WidgetAction) -> bool:
        run_impl = getattr(action, "run", None)
        if run_impl is None:
            return True
        return run_impl.__func__ is WidgetAction.run  # type: ignore[attr-defined]


def normalise_tools(tools: Sequence[str | Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    normalised: list[Mapping[str, Any]] = []
    for tool in tools:
        if isinstance(tool, Mapping):
            normalised.append(dict(tool))
        elif isinstance(tool, str):
            identifier = tool.strip()
            if identifier:
                normalised.append({"type": identifier})
    return normalised


def _ensure_json_serializable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, Mapping):
            return {key: _ensure_json_serializable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_ensure_json_serializable(item) for item in value]
        return str(value)


def _extract_response_payload(response: Any) -> Any:
    if response is None:
        return None
    if hasattr(response, "output_text"):
        return response.output_text
    if hasattr(response, "choices"):
        choices = getattr(response, "choices")
        if isinstance(choices, Sequence) and choices:
            first = choices[0]
            message = getattr(first, "message", None)
            if message is not None:
                content = getattr(message, "content", None)
                if content is not None:
                    return content
            if hasattr(first, "text"):
                return first.text
    return None


__all__ = [
    "WidgetExecutionPipeline",
    "WidgetExecutionRequest",
    "WidgetExecutionResult",
    "WidgetExecutionLogEntry",
    "WidgetExecutionError",
    "resolve_widget_action",
    "normalise_tools",
]
