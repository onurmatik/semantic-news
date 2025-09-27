"""Utility helpers for working with locality configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from django.conf import settings


@dataclass(frozen=True)
class LocalityOption:
    """Simple representation of a configured locality option."""

    code: str
    label: str
    is_default: bool = False


def _settings_localities() -> Sequence[tuple[str, str]]:
    """Return the locality tuples defined in settings."""

    localities: Iterable[tuple[str, str]] = getattr(settings, "LOCALITIES", ())
    return tuple(localities)


def get_default_locality_code() -> str | None:
    """Return the configured default locality code, if any."""

    return getattr(settings, "DEFAULT_LOCALITY", None)


def get_locality_options() -> List[LocalityOption]:
    """Return configured localities sorted with the default first."""

    default_code = get_default_locality_code()
    options = [
        LocalityOption(code=code, label=label, is_default=(code == default_code))
        for code, label in _settings_localities()
    ]

    # Sort with the default first, remaining options alphabetically by label.
    options.sort(key=lambda opt: (not opt.is_default, opt.label.lower()))
    return options


def get_locality_choices() -> List[tuple[str, str]]:
    """Return choices tuple suitable for Django form/model fields."""

    return [(opt.code, opt.label) for opt in get_locality_options()]


def get_default_locality_label() -> str:
    """Return the label of the default locality or a sensible fallback."""

    default_code = get_default_locality_code()
    if default_code:
        label = get_locality_label(default_code)
        if label:
            return label
    return "Global"


def get_locality_label(code: str | None) -> str | None:
    """Resolve a locality code to its configured human-readable label."""

    if code is None:
        return None
    for opt in get_locality_options():
        if opt.code == code:
            return opt.label
    return code


def resolve_locality_code(value: str | None) -> str | None:
    """Return the configured code for a value, accepting code or label."""

    if value is None:
        return None

    for opt in get_locality_options():
        if value == opt.code or value == opt.label:
            return opt.code
    return value


def get_locality_form_choices(
    include_blank: bool = True, *, blank_label: str | None = None
) -> List[tuple[str, str]]:
    """Return locality choices for forms, optionally prefixed with a blank."""

    choices = get_locality_choices()
    if include_blank:
        resolved_label = blank_label or get_default_locality_label()
        return [("", resolved_label)] + choices
    return choices
