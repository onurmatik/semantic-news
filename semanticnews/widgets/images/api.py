from datetime import datetime
from typing import Optional, List, Literal

from django.utils.timezone import make_naive
from ninja import Router, Schema
from ninja.errors import HttpError
import base64
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile

from semanticnews.topics.models import Topic
from .models import TopicImage
from semanticnews.openai import OpenAI
from semanticnews.prompting import append_default_language_instruction

router = Router()

StatusLiteral = Literal["finished", "error"]


class TopicImageCreateRequest(Schema):
    """Request body for generating an image for a topic."""

    topic_uuid: str
    style: Optional[str] = None     # "default" | "photo" | "illustration"


class TopicImageCreateResponse(Schema):
    """Response returned after creating a topic image."""

    image_url: str
    thumbnail_url: str
    status: StatusLiteral
    error_message: Optional[str] = None
    error_code: Optional[str] = None


@router.post("/create", response=TopicImageCreateResponse)
def create_image(request, payload: TopicImageCreateRequest):
    """Generate and store an image for a topic using OpenAI."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=payload.topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    chosen_style = (payload.style or "default").lower()
    style_hint = ""
    if chosen_style == "photo":
        style_hint = "- photorealistic editorial photo, natural lighting\n"
    elif chosen_style == "illustration":
        style_hint = "- clean vector illustration\n"

    context = topic.build_context()
    prompt = (
        "Create an illustration based on the abstract description of the content in the news item.\n"
        "- flat-illustration style, muted teal/terracotta palette and simple shapes\n"
        "- avoid explicit logos\n"
        "- the image’s job is to cue, not tell the whole story\n"
        "- symbolic, not partisan without extremist branding\n"
        f"{style_hint}\n"
    )
    prompt = append_default_language_instruction(prompt)
    prompt += f"\n\n{context}"

    topic_image = TopicImage.objects.create(topic=topic)
    try:
        with OpenAI() as client:
            result = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="1536x1024",
                output_format="webp",
            )

        image_base64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)

        base_name = f"{topic.slug or topic.id}"
        main_file = ContentFile(image_bytes, name=f"{base_name}.webp")

        thumb_size = (450, 300)
        thumb_img = Image.open(BytesIO(image_bytes))
        thumb_img = thumb_img.convert("RGB")
        thumb_img.thumbnail(thumb_size, Image.LANCZOS)
        thumb_io = BytesIO()
        thumb_img.save(thumb_io, format="WEBP", quality=85)

        thumb_name = f"{base_name}_thumb_{thumb_size[0]}x{thumb_size[1]}.webp"
        thumb_file = ContentFile(thumb_io.getvalue(), name=thumb_name)

        topic_image.image.save(main_file.name, main_file, save=False)
        topic_image.thumbnail.save(thumb_file.name, thumb_file, save=False)
        topic_image.status = "finished"
        topic_image.error_message = None
        topic_image.error_code = None
        topic_image.save()

        (
            TopicImage.objects
            .filter(topic=topic, is_deleted=False, is_hero=True)
            .exclude(pk=topic_image.pk)
            .update(is_hero=False)
        )
        topic_image.is_hero = True
        topic_image.save(update_fields=["is_hero"])

        return TopicImageCreateResponse(
            image_url=topic_image.image.url,
            thumbnail_url=topic_image.thumbnail.url if topic_image.thumbnail else "",
            status="finished",
        )
    except Exception as e:
        topic_image.status = "error"
        topic_image.error_message = str(e)
        topic_image.error_code = getattr(e, "code", None) or "openai_error"
        topic_image.save(update_fields=["status", "error_message", "error_code"])

        return TopicImageCreateResponse(
            image_url="",
            thumbnail_url="",
            status="error",
            error_message=topic_image.error_message,
            error_code=topic_image.error_code,
        )


class TopicImageItem(Schema):
    id: int
    image_url: str
    thumbnail_url: str
    created_at: datetime
    is_hero: bool


class TopicImageListResponse(Schema):
    total: int
    items: List[TopicImageItem]


@router.get("/{topic_uuid}/list", response=TopicImageListResponse)
def list_images(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    images = (
        TopicImage.objects
        .filter(topic=topic, status="finished", is_deleted=False)
        .order_by("created_at")
    )

    items = [
        TopicImageItem(
            id=img.id,
            image_url=img.image.url,
            thumbnail_url=img.thumbnail.url if img.thumbnail else "",
            created_at=make_naive(img.created_at),
            is_hero=img.is_hero,
        )
        for img in images
    ]
    return TopicImageListResponse(total=len(items), items=items)


class TopicImageClearResponse(Schema):
    status: StatusLiteral
    error_message: Optional[str] = None


@router.post("/{topic_uuid}/clear", response=TopicImageClearResponse)
def clear_image(request, topic_uuid: str):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise HttpError(404, "Topic not found")

    if topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    heroes = list(
        TopicImage.objects
        .filter(topic=topic, is_deleted=False, is_hero=True)
        .order_by("-created_at")
    )

    if not heroes:
        return TopicImageClearResponse(status="finished")

    for hero in heroes:
        hero.is_hero = False
        hero.save(update_fields=["is_hero"])

    return TopicImageClearResponse(status="finished")


@router.delete("/{image_id}", response={204: None})
def delete_image(request, image_id: int):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        obj = TopicImage.objects.select_related("topic").get(id=image_id)
    except TopicImage.DoesNotExist:
        raise HttpError(404, "Image not found")

    if obj.topic.created_by_id != user.id:
        raise HttpError(403, "Forbidden")

    if obj.is_deleted:
        return 204, None

    obj.is_deleted = True
    obj.save(update_fields=["is_deleted"])
    return 204, None
