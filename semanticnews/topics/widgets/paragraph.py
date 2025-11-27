from typing import Any, Dict, List

from pydantic import BaseModel

from .base import Widget, WidgetAction


class ParagraphSchema(BaseModel):
    text: str
    instructions: str = ""


class GenerateAction(WidgetAction):
    name = "generate"
    icon = "bi bi-stars"

    def build_prompt(self, context: Dict[str, Any]) -> str:
        topic = context.get("topic_title") or context.get("topic") or ""
        recap = (context.get("latest_recap") or "").strip()
        raw_paragraphs = context.get("paragraphs")
        paragraphs: List[str] = []
        if isinstance(raw_paragraphs, list):
            paragraphs = [str(item).strip() for item in raw_paragraphs if str(item).strip()]
        instructions = (context.get("instructions") or "").strip()

        prompt_parts = [
            "You are drafting a narrative paragraph for this topic.",
            f"Topic title: {topic}" if topic else "",
        ]

        if recap:
            prompt_parts.append("Latest recap of the topic:\n" + recap)
        if paragraphs:
            prompt_parts.append(
                "Existing paragraphs for context:\n" + "\n\n".join(paragraphs)
            )

        prompt_parts.append(
            "Write a new paragraph that fits naturally with the existing content."
            " Avoid markdown formatting or headings."
        )

        if instructions:
            prompt_parts.append("Follow these user instructions only in context of the topic:\n" + instructions)

        return "\n\n".join(filter(None, prompt_parts))


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
    actions = [GenerateAction, SummarizeAction, ExpandAction]
