import pkgutil
import importlib
import pkgutil
from typing import Dict

from .base import Widget

WIDGET_REGISTRY: Dict[str, Widget] = {}


def load_widgets() -> Dict[str, Widget]:
    """Auto-discover and register all Widget subclasses under this package."""
    global WIDGET_REGISTRY

    for _, modname, _ in pkgutil.iter_modules(__path__):
        if modname in {"api", "services"}:
            continue
        module = importlib.import_module(f"{__name__}.{modname}")
        for obj in module.__dict__.values():
            if isinstance(obj, type) and issubclass(obj, Widget) and obj is not Widget:
                try:
                    # Extract class attributes to pass to dataclass __init__
                    kwargs = {}
                    for field_name in ['name', 'icon', 'form_template', 'template', 'actions', 'context_structure', 'schema']:
                        if hasattr(obj, field_name):
                            kwargs[field_name] = getattr(obj, field_name)
                    instance = obj(**kwargs)
                except TypeError:
                    instance = obj(getattr(obj, "name", obj.__name__))
                WIDGET_REGISTRY[instance.name] = instance

    return WIDGET_REGISTRY


def get_widget(name: str) -> Widget:
    """Retrieve a widget instance by name."""
    if not WIDGET_REGISTRY:
        load_widgets()
    return WIDGET_REGISTRY[name]


# Automatically populate registry on import
load_widgets()
