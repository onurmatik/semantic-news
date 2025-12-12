import base64
import re
import uuid
from collections.abc import Mapping, Sequence
from io import BytesIO
from typing import Any, Dict, List

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, HttpUrl

from .base import GenericGenerateAction, Widget, WidgetAction
from .paragraph import _normalise_paragraphs

THUMBNAIL_SIZE = (450, 300)


class ImageSchema(BaseModel):
    prompt: str = ""
    form_image_url: HttpUrl | None = None
    image_data: str | None = None


def _build_image_context(context: Dict[str, Any]) -> Dict[str, Any]:
    topic = (context.get("topic_title") or context.get("topic") or "").strip()
    recap = (context.get("latest_recap") or "").strip()
    prompt = (context.get("prompt") or context.get("form_prompt") or "").strip()
    form_image_url = (context.get("form_image_url") or "").strip()
    image_data = (
        context.get("thumbnail_url")
        or ""
    )
    image_data = image_data.strip() if isinstance(image_data, str) else ""
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
        "form_image_url": form_image_url,
        "image_data": image_data,
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
        form_image_url = image_context["form_image_url"]

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
        if form_image_url:
            prompt_parts.append(
                "Use this existing image as a reference for the new artwork:\n"
                + form_image_url
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
        image_data = image_context["image_data"]
        form_image_url = image_context["form_image_url"]

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

        if image_data:
            prompt_parts.append(
                "Use the following image data as the base for your variation; keep the scene coherent with the surrounding context:\n"
                + image_data
            )
        elif form_image_url:
            prompt_parts.append(
                "Use the following image URL as the base for your variation; keep the scene coherent with the surrounding context:\n"
                + form_image_url
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


def _resolve_topic_and_section(context: Mapping[str, Any]):
    from semanticnews.topics.models import Topic, TopicSection

    section = None
    topic = None

    section_id = context.get("section_id")
    if section_id:
        section = (
            TopicSection.objects.select_related("topic").filter(id=section_id).first()
        )
        topic = getattr(section, "topic", None)

    if topic is None:
        topic_id = context.get("topic_id")
        if topic_id:
            topic = Topic.objects.filter(id=topic_id).first()

    if topic is None:
        topic_uuid = context.get("topic_uuid")
        if topic_uuid:
            topic = Topic.objects.filter(uuid=topic_uuid).first()

    return topic, section


def _decode_image_bytes(value: str) -> tuple[bytes, str] | None:
    if not value:
        return None

    cleaned = value.strip()
    data_match = re.match(r"data:image/(?P<fmt>[A-Za-z0-9.+-]+);base64,(?P<data>.+)", cleaned)

    if data_match:
        fmt = data_match.group("fmt") or "png"
        encoded = data_match.group("data")
    else:
        fmt = "png"
        encoded = cleaned

    try:
        decoded = base64.b64decode(encoded, validate=True)
    except Exception:
        return None

    if not decoded:
        return None

    return decoded, fmt


def _build_thumbnail(image_bytes: bytes, fmt: str) -> bytes | None:
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            image = img.convert("RGB") if img.mode in {"RGBA", "P", "LA"} else img
            image.thumbnail(THUMBNAIL_SIZE)
            buffer = BytesIO()
            image.save(buffer, format=(fmt or "png").upper())
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError):
        return None


def _build_storage_path(
    *, filename: str, extension: str, context: Mapping[str, Any]
) -> str:
    topic, _ = _resolve_topic_and_section(context)
    user_id = getattr(topic, "created_by_id", None) or context.get("user_id") or "anonymous"
    topic_uuid = (
        getattr(topic, "uuid", None)
        or context.get("topic_uuid")
        or context.get("topic_id")
        or "unknown"
    )

    safe_ext = extension.lstrip(".") or "png"
    return f"topics/widgets/image/{user_id}/{topic_uuid}/{filename}.{safe_ext}"


def _persist_image_value(image_value: str, *, context: Mapping[str, Any]) -> Dict[str, Any]:
    persisted: Dict[str, Any] = {}
    if not image_value:
        return persisted

    if image_value.startswith(("http://", "https://")):
        persisted["image_url"] = image_value
        persisted["image_data"] = image_value
        return persisted

    if not image_value.lower().startswith("data:image/"):
        return persisted

    decoded = _decode_image_bytes(image_value)
    if decoded is None:
        return persisted

    raw_bytes, fmt = decoded
    filename_base = uuid.uuid4().hex
    extension = (fmt or "png").split("/")[-1].split("+")[0]

    image_path = _build_storage_path(
        filename=filename_base, extension=extension, context=context
    )
    saved_image_path = default_storage.save(image_path, ContentFile(raw_bytes))
    persisted["image_url"] = default_storage.url(saved_image_path)

    thumb_bytes = _build_thumbnail(raw_bytes, fmt)
    if thumb_bytes:
        thumb_path = _build_storage_path(
            filename=f"{filename_base}_thumb", extension=extension, context=context
        )
        saved_thumb_path = default_storage.save(thumb_path, ContentFile(thumb_bytes))
        persisted["thumbnail_url"] = default_storage.url(saved_thumb_path)

    persisted["image_data"] = persisted.get("thumbnail_url") or persisted["image_url"]
    return persisted


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

    persisted_image = (
        _persist_image_value(normalised_image, context=context) if normalised_image else {}
    )

    for key, value in persisted_image.items():
        if value is not None:
            content[key] = value

    if normalised_image and not persisted_image:
        content["image_data"] = normalised_image

    preview_url = content.get("thumbnail_url") or content.get("image_url")
    if preview_url:
        content["image_data"] = preview_url

    content.setdefault("prompt", context.get("prompt", ""))
    content.setdefault("form_prompt", context.get("form_prompt", context.get("prompt", "")))
    content.setdefault("form_image_url", content.get("image_url") or context.get("form_image_url", ""))
    content.setdefault("image_data", context.get("image_data", ""))
    content.setdefault("image_url", context.get("image_url", ""))
    content.setdefault("thumbnail_url", context.get("thumbnail_url", ""))
    return content


def _extract_image_source(payload: Any) -> str | None:
    if payload is None:
        return None

    if isinstance(payload, Mapping):
        type_hint = str(payload.get("type") or "").lower()
        if "image" in type_hint:
            for key in ("result", "image_data", "image_url", "image"):
                candidate = payload.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

        for key in ("image_data", "image_url", "image", "url", "result"):
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
