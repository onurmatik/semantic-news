from dataclasses import dataclass, field
from typing import Type, Optional, Any, Dict, List


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
        return [action_cls() for action_cls in self.actions]
