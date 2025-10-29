from django.core.exceptions import ValidationError
from django.test import TestCase

from semanticnews.topics.models import Topic

from .models import TopicWidget, WidgetType


class TopicWidgetModelTests(TestCase):
    def setUp(self):
        self.topic = Topic.objects.create(title="")

    def test_singleton_enforced_per_language(self):
        TopicWidget.objects.create(
            topic=self.topic,
            widget_type=WidgetType.RECAP,
            language_code="en",
        )
        with self.assertRaises(ValidationError):
            TopicWidget.objects.create(
                topic=self.topic,
                widget_type=WidgetType.RECAP,
                language_code="en",
            )

    def test_primary_flag_unique_per_topic_and_type(self):
        TopicWidget.objects.create(
            topic=self.topic,
            widget_type=WidgetType.COVER_IMAGE,
            language_code="en",
            is_primary_language=True,
        )
        with self.assertRaises(ValidationError):
            TopicWidget.objects.create(
                topic=self.topic,
                widget_type=WidgetType.COVER_IMAGE,
                language_code="en",
                is_primary_language=True,
            )
