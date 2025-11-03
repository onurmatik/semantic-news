"""Helper utilities for widget execution and post-processing."""
from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any, Callable, Iterable, Mapping, MutableMapping
from urllib.parse import urlparse
from uuid import uuid4

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import Storage, default_storage
from markdown import markdown as render_markdown

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_LIMIT = 4000


def build_topic_context_snippet(
    topic,
    *,
    metadata: Mapping[str, Any] | None = None,
    max_length: int | None = None,
) -> str:
    """Return a trimmed markdown snippet describing the topic.

    The helper respects optional overrides provided via metadata:

    * ``context_override`` – explicit markdown content to use instead of the
      topic generated context.
    * ``context_limit`` – number of characters to include in the snippet.

    Parameters
    ----------
    topic:
        Topic instance implementing ``build_context``.
    metadata:
        Optional widget metadata dict.
    max_length:
        Optional hard limit for the snippet length.
    """

    metadata = metadata or {}

    if metadata.get("context_override"):
        snippet = str(metadata.get("context_override") or "")
    else:
        snippet = topic.build_context() if hasattr(topic, "build_context") else ""

    limit = max_length or metadata.get("context_limit") or DEFAULT_CONTEXT_LIMIT
    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        limit_value = DEFAULT_CONTEXT_LIMIT

    if limit_value > 0 and len(snippet) > limit_value:
        snippet = snippet[: limit_value - 1].rstrip() + "…"

    return snippet.strip()


def append_extra_instructions(
    *instructions: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    """Combine instruction snippets into a clean, deduplicated block."""

    metadata = metadata or {}

    combined: list[str] = []

    def _append(value: str | None) -> None:
        if not value:
            return
        normalized = str(value).strip()
        if not normalized:
            return
        if normalized not in combined:
            combined.append(normalized)

    for value in instructions:
        _append(value)

    extra = metadata.get("extra_instructions")
    if isinstance(extra, str):
        _append(extra)
    elif isinstance(extra, Iterable):
        for value in extra:
            if isinstance(value, str):
                _append(value)

    return "\n\n".join(combined).strip()


def _resolve_storage(storage: Storage | None = None) -> Storage:
    return storage or default_storage


def fetch_external_assets(
    widget,
    metadata: MutableMapping[str, Any] | None = None,
    *,
    storage: Storage | None = None,
) -> dict[str, Mapping[str, Any]]:
    """Download external assets declared in widget metadata."""

    if metadata is None:
        metadata = {}

    assets = metadata.get("external_assets")
    if not assets:
        return {}

    storage_backend = _resolve_storage(storage)
    resolved: dict[str, Mapping[str, Any]] = {}

    for asset in assets:
        if not isinstance(asset, Mapping):
            continue

        asset_url = asset.get("url")
        if not asset_url:
            continue

        asset_key = asset.get("key") or asset.get("name") or asset_url
        if asset.get("stored_path"):
            stored = {
                "path": asset["stored_path"],
            }
            try:
                stored["url"] = storage_backend.url(asset["stored_path"])
            except Exception:  # pragma: no cover - storage backends may not expose URLs
                stored["url"] = asset["stored_path"]
            resolved[str(asset_key)] = stored
            continue

        timeout = asset.get("timeout") or 10
        try:
            response = requests.get(asset_url, timeout=timeout)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network failures are logged
            logger.warning(
                "Failed to fetch external asset %s for widget %s: %s",
                asset_url,
                getattr(widget, "id", "unknown"),
                exc,
            )
            continue

        filename = asset.get("filename") or os.path.basename(urlparse(asset_url).path)
        if not filename:
            filename = "asset"

        name, ext = os.path.splitext(filename)
        if not ext:
            content_type = response.headers.get("Content-Type", "").split(";")[0]
            guessed_ext = mimetypes.guess_extension(content_type) if content_type else None
            if guessed_ext:
                ext = guessed_ext
        if ext:
            filename = f"{name or 'asset'}{ext}"
        else:
            filename = name or "asset"

        storage_path = asset.get("storage_path") or f"widgets/assets/{uuid4().hex}-{filename}"
        storage_backend.save(storage_path, ContentFile(response.content))

        stored_info = {"path": storage_path}
        try:
            stored_info["url"] = storage_backend.url(storage_path)
        except Exception:  # pragma: no cover - optional URL resolution
            stored_info["url"] = storage_path

        resolved[str(asset_key)] = stored_info

    if resolved:
        metadata.setdefault("resolved_assets", {}).update(resolved)

    return resolved


def _markdown_to_html(value: str) -> str:
    return render_markdown(value, output_format="html5")


def _map_markdown(payload: Any) -> Any:
    if isinstance(payload, str):
        return _markdown_to_html(payload)
    if isinstance(payload, list):
        return [_map_markdown(item) for item in payload]
    if isinstance(payload, Mapping):
        return {key: _map_markdown(value) for key, value in payload.items()}
    return payload


def postprocess_markdown(state) -> Any:
    """Convert markdown responses into HTML while keeping the source."""

    payload = state.parsed_response
    if payload is None:
        return payload

    if isinstance(payload, str):
        return {"markdown": payload, "html": _markdown_to_html(payload)}

    if isinstance(payload, Mapping):
        rendered: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str):
                rendered[key] = {
                    "markdown": value,
                    "html": _markdown_to_html(value),
                }
            else:
                rendered[key] = value
        return rendered

    if isinstance(payload, list):
        rendered_list: list[Any] = []
        for item in payload:
            if isinstance(item, str):
                rendered_list.append({"markdown": item, "html": _markdown_to_html(item)})
            else:
                rendered_list.append(item)
        return rendered_list

    return payload


