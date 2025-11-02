"""Execution registry and orchestration for widgets."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping

from django.conf import settings
from django.template import Context, Template
from jsonschema import Draft202012Validator

from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction
from semanticnews.topics.models import TopicSection

from .models import Widget, WidgetAPIExecution

logger = logging.getLogger(__name__)


class WidgetExecutionError(Exception):
    """Base error for widget execution failures."""


class WidgetRegistryLookupError(WidgetExecutionError):
    """Raised when a widget type is not registered with the execution registry."""


class WidgetResponseValidationError(WidgetExecutionError):
    """Raised when an LLM response does not match the declared schema."""


def _serialize_datetime(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_tool_definitions(tool_identifiers: Iterable[Any]) -> list[dict[str, Any]]:
    """Normalise tool identifiers into OpenAI tool definitions."""

    tools: list[dict[str, Any]] = []
    for tool in tool_identifiers or []:
        if isinstance(tool, dict):
            tools.append(tool)
            continue
        if isinstance(tool, str):
            normalized = tool.strip()
            if normalized:
                tools.append({"type": normalized})
    return tools


def _default_context_builder(state: "WidgetExecutionState") -> dict[str, Any]:
    topic = state.section.topic if state.section else state.execution.topic
    section = state.section

    context: dict[str, Any] = {
        "topic": {
            "id": topic.id,
            "uuid": str(topic.uuid),
            "title": topic.title,
        },
        "history": state.history,
        "metadata": state.execution.metadata or {},
    }

    if section:
        context["section"] = {
            "id": section.id,
            "language_code": section.language_code,
            "display_order": section.display_order,
            "status": section.status,
        }

    return context


def _default_prompt_renderer(state: "WidgetExecutionState", context: Mapping[str, Any]) -> str:
    template = Template(state.widget.prompt_template or "")
    return template.render(Context(context))


def _default_postprocess(state: "WidgetExecutionState") -> None:
    """No-op post-processing hook used by default."""

    return None


def _validate_against_schema(data: Any, schema: Mapping[str, Any] | None) -> None:
    if not schema:
        return

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda exc: exc.path)
    if errors:
        error = errors[0]
        raise WidgetResponseValidationError(error.message)


@dataclass
class WidgetExecutionState:
    """Mutable execution state shared across the strategy pipeline."""

    execution: WidgetAPIExecution
    section: TopicSection | None
    widget: Widget
    history: list[dict[str, Any]] = field(default_factory=list)
    context: MutableMapping[str, Any] = field(default_factory=dict)
    rendered_prompt: str = ""
    final_prompt: str = ""
    extra_instructions: str = ""
    model_name: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)
    response_schema: Any | None = None
    raw_response: Any | None = None
    parsed_response: Any | None = None


class WidgetExecutionStrategy:
    """Hook-based strategy that orchestrates widget execution."""

    def __init__(
        self,
        *,
        context_builder: Callable[[WidgetExecutionState], Mapping[str, Any]] | None = None,
        prompt_renderer: Callable[[WidgetExecutionState, Mapping[str, Any]], str] | None = None,
        extra_instructions: str | Callable[[WidgetExecutionState], str | None] | None = None,
        response_schema: Any | None = None,
        preprocess: Callable[[WidgetExecutionState], None] | None = None,
        postprocess: Callable[[WidgetExecutionState], Any] | None = None,
    ) -> None:
        self.context_builder = context_builder or _default_context_builder
        self.prompt_renderer = prompt_renderer or _default_prompt_renderer
        self.extra_instructions_hook = extra_instructions
        self.response_schema = response_schema
        self.preprocess_hook = preprocess
        self.postprocess_hook = postprocess or _default_postprocess

    def execute(self, state: WidgetExecutionState) -> WidgetExecutionState:
        state.context = dict(self.context_builder(state))
        state.rendered_prompt = self.prompt_renderer(state, state.context)
        state.extra_instructions = self._resolve_extra_instructions(state) or ""
        self._run_preprocess(state)
        state.final_prompt = self._combine_prompt(state.rendered_prompt, state.extra_instructions)
        state.raw_response, state.parsed_response = self.call_model(state)
        _validate_against_schema(state.parsed_response, state.widget.response_format)
        postprocessed = self.postprocess_hook(state)
        if postprocessed is not None:
            state.parsed_response = postprocessed
        return state

    def call_model(self, state: WidgetExecutionState) -> tuple[Any, Any]:
        schema = state.response_schema or self.response_schema
        if not schema:
            raise WidgetExecutionError(
                "Widget execution strategy requires a response schema to parse model output."
            )

        with OpenAI() as client:
            response = client.responses.parse(
                model=state.model_name,
                input=state.final_prompt,
                tools=state.tools or None,
                text_format=schema,
            )

        parsed = response.output_parsed
        if hasattr(parsed, "model_dump"):
            parsed_payload = parsed.model_dump()
        elif hasattr(parsed, "dict"):
            parsed_payload = parsed.dict()
        else:
            parsed_payload = parsed

        raw_payload = response.model_dump() if hasattr(response, "model_dump") else json.loads(json.dumps(response))
        return raw_payload, parsed_payload

    def _resolve_extra_instructions(self, state: WidgetExecutionState) -> str | None:
        hook = self.extra_instructions_hook
        if callable(hook):
            return hook(state) or None
        return hook

    def _run_preprocess(self, state: WidgetExecutionState) -> None:
        if self.preprocess_hook:
            self.preprocess_hook(state)

    @staticmethod
    def _combine_prompt(prompt: str, instructions: str | None) -> str:
        prompt_text = prompt or ""
        instructions_text = (instructions or "").strip()
        if instructions_text:
            if prompt_text and not prompt_text.endswith("\n"):
                prompt_text += "\n"
            prompt_text += "\n" if prompt_text.strip() else ""
            prompt_text += instructions_text
        return append_default_language_instruction(prompt_text)


class WidgetExecutionRegistry:
    """Registry mapping widget types to execution strategies."""

    def __init__(self) -> None:
        self._strategies: Dict[str, WidgetExecutionStrategy] = {}

    def register(self, widget_type: str, strategy: WidgetExecutionStrategy) -> None:
        logger.debug("Registering widget strategy for type %s", widget_type)
        self._strategies[widget_type] = strategy

    def unregister(self, widget_type: str) -> None:
        self._strategies.pop(widget_type, None)

    def get(self, widget_type: str) -> WidgetExecutionStrategy:
        try:
            return self._strategies[widget_type]
        except KeyError as exc:
            raise WidgetRegistryLookupError(f"No widget execution strategy registered for '{widget_type}'") from exc


class WidgetExecutionService:
    """High-level orchestrator that executes widgets using the registry."""

    history_limit = 10

    def __init__(self, registry: WidgetExecutionRegistry | None = None) -> None:
        self.registry = registry or widget_registry

    def execute(self, execution: WidgetAPIExecution) -> WidgetExecutionState:
        section = execution.section
        widget = execution.widget
        widget_type = execution.widget_type or widget.name
        strategy = self.registry.get(widget_type)

        history = self._build_history(section or None)

        state = WidgetExecutionState(
            execution=execution,
            section=section,
            widget=widget,
            history=history,
        )

        state.model_name = execution.model_name or execution.metadata.get("model") or settings.DEFAULT_AI_MODEL
        state.tools = execution.tools or _build_tool_definitions(widget.tools)
        state.response_schema = strategy.response_schema

        execution.prompt_template = widget.prompt_template or ""
        execution.tools = state.tools
        execution.model_name = state.model_name
        execution.widget_type = widget_type
        execution.prompt_context = {}
        execution.metadata = execution.metadata or {}

        try:
            state = strategy.execute(state)
        except Exception:
            self._apply_state(execution, state, len(history))
            raise

        self._apply_state(execution, state, len(history))
        return state

    def _build_history(self, section: TopicSection | None) -> list[dict[str, Any]]:
        if section is None:
            return []

        qs = (
            TopicSection.objects.filter(topic=section.topic, widget=section.widget)
            .exclude(pk=section.pk)
            .order_by("-published_at", "-id")[: self.history_limit]
        )

        history: list[dict[str, Any]] = []
        for item in qs:
            history.append(
                {
                    "id": item.id,
                    "status": item.status,
                    "published_at": _serialize_datetime(item.published_at),
                    "language_code": item.language_code,
                    "content": item.content,
                    "error_message": item.error_message,
                }
            )
        return history

    @staticmethod
    def _apply_state(
        execution: WidgetAPIExecution, state: WidgetExecutionState, history_count: int
    ) -> None:
        execution.prompt_context = state.context
        execution.prompt_text = state.final_prompt or state.rendered_prompt
        execution.extra_instructions = state.extra_instructions
        execution.metadata["rendered_prompt"] = state.rendered_prompt
        execution.metadata["history_count"] = history_count
        execution.raw_response = state.raw_response
        execution.parsed_response = state.parsed_response


widget_registry = WidgetExecutionRegistry()
