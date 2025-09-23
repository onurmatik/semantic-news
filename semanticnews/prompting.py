"""Shared prompt utilities for Semantic News AI interactions."""

from collections.abc import Iterable

from django.conf import settings
from django.utils.translation import get_language_info


_DEFAULT_LANGUAGE_CODE = "en"
_DEFAULT_LANGUAGE_NAME = "English"


def get_default_language_instruction() -> str:
    """Return the instruction to respond in the configured default language."""

    language_name = _DEFAULT_LANGUAGE_NAME

    if getattr(settings, "configured", False):
        language_code = getattr(settings, "LANGUAGE_CODE", _DEFAULT_LANGUAGE_CODE)
        resolved_name = _resolve_language_name(language_code, getattr(settings, "LANGUAGES", ()))
        if resolved_name:
            language_name = resolved_name

    return f"Respond in {language_name}."


def append_default_language_instruction(prompt: str) -> str:
    """Append the default language instruction to a prompt.

    Ensures the instruction appears on a new line even if the prompt already
    ends with other text.
    """

    instruction = get_default_language_instruction()
    if prompt.endswith("\n"):
        return prompt + instruction
    return prompt + "\n" + instruction


def _resolve_language_name(language_code: str, languages: Iterable[tuple[str, str]]) -> str | None:
    """Return a human-readable language name for ``language_code``."""

    for candidate in _language_code_candidates(language_code):
        name = _lookup_language_name(candidate, languages)
        if name:
            return name

    for candidate in _language_code_candidates(language_code):
        try:
            info = get_language_info(candidate)
        except KeyError:
            continue

        name = info.get("name_local") or info.get("name")
        if name:
            return name

    return None


def _lookup_language_name(language_code: str, languages: Iterable[tuple[str, str]]) -> str | None:
    normalized = language_code.lower()
    for configured_code, configured_name in languages:
        if str(configured_code).lower() == normalized:
            return str(configured_name)
    return None


def _language_code_candidates(language_code: str) -> list[str]:
    normalized = language_code.replace("_", "-")
    candidates: list[str] = []

    def _add(code: str) -> None:
        if code and code not in candidates:
            candidates.append(code)

    _add(language_code)
    _add(normalized)
    if "-" in normalized:
        _add(normalized.split("-", 1)[0])

    return candidates
