import base64
import re
from collections.abc import Mapping, Sequence
from typing import Any, Dict, List

from pydantic import BaseModel, HttpUrl

from .base import GenericGenerateAction, Widget, WidgetAction
from .paragraph import _normalise_paragraphs


class ImageSchema(BaseModel):
    prompt: str = ""
    image_url: HttpUrl | None = None


def _build_image_context(context: Dict[str, Any]) -> Dict[str, Any]:
    topic = (context.get("topic_title") or context.get("topic") or "").strip()
    recap = (context.get("latest_recap") or "").strip()
    prompt = (context.get("prompt") or "").strip()
    image_url = (context.get("image_url") or context.get("url") or "").strip()
    previous_paragraphs = _normalise_paragraphs(context.get("previous_paragraphs"))
    next_paragraphs = _normalise_paragraphs(context.get("next_paragraphs"))

    if not previous_paragraphs and not next_paragraphs:
        all_paragraphs = _normalise_paragraphs(context.get("paragraphs"))
        previous_paragraphs = all_paragraphs
        next_paragraphs = []

    return {
        "topic": topic,
        "recap": recap,
        "prompt": prompt,
        "image_url": image_url,
        "previous_paragraphs": previous_paragraphs,
        "next_paragraphs": next_paragraphs,
    }


class GenerateImageAction(GenericGenerateAction):
    tools = ["image_generation"]

    def build_generate_prompt(self, context: Dict[str, Any]) -> str:
        image_context = _build_image_context(context)
        topic = image_context["topic"]
        recap = image_context["recap"]
        prompt_text = image_context["prompt"]
        previous_paragraphs = image_context["previous_paragraphs"]
        next_paragraphs = image_context["next_paragraphs"]
        image_url = image_context["image_url"]

        prompt_parts: List[str] = [
            "You are creating a contextual illustration for this topic.",
            f"Topic title: {topic}" if topic else "",
        ]

        if recap:
            prompt_parts.append("Latest recap of the topic:\n" + recap)
        if previous_paragraphs:
            prompt_parts.append(
                "Paragraphs before this image:\n" + "\n\n".join(previous_paragraphs)
            )
        if next_paragraphs:
            prompt_parts.append(
                "Paragraphs after this image:\n" + "\n\n".join(next_paragraphs)
            )

        if prompt_text:
            prompt_parts.append("Use this image prompt as creative guidance:\n" + prompt_text)
        if image_url:
            prompt_parts.append(
                "If it helps, use this existing image as a reference for the new artwork:\n"
                + image_url
            )

        prompt_parts.append(
            "The illustration should match the flow of the surrounding paragraphs and the topic recap."
            " Provide a single high-quality image output that fits at this position."
        )

        return "\n\n".join(filter(None, prompt_parts))

    def postprocess(
        self,
        *,
        context: Dict[str, Any],
        response: Any,
        raw_response: Any | None = None,
    ) -> Dict[str, Any]:
        return _build_image_content(context=context, response=response, raw_response=raw_response)


class VariateImageAction(WidgetAction):
    name = "variate"
    icon = "bi bi-shuffle"
    tools = ["image_generation"]

    def build_prompt(self, context: Dict[str, Any]) -> str:
        image_context = _build_image_context(context)
        topic = image_context["topic"]
        recap = image_context["recap"]
        prompt_text = image_context["prompt"]
        previous_paragraphs = image_context["previous_paragraphs"]
        next_paragraphs = image_context["next_paragraphs"]
        image_url = image_context["image_url"]

        prompt_parts: List[str] = [
            "Create a contextual variation of an existing illustration.",
            f"Topic title: {topic}" if topic else "",
        ]

        if recap:
            prompt_parts.append("Latest recap of the topic:\n" + recap)
        if previous_paragraphs:
            prompt_parts.append(
                "Paragraphs before this image:\n" + "\n\n".join(previous_paragraphs)
            )
        if next_paragraphs:
            prompt_parts.append(
                "Paragraphs after this image:\n" + "\n\n".join(next_paragraphs)
            )

        if prompt_text:
            prompt_parts.append("Use this image prompt as creative guidance:\n" + prompt_text)

        if image_url:
            prompt_parts.append(
                "Use the following image URL as the base for your variation; keep the scene coherent with the surrounding context:\n"
                + image_url
            )
        else:
            prompt_parts.append(
                "No base image URL is available. Create a new illustration that fits this position and respects the contextual details above."
            )

        prompt_parts.append(
            "Provide a single high-quality image output that matches the flow of the surrounding paragraphs and the topic recap."
        )

        return "\n\n".join(filter(None, prompt_parts))

    def postprocess(
        self,
        *,
        context: Dict[str, Any],
        response: Any,
        raw_response: Any | None = None,
    ) -> Dict[str, Any]:
        return _build_image_content(context=context, response=response, raw_response=raw_response)


class ImageWidget(Widget):
    name = "image"
    icon = "bi bi-image"
    schema = ImageSchema
    form_template = "widgets/image_form.html"
    template = "widgets/image.html"
    actions = [GenerateImageAction, VariateImageAction]


def _build_image_content(
    *,
    context: Dict[str, Any],
    response: Any,
    raw_response: Any | None,
) -> Dict[str, Any]:
    if isinstance(response, Mapping):
        content: Dict[str, Any] = dict(response)
    else:
        content = {"result": response if response is not None else ""}

    image_source = _extract_image_source(raw_response) or _extract_image_source(response)
    normalised_image = _normalise_image_value(image_source)

    if normalised_image:
        content["image_url"] = normalised_image

    content.setdefault("prompt", context.get("prompt", ""))
    content.setdefault("url", "")
    content.setdefault("image_url", "")
    return content


def _extract_image_source(payload: Any) -> str | None:
    if payload is None:
        return None

    if isinstance(payload, Mapping):
        type_hint = str(payload.get("type") or "").lower()
        if "image" in type_hint:
            for key in ("result", "image_url", "image"):
                candidate = payload.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

        for key in ("image_url", "image", "url", "result"):
            candidate = payload.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        outputs = payload.get("output") or payload.get("outputs")
        if isinstance(outputs, Sequence) and not isinstance(outputs, (str, bytes, bytearray)):
            for item in outputs:
                nested = _extract_image_source(item)
                if nested:
                    return nested

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            nested = _extract_image_source(item)
            if nested:
                return nested

    if isinstance(payload, str) and payload.strip():
        return payload.strip()

    return None


def _normalise_image_value(value: str | None) -> str | None:
    if not value:
        return None

    cleaned_value = value.strip()
    if not cleaned_value:
        return None

    if cleaned_value.startswith(("http://", "https://")):
        return cleaned_value

    if cleaned_value.lower().startswith("data:image/"):
        return cleaned_value

    if " " in cleaned_value:
        return None

    if not re.fullmatch(r"[A-Za-z0-9+/=\n\r]+", cleaned_value):
        return None

    try:
        decoded = base64.b64decode(cleaned_value, validate=True)
    except Exception:
        return None

    if not decoded:
        return None

    return f"data:image/png;base64,{cleaned_value}"
