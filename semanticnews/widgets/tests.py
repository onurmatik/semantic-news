from django.test import TestCase

from .defaults import DEFAULT_WIDGETS
from .models import Widget, WidgetType


class WidgetModelTests(TestCase):
    def test_seeded_widgets_match_defaults(self):
        seeded = {widget.name: widget for widget in Widget.objects.all()}
        expected_names = {definition["name"] for definition in DEFAULT_WIDGETS}

        self.assertTrue(expected_names.issubset(seeded.keys()))

        for definition in DEFAULT_WIDGETS:
            widget = seeded[definition["name"]]
            self.assertEqual(widget.type, definition["type"])
            self.assertEqual(widget.prompt, definition["prompt"])
            self.assertEqual(widget.response_format, definition["response_format"])
            self.assertEqual(widget.tools, definition["tools"])
            self.assertEqual(widget.template, definition["template"])

    def test_widget_type_choices_cover_defaults(self):
        default_types = {definition["type"] for definition in DEFAULT_WIDGETS}
        available_types = set(dict(WidgetType.choices))

        self.assertTrue(default_types.issubset(available_types))
