"""Helpers for computing per-topic module layouts."""

from __future__ import annotations

from typing import Dict, List, Literal, Set

Placement = Literal["primary", "sidebar"]

PLACEMENT_PRIMARY: Placement = "primary"
PLACEMENT_SIDEBAR: Placement = "sidebar"

REORDERABLE_BASE_MODULES = {"text", "data", "data_visualizations"}
PRIMARY_FIXED_BASE_MODULES = {"images", "recaps", "content_toolbar", "relations"}
SIDEBAR_FIXED_BASE_MODULES = {"timeline", "related_topics", "documents", "related_events"}

DISPLAY_ORDER_SCALE = 1000


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
    "content_toolbar": {
        "templates": {
            "detail": {
                "template": "topics/content/toolbar.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/content/toolbar.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["topic"],
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
        "context_keys": ["datas", "latest_data", "data", "topic"],
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
    "text": {
        "templates": {
            "detail": {
                "template": "topics/text/card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/text/card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["topic"],
    },
    "embeds": {
        "templates": {
            "detail": {
                "template": "topics/webcontent/embeds/card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/webcontent/embeds/card.html",
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
        "context_keys": ["related_entities", "topic"],
    },
    "related_topics": {
        "templates": {
            "detail": {
                "template": "topics/related_topics/detail_card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/related_topics/edit_card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["related_topic_links", "topic"],
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
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/timeline/overview_card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["timeline", "topic"],
    },
    "documents": {
        "templates": {
            "detail": {
                "template": "topics/webcontent/documents/card.html",
                "context": {"edit_mode": False},
            },
            "edit": {
                "template": "topics/webcontent/documents/card.html",
                "context": {"edit_mode": True},
            },
        },
        "context_keys": ["documents", "webpages", "topic"],
    },
}


DEFAULT_LAYOUT: List[Dict[str, object]] = [
    {
        "module_key": "images",
        "placement": PLACEMENT_PRIMARY,
        "display_order": 10,
    },
    {
        "module_key": "recaps",
        "placement": PLACEMENT_PRIMARY,
        "display_order": 20,
    },
    {
        "module_key": "content_toolbar",
        "placement": PLACEMENT_PRIMARY,
        "display_order": 30,
    },
    {
        "module_key": "text",
        "placement": PLACEMENT_PRIMARY,
        "display_order": 40,
    },
    {
        "module_key": "data",
        "placement": PLACEMENT_PRIMARY,
        "display_order": 50,
    },
    {
        "module_key": "data_visualizations",
        "placement": PLACEMENT_PRIMARY,
        "display_order": 60,
    },
    {
        "module_key": "embeds",
        "placement": PLACEMENT_PRIMARY,
        "display_order": 70,
    },
    {
        "module_key": "relations",
        "placement": PLACEMENT_PRIMARY,
        "display_order": 80,
    },
    {
        "module_key": "related_topics",
        "placement": PLACEMENT_SIDEBAR,
        "display_order": 10,
    },
    {
        "module_key": "related_events",
        "placement": PLACEMENT_SIDEBAR,
        "display_order": 20,
    },
    {
        "module_key": "timeline",
        "placement": PLACEMENT_SIDEBAR,
        "display_order": 30,
    },
    {
        "module_key": "documents",
        "placement": PLACEMENT_SIDEBAR,
        "display_order": 40,
    },
]


def _build_text_descriptors(
    template_config: Dict[str, object],
    registry_entry: Dict[str, object],
    placement: Placement,
    base_display_order: int,
    texts,
) -> List[Dict[str, object]]:
    descriptors: List[Dict[str, object]] = []
    base_context_overrides = dict(template_config.get("context", {}))
    for index, text_obj in enumerate(texts):
        identifier = str(text_obj.id)
        descriptor = {
            "module_key": f"text:{identifier}",
            "base_module_key": "text",
            "module_identifier": identifier,
            "placement": placement,
            "display_order": base_display_order + index,
            "template_name": template_config.get("template"),
            "context_overrides": dict(base_context_overrides),
            "context_keys": registry_entry.get("context_keys", []),
            "text": text_obj,
        }
        descriptors.append(descriptor)
    return descriptors


def _build_data_descriptors(
    template_config: Dict[str, object],
    registry_entry: Dict[str, object],
    placement: Placement,
    base_display_order: int,
    data_values,
    data_ids_with_insights: Set[str],
    has_unsourced_insight: bool,
) -> List[Dict[str, object]]:
    descriptors: List[Dict[str, object]] = []
    base_context_overrides = dict(template_config.get("context", {}))
    unsourced_assigned = False
    for index, data_obj in enumerate(data_values):
        identifier = str(data_obj.id)
        context_overrides = dict(base_context_overrides)
        should_show_insights = identifier in data_ids_with_insights
        if not should_show_insights and has_unsourced_insight and not unsourced_assigned:
            should_show_insights = True
            unsourced_assigned = True
        context_overrides["show_data_insights"] = should_show_insights
        context_overrides["data"] = data_obj
        descriptor = {
            "module_key": f"data:{identifier}",
            "base_module_key": "data",
            "module_identifier": identifier,
            "placement": placement,
            "display_order": base_display_order + index,
            "template_name": template_config.get("template"),
            "context_overrides": context_overrides,
            "context_keys": registry_entry.get("context_keys", []),
            "data": data_obj,
        }
        descriptors.append(descriptor)
    return descriptors


def _build_visualization_descriptors(
    template_config: Dict[str, object],
    registry_entry: Dict[str, object],
    placement: Placement,
    base_display_order: int,
    visualizations,
) -> List[Dict[str, object]]:
    descriptors: List[Dict[str, object]] = []
    base_context_overrides = dict(template_config.get("context", {}))
    for index, visualization in enumerate(visualizations):
        identifier = str(visualization.id)
        descriptor = {
            "module_key": f"data_visualizations:{identifier}",
            "base_module_key": "data_visualizations",
            "module_identifier": identifier,
            "placement": placement,
            "display_order": base_display_order + index,
            "template_name": template_config.get("template"),
            "context_overrides": dict(base_context_overrides),
            "context_keys": registry_entry.get("context_keys", []),
            "visualization": visualization,
        }
        descriptors.append(descriptor)
    return descriptors


def get_layout_for_mode(topic, mode: Literal["detail", "edit"]) -> Dict[str, List[Dict[str, object]]]:
    """Return ordered module descriptors grouped by placement for ``mode``."""

    placements: Dict[str, List[Dict[str, object]]] = {
        PLACEMENT_PRIMARY: [],
        PLACEMENT_SIDEBAR: [],
    }

    text_values = list(
        topic.texts.filter(is_deleted=False).order_by("display_order", "created_at")
    )
    data_values = list(
        topic.datas.filter(is_deleted=False).order_by("display_order", "created_at")
    )
    visualization_values = list(
        topic.data_visualizations.filter(is_deleted=False).order_by("display_order", "created_at")
    )
    insight_qs = topic.data_insights.filter(is_deleted=False).prefetch_related("sources")

    data_ids_with_insights: Set[str] = set()
    has_unsourced_insight = False
    for insight in insight_qs:
        sources = list(insight.sources.all())
        if not sources:
            has_unsourced_insight = True
        for source in sources:
            source_id = getattr(source, "id", None)
            if source_id is not None:
                data_ids_with_insights.add(str(source_id))

    for entry in DEFAULT_LAYOUT:
        module_key = entry["module_key"]
        placement = entry["placement"]
        base_display_order = entry["display_order"] * DISPLAY_ORDER_SCALE
        registry_entry = MODULE_REGISTRY.get(module_key)
        if not registry_entry:
            continue
        template_config = registry_entry.get("templates", {}).get(mode)
        if not template_config:
            continue

        if module_key == "text":
            descriptors = _build_text_descriptors(
                template_config,
                registry_entry,
                placement,
                base_display_order,
                text_values,
            )
            placements[placement].extend(descriptors)
            continue

        if module_key == "data":
            descriptors = _build_data_descriptors(
                template_config,
                registry_entry,
                placement,
                base_display_order,
                data_values,
                data_ids_with_insights,
                has_unsourced_insight,
            )
            placements[placement].extend(descriptors)
            continue

        if module_key == "data_visualizations":
            descriptors = _build_visualization_descriptors(
                template_config,
                registry_entry,
                placement,
                base_display_order,
                visualization_values,
            )
            placements[placement].extend(descriptors)
            continue

        descriptor = {
            "module_key": module_key,
            "base_module_key": module_key,
            "module_identifier": None,
            "placement": placement,
            "display_order": base_display_order,
            "template_name": template_config.get("template"),
            "context_overrides": dict(template_config.get("context", {})),
            "context_keys": registry_entry.get("context_keys", []),
        }
        placements[placement].append(descriptor)

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
    base_key = module.get("base_module_key", module.get("module_key"))
    if base_key == "text":
        text_obj = module.get("text")
        if not text_obj:
            return False
        return bool((text_obj.content or "").strip())

    if base_key == "data_visualizations":
        visualization = module.get("visualization")
        if not visualization:
            return False
        insight = getattr(visualization, "insight", None)
        if insight and getattr(insight, "insight", "").strip():
            return True
        chart_data = getattr(visualization, "chart_data", None)
        return bool(chart_data)

    if base_key == "data":
        data_obj = module.get("data")
        if not data_obj:
            data_obj = module.get("context_overrides", {}).get("data")
        if not data_obj:
            return False
        table_data = getattr(data_obj, "data", {}) or {}
        if isinstance(table_data, dict):
            headers = table_data.get("headers", [])
            rows = table_data.get("rows", [])
            if headers or rows:
                return True
        return False

    registry_entry = MODULE_REGISTRY.get(base_key, {})
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
