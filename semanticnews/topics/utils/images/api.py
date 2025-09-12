from ninja import Router, Schema
from ninja.errors import HttpError
import base64
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile

from ...models import Topic
from .models import TopicImage
from ....openai import OpenAI

router = Router()


class TopicImageCreateRequest(Schema):
    """Request body for generating an image for a topic."""

    topic_uuid: str


class TopicImageCreateResponse(Schema):
    """Response returned after creating a topic image."""

    image_url: str
    thumbnail_url: str


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

    prompt = (
        "Create an illustration based on the abstract description of the content in the news item.\n"
        "- flat‑illustration style, muted teal/terracotta palette and simple shapes\n"
        "- avoid explicit logos\n"
        "- the image’s job is to cue, not tell the whole story\n"
        "- symbolic, not partisan without extremist branding\n\n"
        f"{topic.build_context()}"
    )

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
        topic_image.save()
    except Exception as e:
        topic_image.status = "error"
        topic_image.error_message = str(e)
        topic_image.save(update_fields=["status", "error_message"])
        raise

    return TopicImageCreateResponse(
        image_url=topic_image.image.url,
        thumbnail_url=topic_image.thumbnail.url if topic_image.thumbnail else "",
    )
