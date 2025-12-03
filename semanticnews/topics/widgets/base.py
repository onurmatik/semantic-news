from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type


@dataclass
class WidgetAction:
    """Base class for widget actions (AI prompts, transformations, etc.)."""
    name: str
    icon: str = ""
    prompt: str = ""
    tools: List[str] = field(default_factory=list)
    schema: Optional[Type] = None

    def build_prompt(self, context: Dict[str, Any]) -> str:
        """
        Override this method to dynamically construct the prompt
        from the provided context (e.g., topic, section, user input).
        """
        return self.prompt.format(**context)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stub for executing the action (LLM call, API, etc.).
        Can be implemented in subclasses or external logic.
        """
        prompt = self.build_prompt(context)
        return {"prompt": prompt, "result": f"Simulated result for '{self.name}'"}


class GenericGenerateAction(WidgetAction):
    """Shared plumbing for "generate" style widget actions."""

    name = "generate"
    icon = "bi bi-stars"
    tools: List[str] = []
    schema: Optional[Type] = None

    def build_prompt(self, context: Dict[str, Any]) -> str:
        return self.build_generate_prompt(context)

    def build_generate_prompt(self, context: Dict[str, Any]) -> str:
        raise NotImplementedError("Subclasses must implement prompt construction")

    def get_schema(self) -> Optional[Type]:
        """Optional hook for subclasses to provide a schema for this action."""

        return self.schema


@dataclass
class Widget:
    """Base class for reusable widgets."""
    name: str
    icon: str = ""
    form_template: str = ""
    template: str = ""
    actions: List[Type[WidgetAction]] = field(default_factory=list)
    context_structure: Dict[str, Any] = field(default_factory=dict)
    schema: Optional[Type] = None

    def get_actions(self) -> List[WidgetAction]:
        """Return initialized action instances."""
        actions = []
        for action_cls in self.actions:
            # Extract class attributes to pass to dataclass __init__
            kwargs = {}
            for field_name in ['name', 'icon', 'prompt', 'tools', 'schema']:
                if hasattr(action_cls, field_name):
                    kwargs[field_name] = getattr(action_cls, field_name)
            actions.append(action_cls(**kwargs))
        return actions
