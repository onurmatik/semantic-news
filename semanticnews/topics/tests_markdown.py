from django.template import Context, Template
from django.test import SimpleTestCase


class MarkdownifyFilterTests(SimpleTestCase):
    """Ensure the markdownify filter renders Markdown safely."""

    def render(self, text: str) -> str:
        template = Template("{% load markdown_extras %}{{ text|markdownify }}")
        return template.render(Context({"text": text}))

    def test_allows_basic_formatting(self):
        html = self.render("**bold** and [link](https://example.com)")

        self.assertIn("<strong>bold</strong>", html)
        self.assertIn('href="https://example.com"', html)

    def test_rejects_javascript_links(self):
        html = self.render("[click me](javascript:alert(1))")

        self.assertIn("<a", html)
        self.assertNotIn("javascript:alert(1)", html)
