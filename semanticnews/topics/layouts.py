"""Helpers for computing per-topic module layouts."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Iterable, List, Literal, Sequence

from .models import TopicModuleLayout

LayoutMode = Literal["detail", "edit"]


def _topic_has_hero_image(context):
    """Return whether the topic currently has a hero image."""

    topic = context.get("topic")
    if not topic:
        return False

    image = getattr(topic, "image", None)
    return bool(image)


MODULE_REGISTRY: Dict[str, Dict[str, object]] = {
    "images": {
        "templates": {
            "detail": {
                "template": "topics/images/hero.html",
                "context": {},
            },
            "edit": {
                "template": "topics/images/card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["topic"],
        "has_content": _topic_has_hero_image,
    },
    "recaps": {
        "templates": {
            "detail": {
                "template": "topics/recaps/card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/recaps/card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["latest_recap", "topic"],
    },
    "data": {
        "templates": {
            "detail": {
                "template": "topics/data/card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/data/card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["datas", "latest_data", "topic"],
    },
    "data_visualizations": {
        "templates": {
            "detail": {
                "template": "topics/data/visualization_card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/data/visualization_card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["data_visualizations", "topic"],
    },
    "narratives": {
        "templates": {
            "detail": {
                "template": "topics/narratives/card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/narratives/card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["current_narrative", "latest_narrative", "topic"],
    },
    "embeds": {
        "templates": {
            "detail": {
                "template": "topics/embeds/card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/embeds/card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["youtube_video", "tweets", "topic"],
    },
    "relations": {
        "templates": {
            "detail": {
                "template": "topics/relations/card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/relations/card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["latest_relation", "relations_json", "topic"],
    },
    "related_events": {
        "templates": {
            "detail": {
                "template": "topics/timeline/related_events_card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/timeline/related_events_card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["related_events", "topic"],
    },
    "timeline": {
        "templates": {
            "detail": {
                "template": "topics/timeline/overview_card.html",
                "context": {},
            },
            "edit": {
                "template": "topics/timeline/overview_card.html",
                "context": {},
            },
        },
        "context_keys": ["timeline", "topic"],
    },
    "documents": {
        "templates": {
            "detail": {
                "template": "topics/documents/card.html",
                "context": {},
            },
            "edit": {
                "template": "topics/documents/card.html",
                "context": {},
            },
        },
        "context_keys": ["documents", "webpages", "topic"],
    },
}


DEFAULT_LAYOUT: List[Dict[str, object]] = [
    {
        "module_key": "images",
        "placement": TopicModuleLayout.PLACEMENT_PRIMARY,
        "size_variant": TopicModuleLayout.SIZE_EXPANDED,
        "display_order": 1,
    },
    {
        "module_key": "recaps",
        "placement": TopicModuleLayout.PLACEMENT_PRIMARY,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 2,
    },
    {
        "module_key": "data",
        "placement": TopicModuleLayout.PLACEMENT_PRIMARY,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 3,
    },
    {
        "module_key": "data_visualizations",
        "placement": TopicModuleLayout.PLACEMENT_PRIMARY,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 4,
    },
    {
        "module_key": "narratives",
        "placement": TopicModuleLayout.PLACEMENT_PRIMARY,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 5,
    },
    {
        "module_key": "embeds",
        "placement": TopicModuleLayout.PLACEMENT_PRIMARY,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 6,
    },
    {
        "module_key": "relations",
        "placement": TopicModuleLayout.PLACEMENT_PRIMARY,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 7,
    },
    {
        "module_key": "related_events",
        "placement": TopicModuleLayout.PLACEMENT_SIDEBAR,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 8,
    },
    {
        "module_key": "timeline",
        "placement": TopicModuleLayout.PLACEMENT_SIDEBAR,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 9,
    },
    {
        "module_key": "documents",
        "placement": TopicModuleLayout.PLACEMENT_SIDEBAR,
        "size_variant": TopicModuleLayout.SIZE_DEFAULT,
        "display_order": 10,
    },
]


def _normalize_layout(records: Iterable[TopicModuleLayout]) -> List[Dict[str, object]]:
    """Convert ``TopicModuleLayout`` rows into plain dictionaries."""

    layout: List[Dict[str, object]] = []
    for record in records:
        layout.append(
            {
                "module_key": record.module_key,
                "placement": record.placement,
                "size_variant": record.size_variant,
                "display_order": record.display_order,
            }
        )
    if not layout:
        layout = deepcopy(DEFAULT_LAYOUT)
    else:
        existing_keys = {entry["module_key"] for entry in layout}
        for default_entry in DEFAULT_LAYOUT:
            if default_entry["module_key"] not in existing_keys:
                layout.append(deepcopy(default_entry))
    return layout


def get_topic_layout(topic) -> List[Dict[str, object]]:
    """Return the stored layout configuration for ``topic`` or defaults."""

    return _normalize_layout(topic.module_layouts.all())


def get_layout_for_mode(topic, mode: LayoutMode) -> Dict[str, List[Dict[str, object]]]:
    """Return ordered module descriptors grouped by placement for ``mode``."""

    base_layout = get_topic_layout(topic)
    placements: Dict[str, List[Dict[str, object]]] = {
        TopicModuleLayout.PLACEMENT_PRIMARY: [],
        TopicModuleLayout.PLACEMENT_SIDEBAR: [],
    }

    for entry in base_layout:
        module_key = entry["module_key"]
        registry_entry = MODULE_REGISTRY.get(module_key)
        if not registry_entry:
            continue
        templates = registry_entry.get("templates", {})
        template_config = templates.get(mode)
        if not template_config:
            continue

        descriptor = {
            "module_key": module_key,
            "placement": entry["placement"],
            "size_variant": entry["size_variant"],
            "display_order": entry["display_order"],
            "template_name": template_config.get("template"),
            "context_overrides": template_config.get("context", {}),
            "context_keys": registry_entry.get("context_keys", []),
        }

        placements.setdefault(entry["placement"], []).append(descriptor)

    for modules in placements.values():
        modules.sort(key=lambda module: module["display_order"])

    return placements


def _value_has_content(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return bool(value)
    except TypeError:  # pragma: no cover - defensive
        return True


def _module_has_content(module: Dict[str, object], context: Dict[str, object]) -> bool:
    registry_entry = MODULE_REGISTRY.get(module.get("module_key"), {})
    content_check = registry_entry.get("has_content")
    if callable(content_check):
        return bool(content_check(context))

    for key in registry_entry.get("context_keys", []):
        if key == "topic":
            continue
        if key in context and _value_has_content(context[key]):
            return True
    return False


def annotate_module_content(modules: List[Dict[str, object]], context: Dict[str, object]) -> None:
    """Annotate ``modules`` with a ``has_content`` flag based on ``context``."""

    for module in modules:
        module["has_content"] = _module_has_content(module, context)


def serialize_layout(layout: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    """Return a JSON-serialisable copy of ``layout`` entries."""

    return [
        {
            "module_key": entry["module_key"],
            "placement": entry["placement"],
            "size_variant": entry["size_variant"],
            "display_order": entry["display_order"],
        }
        for entry in layout
    ]


ALLOWED_PLACEMENTS = {
    TopicModuleLayout.PLACEMENT_PRIMARY,
    TopicModuleLayout.PLACEMENT_SIDEBAR,
}

ALLOWED_SIZE_VARIANTS = {
    TopicModuleLayout.SIZE_DEFAULT,
    TopicModuleLayout.SIZE_COMPACT,
    TopicModuleLayout.SIZE_EXPANDED,
}
