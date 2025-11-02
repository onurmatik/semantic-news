from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Widget


class WidgetModelTests(TestCase):
    def test_defaults_are_empty_collections(self):
        widget = Widget(name="Example")
        widget.full_clean()
        widget.save()

        self.assertEqual(widget.response_format, {})
        self.assertEqual(widget.tools, [])

    def test_response_format_must_be_mapping(self):
        widget = Widget(name="Bad response", response_format=["not", "a", "dict"])

        with self.assertRaises(ValidationError) as exc:
            widget.full_clean()

        self.assertIn("response_format", exc.exception.error_dict)

    def test_tools_must_be_list_of_non_empty_strings(self):
        widget = Widget(name="Bad tools", tools=["valid", 7, ""])

        with self.assertRaises(ValidationError) as exc:
            widget.full_clean()

        self.assertIn("tools", exc.exception.error_dict)

    def test_valid_widget_passes_clean(self):
        widget = Widget(
            name="Valid widget",
            prompt_template="Render content",
            response_format={"type": "markdown"},
            tools=["web_search"],
            template="{{ body }}",
        )

        # Should not raise
        widget.full_clean()
        widget.save()
