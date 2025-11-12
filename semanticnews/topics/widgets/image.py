from typing import Dict, Any
from typing import Any, Dict

from pydantic import BaseModel, HttpUrl

from .base import Widget, WidgetAction


class ImageSchema(BaseModel):
    prompt: str
    image_url: HttpUrl | None = None


class GenerateImageAction(WidgetAction):
    name = "generate"
    icon = "bi bi-stars"
    tools = ["image_generation"]

    def build_prompt(self, context: Dict[str, Any]) -> str:
        prompt_text = context.get("prompt", "")
        return f"Generate a high-quality image based on the following description:\n\n{prompt_text}"


class VariateImageAction(WidgetAction):
    name = "variate"
    icon = "bi bi-shuffle"
    tools = ["image_generation"]

    def build_prompt(self, context: Dict[str, Any]) -> str:
        image_url = context.get("image_url")
        return f"Create a variation of the existing image: {image_url}"


class ImageWidget(Widget):
    name = "image"
    icon = "bi bi-image"
    schema = ImageSchema
    form_template = "widgets/image_form.html"
    template = "widgets/image.html"
    actions = [GenerateImageAction, VariateImageAction]
