from typing import List

from ninja import Router, Schema
from ninja.errors import HttpError

from ...models import Topic
from .models import TopicYoutubeVideo

router = Router()

