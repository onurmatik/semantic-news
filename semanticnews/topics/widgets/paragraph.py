from typing import Any, Dict, List

from pydantic import BaseModel

from .base import GenericGenerateAction, Widget, WidgetAction


class ParagraphSchema(BaseModel):
    text: str
    instructions: str = ""


class GenerateAction(GenericGenerateAction):
    def build_generate_prompt(self, context: Dict[str, Any]) -> str:
        topic = context.get("topic_title") or context.get("topic") or ""
        recap = (context.get("latest_recap") or "").strip()
        previous_paragraphs = self._normalise_paragraphs(
            context.get("previous_paragraphs")
        )
        next_paragraphs = self._normalise_paragraphs(context.get("next_paragraphs"))
        if not previous_paragraphs and not next_paragraphs:
            # Backward compatibility for contexts that only expose the full list.
            all_paragraphs = self._normalise_paragraphs(context.get("paragraphs"))
            previous_paragraphs = all_paragraphs
            next_paragraphs = []
        instructions = (context.get("instructions") or "").strip()

        prompt_parts = [
            "You are drafting a narrative paragraph for this topic.",
            f"Topic title: {topic}" if topic else "",
        ]

        if recap:
            prompt_parts.append("Latest recap of the topic:\n" + recap)
        if previous_paragraphs:
            prompt_parts.append(
                "Earlier paragraphs for context:\n" + "\n\n".join(previous_paragraphs)
            )
        if next_paragraphs:
            prompt_parts.append(
                "Upcoming paragraphs to stay consistent with:\n" + "\n\n".join(next_paragraphs)
            )

        prompt_parts.append(
            "Write a new paragraph that fits naturally with the existing content."
            " Avoid markdown formatting or headings."
        )

        if instructions:
            prompt_parts.append("Follow these user instructions only in context of the topic:\n" + instructions)

        return "\n\n".join(filter(None, prompt_parts))

    @staticmethod
    def _normalise_paragraphs(raw_paragraphs: Any) -> List[str]:
        if not isinstance(raw_paragraphs, list):
            return []
        paragraphs: List[str] = []
        for item in raw_paragraphs:
            text = str(item).strip()
            if text:
                paragraphs.append(text)
        return paragraphs


class SummarizeAction(WidgetAction):
    name = "summarize"
    icon = "bi bi-sort-down"

    def build_prompt(self, context: Dict[str, Any]) -> str:
        topic = context.get("topic_title") or context.get("topic") or ""
        text = (context.get("text") or "").strip()
        instructions = (context.get("instructions") or "").strip()

        parts = ["You are refining a paragraph for this topic."]
        if topic:
            parts.append(f"Topic title: {topic}")
        if text:
            parts.append("Paragraph to summarize:\n" + text)
        parts.append(
            "Summarize the paragraph concisely while keeping the original voice and"
            " avoiding markdown formatting."
        )
        if instructions:
            parts.append(
                "Follow these optional user instructions while summarizing:\n" + instructions
            )

        return "\n\n".join(parts)


class ExpandAction(WidgetAction):
    name = "expand"
    icon = "bi bi-sort-up"

    def build_prompt(self, context: Dict[str, Any]) -> str:
        topic = context.get("topic_title") or context.get("topic") or ""
        text = (context.get("text") or "").strip()
        instructions = (context.get("instructions") or "").strip()

        parts = ["You are enriching a paragraph for this topic."]
        if topic:
            parts.append(f"Topic title: {topic}")
        if text:
            parts.append("Paragraph to expand:\n" + text)
        parts.append(
            "Expand the paragraph with relevant details while keeping the original"
            " tone and avoiding markdown formatting or headings."
        )
        if instructions:
            parts.append(
                "Follow these optional user instructions while expanding:\n" + instructions
            )

        return "\n\n".join(parts)


class ParagraphWidget(Widget):
    name = "paragraph"
    icon = "bi bi-justify-left"
    schema = ParagraphSchema
    form_template = "widgets/paragraph_form.html"
    template = "widgets/paragraph.html"
    actions = [GenerateAction, SummarizeAction, ExpandAction]
