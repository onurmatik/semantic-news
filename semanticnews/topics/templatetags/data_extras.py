from __future__ import annotations

from typing import Iterable, List, Sequence, Any

from django import template

register = template.Library()


def _extract_identifier(value: Any) -> str | None:
    """Return a string identifier for ``value`` if available."""

    if value is None:
        return None

    # Support both attribute and mapping based access.
    for attr in ("id", "data_id", "original_id"):
        attr_value = getattr(value, attr, None)
        if attr_value is not None:
            return str(attr_value)
    if isinstance(value, dict):
        for key in ("id", "data_id", "original_id"):
            if key in value and value[key] is not None:
                return str(value[key])
    return None


def _source_identifiers(insight: Any) -> List[str]:
    """Return the data identifiers associated with ``insight``."""

    if insight is None:
        return []

    source_ids = getattr(insight, "source_ids", None)
    if isinstance(source_ids, (list, tuple, set)):
        return [str(source_id) for source_id in source_ids if source_id is not None]

    sources = getattr(insight, "sources", None)
    if sources is None:
        return []

    if hasattr(sources, "all"):
        iterable: Iterable[Any] = sources.all()
    else:
        iterable = sources

    identifiers: List[str] = []
    for source in iterable or []:
        source_id = getattr(source, "id", None)
        if source_id is not None:
            identifiers.append(str(source_id))
    return identifiers


@register.filter
def insights_for_data(dataset: Any, insights: Sequence[Any] | None) -> List[Any]:
    """Return the subset of ``insights`` linked to ``dataset``."""

    if not dataset or not insights:
        return []

    data_identifier = _extract_identifier(dataset)
    if data_identifier is None:
        return []

    matched: List[Any] = []
    for insight in insights:
        if data_identifier in _source_identifiers(insight):
            matched.append(insight)
    return matched