def postprocess_markdown_to_html(state) -> Any:
    """Convert markdown strings recursively into raw HTML strings."""

    payload = state.parsed_response
    if payload is None:
        return payload
    return _map_markdown(payload)


def postprocess_file_download(
    state,
    *,
    field: str = "download_url",
    target_field: str = "stored_file",
    storage: Storage | None = None,
) -> Any:
    """Download a file referenced in the parsed response and store it."""

    payload = state.parsed_response
    if not isinstance(payload, Mapping):
        return payload

    download_url = payload.get(field)
    if not download_url:
        return payload

    storage_backend = _resolve_storage(storage)

    try:
        response = requests.get(download_url, timeout=10)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - network failures are logged
        logger.warning("Failed to download widget file %s: %s", download_url, exc)
        return payload

    filename = os.path.basename(urlparse(download_url).path) or "download"
    storage_path = f"widgets/downloads/{uuid4().hex}-{filename}"
    storage_backend.save(storage_path, ContentFile(response.content))

    updated = dict(payload)
    updated[target_field] = storage_path
    try:
        updated[f"{target_field}_url"] = storage_backend.url(storage_path)
    except Exception:  # pragma: no cover - optional URL
        updated[f"{target_field}_url"] = storage_path

    return updated


POSTPROCESSORS: Mapping[str, Callable[[Any], Any]] = {
    "markdown": postprocess_markdown,
    "markdown_to_html": postprocess_markdown_to_html,
    "file_download": postprocess_file_download,
}


def resolve_postprocessors(definition: Any) -> list[Callable[[Any], Any]]:
    """Normalise metadata definitions into post-processing callables."""

    if not definition:
        return []

    names: list[str] = []

    if isinstance(definition, str):
        names = [definition]
    elif isinstance(definition, Iterable):
        for item in definition:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, Mapping) and isinstance(item.get("name"), str):
                names.append(item["name"])

    hooks: list[Callable[[Any], Any]] = []
    for name in names:
        lookup = POSTPROCESSORS.get(name)
        if lookup:
            hooks.append(lookup)

    return hooks


__all__ = [
    "append_extra_instructions",
    "build_topic_context_snippet",
    "fetch_external_assets",
    "postprocess_file_download",
    "postprocess_markdown",
    "postprocess_markdown_to_html",
    "POSTPROCESSORS",
    "resolve_postprocessors",
]
