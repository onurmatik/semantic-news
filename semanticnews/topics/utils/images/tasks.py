import base64
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from semanticnews.openai import OpenAI

from .models import TopicImage


def create_image(self):
    recap = self.recaps.last()
    if not recap:
        return

    prompt = (f"Create an illustration based on the abstract description of the content in the news item.\n"
              f"- flat‑illustration style, muted teal/terracotta palette and simple shapes\n"
              f"- avoid explicit logos\n"
              f"- the image’s job is to cue, not tell the whole story\n"
              f"- symbolic, not partisan without extremist branding\n\n"
              f"# {self.name}\n{recap.recap}")
    client = OpenAI()
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1536x1024",
        output_format="webp",
        # quality="low",
    )

    # decode the main image delivered as base64
    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    base_name = f"{self.slug or self.id}"
    main_file = ContentFile(image_bytes, name=f"{base_name}.webp")

    # Create thumbnail
    thumb_size = (450, 300)
    thumb_img = Image.open(BytesIO(image_bytes))
    thumb_img = thumb_img.convert("RGB")
    thumb_img.thumbnail(thumb_size, Image.LANCZOS)
    thumb_io = BytesIO()
    thumb_img.save(thumb_io, format="WEBP", quality=85)

    thumb_name = f"{base_name}_thumb_{thumb_size[0]}x{thumb_size[1]}.webp"
    thumb_file = ContentFile(thumb_io.getvalue(), name=thumb_name)

    # S3 safe file saving flow:
    # create the DB row without touching storage
    topic_image = TopicImage(topic=self)
    # push the binaries through the storage backend
    topic_image.image.save(main_file.name, main_file, save=False)
    topic_image.thumbnail.save(thumb_file.name, thumb_file, save=False)
    # persist the row
    topic_image.save()
