from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, Optional, Protocol, List, Any


# ---- Contract for normalized content ----
@dataclass
class NormalizedContent:
    url: Optional[str]                 # may be None for uploads/snippets
    title: Optional[str]
    markdown: Optional[str]
    summary: Optional[str]
    published_at: Optional[datetime]
    language_code: Optional[str]
    content_type: str                  # e.g. "rss.article", "youtube.video", "websearch.snippet"
    site_domain: Optional[str] = None  # map to Site if present
    metadata: Optional[dict] = None    # connector-specific extras


# ---- Simple connector interface ----
class Connector(Protocol):
    name: str
    def ingest(self, **kwargs) -> Iterable[NormalizedContent]: ...


# ---- Global registry ----
_CONNECTORS: Dict[str, Connector] = {}

def register_connector(name: str):
    """Decorator to register a connector by name, e.g. 'rss'."""
    def _wrap(cls):
        inst = cls()
        inst.name = name
        _CONNECTORS[name] = inst
        return cls
    return _wrap

def get_connector(name: str) -> Connector:
    try:
        return _CONNECTORS[name]
    except KeyError:
        raise ValueError(f"Connector '{name}' is not registered. Registered: {list(_CONNECTORS.keys())}")

def list_connectors() -> List[str]:
    return sorted(_CONNECTORS.keys())
