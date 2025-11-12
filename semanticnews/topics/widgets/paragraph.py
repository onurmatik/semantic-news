from typing import Any, Dict

from pydantic import BaseModel
from typing import Any, Dict

from pydantic import BaseModel

from .base import Widget, WidgetAction


class ParagraphSchema(BaseModel):
    text: str


class SummarizeAction(WidgetAction):
    name = "summarize"
    icon = "bi bi-arrow-down-short"

    def build_prompt(self, context: Dict[str, Any]) -> str:
        topic = context.get("topic")
        text = context.get("text", "")
        return f"Summarize the following text in the context of '{topic}':\n\n{text}"


class ExpandAction(WidgetAction):
    name = "expand"
    icon = "bi bi-arrow-up-short"

    def build_prompt(self, context: Dict[str, Any]) -> str:
        topic = context.get("topic")
        text = context.get("text", "")
        return f"Expand the following text with more detail about '{topic}':\n\n{text}"


class ParagraphWidget(Widget):
    name = "paragraph"
    icon = "bi bi-justify-left"
    schema = ParagraphSchema
    form_template = "widgets/paragraph_form.html"
    template = "widgets/paragraph.html"
    actions = [SummarizeAction, ExpandAction]
