from django.core.exceptions import ValidationError
from django.test import TestCase

from semanticnews.topics.models import Topic

from .models import TopicWidget, WidgetType


class TopicWidgetModelTests(TestCase):
    def setUp(self):
        self.topic = Topic.objects.create(title="")

    def test_multiple_widgets_allowed_per_language(self):
        first = TopicWidget.objects.create(
            topic=self.topic,
            widget_type=WidgetType.TEXT,
            language_code="en",
        )
        second = TopicWidget.objects.create(
            topic=self.topic,
            widget_type=WidgetType.TEXT,
            language_code="en",
        )

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(
            TopicWidget.objects.filter(
                topic=self.topic, widget_type=WidgetType.TEXT, language_code="en"
            ).count(),
            2,
        )

    def test_primary_flag_unique_per_topic_and_type(self):
        TopicWidget.objects.create(
            topic=self.topic,
            widget_type=WidgetType.IMAGES,
            language_code="en",
            is_primary_language=True,
        )
        with self.assertRaises(ValidationError):
            TopicWidget.objects.create(
                topic=self.topic,
                widget_type=WidgetType.IMAGES,
                language_code="en",
                is_primary_language=True,
            )
