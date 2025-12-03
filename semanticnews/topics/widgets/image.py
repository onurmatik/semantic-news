import base64
import re
from collections.abc import Mapping, Sequence
from typing import Any, Dict

from pydantic import BaseModel, HttpUrl

from .base import GenericGenerateAction, Widget, WidgetAction


class ImageSchema(BaseModel):
    prompt: str
    image_url: HttpUrl | None = None


class GenerateImageAction(GenericGenerateAction):
    tools = ["image_generation"]

    def build_generate_prompt(self, context: Dict[str, Any]) -> str:
        prompt_text = context.get("prompt", "")
        return f"Generate a high-quality image based on the following description:\n\n{prompt_text}"

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
        image_url = context.get("image_url")
        return f"Create a variation of the existing image: {image_url}"

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
