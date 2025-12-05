from typing import Any, Dict, List

from pydantic import BaseModel

from .base import GenericGenerateAction, Widget, WidgetAction


class ParagraphSchema(BaseModel):
    text: str
    instructions: str = ""


def _normalise_paragraphs(raw_paragraphs: Any) -> List[str]:
    if not isinstance(raw_paragraphs, list):
        return []
    paragraphs: List[str] = []
    for item in raw_paragraphs:
        text = str(item).strip()
        if text:
            paragraphs.append(text)
    return paragraphs



def _build_paragraph_context(context: Dict[str, Any]) -> Dict[str, Any]:
    topic = context.get("topic_title") or context.get("topic") or ""
    recap = (context.get("latest_recap") or "").strip()
    text = (context.get("text") or "").strip()
    previous_paragraphs = _normalise_paragraphs(context.get("previous_paragraphs"))
    next_paragraphs = _normalise_paragraphs(context.get("next_paragraphs"))
    if not previous_paragraphs and not next_paragraphs:
        # Backward compatibility for contexts that only expose the full list.
        all_paragraphs = _normalise_paragraphs(context.get("paragraphs"))
        previous_paragraphs = all_paragraphs
        next_paragraphs = []
    instructions = (context.get("instructions") or "").strip()

    return {
        "topic": topic,
        "recap": recap,
        "text": text,
        "previous_paragraphs": previous_paragraphs,
        "next_paragraphs": next_paragraphs,
        "instructions": instructions,
    }


class GenerateAction(GenericGenerateAction):
    def build_generate_prompt(self, context: Dict[str, Any]) -> str:
        paragraph_context = _build_paragraph_context(context)
        topic = paragraph_context["topic"]
        recap = paragraph_context["recap"]
        draft_text = paragraph_context["text"]
        previous_paragraphs = paragraph_context["previous_paragraphs"]
        next_paragraphs = paragraph_context["next_paragraphs"]
        instructions = paragraph_context["instructions"]

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

        if draft_text:
            prompt_parts.append("Draft paragraph to refine:\n" + draft_text)

        if instructions:
            prompt_parts.append(
                "MANDATORY user guidance (apply before writing):\n" + instructions
            )

        prompt_parts.append(
            "Style requirements:\n- Maintain continuity with the topic and surrounding paragraphs."
            "\n- Avoid markdown formatting or headings."
        )

        if draft_text:
            prompt_parts.append(
                "Revise and improve the draft paragraph so it fits naturally with the"
                " existing content."
                "\n Do not include earlier and upcoming paragraphs to the response."
            )
        else:
            prompt_parts.append(
                "Write a new paragraph that fits naturally with the existing content."
                "\n Do not include earlier and upcoming paragraphs to the response."
            )

        return "\n\n".join(filter(None, prompt_parts))


class SummarizeAction(WidgetAction):
    name = "summarize"
    icon = "bi bi-sort-down"

    def build_prompt(self, context: Dict[str, Any]) -> str:
        paragraph_context = _build_paragraph_context(context)
        topic = paragraph_context["topic"]
        recap = paragraph_context["recap"]
        text = paragraph_context["text"]
        previous_paragraphs = paragraph_context["previous_paragraphs"]
        next_paragraphs = paragraph_context["next_paragraphs"]
        instructions = paragraph_context["instructions"]

        parts = [
            "You are refining a paragraph for this topic.",
            f"Topic title: {topic}" if topic else "",
        ]

        if recap:
            parts.append("Latest recap of the topic:\n" + recap)
        if previous_paragraphs:
            parts.append(
                "Earlier paragraphs for context:\n" + "\n\n".join(previous_paragraphs)
            )
        if next_paragraphs:
            parts.append(
                "Upcoming paragraphs to stay consistent with:\n" + "\n\n".join(next_paragraphs)
            )
        if text:
            parts.append("Paragraph to summarize:\n" + text)

        if instructions:
            parts.append(
                "MANDATORY user guidance (apply before writing):\n" + instructions
            )

        parts.append(
            "Style requirements:\n- Maintain continuity with the topic and surrounding paragraphs."
            "\n- Avoid markdown formatting or headings."
        )

        if text:
            parts.append(
                "Summarize the paragraph concisely while keeping the original voice."
                "\n Do not include earlier and upcoming paragraphs to the response."
            )
        else:
            parts.append(
                "Prepare a shorter paragraph that fits naturally with the existing"
                " content."
                "\n Do not include earlier and upcoming paragraphs to the response."
            )

        return "\n\n".join(filter(None, parts))


class ExpandAction(WidgetAction):
    name = "expand"
    icon = "bi bi-sort-up"

    def build_prompt(self, context: Dict[str, Any]) -> str:
        paragraph_context = _build_paragraph_context(context)
        topic = paragraph_context["topic"]
        recap = paragraph_context["recap"]
        text = paragraph_context["text"]
        previous_paragraphs = paragraph_context["previous_paragraphs"]
        next_paragraphs = paragraph_context["next_paragraphs"]
        instructions = paragraph_context["instructions"]

        parts = [
            "You are enriching a paragraph for this topic.",
            f"Topic title: {topic}" if topic else "",
        ]

        if recap:
            parts.append("Latest recap of the topic:\n" + recap)
        if previous_paragraphs:
            parts.append(
                "Earlier paragraphs for context:\n" + "\n\n".join(previous_paragraphs)
            )
        if next_paragraphs:
            parts.append(
                "Upcoming paragraphs to stay consistent with:\n" + "\n\n".join(next_paragraphs)
            )
        if text:
            parts.append("Paragraph to expand:\n" + text)

        if instructions:
            parts.append(
                "MANDATORY user guidance (apply before writing):\n" + instructions
            )

        parts.append(
            "Style requirements:\n- Maintain continuity with the topic and surrounding paragraphs."
            "\n- Avoid markdown formatting or headings."
        )

        if text:
            parts.append(
                "Expand the paragraph with relevant details while keeping the original"
                " tone."
                "\n Do not include earlier and upcoming paragraphs to the response."
            )
        else:
            parts.append(
                "Prepare a longer paragraph that fits naturally with the existing"
                " content."
                "\n Do not include earlier and upcoming paragraphs to the response."
            )

        return "\n\n".join(filter(None, parts))


class ParagraphWidget(Widget):
    name = "paragraph"
    icon = "bi bi-justify-left"
    schema = ParagraphSchema
    form_template = "widgets/paragraph_form.html"
    template = "widgets/paragraph.html"
    actions = [GenerateAction, SummarizeAction, ExpandAction]
