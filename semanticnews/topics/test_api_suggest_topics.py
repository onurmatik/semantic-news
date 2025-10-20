from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import TestCase

from semanticnews.prompting import get_default_language_instruction
from semanticnews.topics.models import Topic
from semanticnews.topics.utils.text.models import TopicText


class SuggestTopicsAPITests(TestCase):
    """Tests for the topics suggestion API endpoint."""

    @patch("semanticnews.topics.api.OpenAI")
    def test_suggest_topics_returns_topics(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(topics=["Topic A", "Topic B"])
        mock_client.responses.parse.return_value = mock_response

        response = self.client.get("/api/topics/suggest", {"about": "economy", "limit": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["Topic A", "Topic B"])
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        prompt = kwargs["input"]
        self.assertIn("Description:\neconomy", prompt)
        self.assertIn(get_default_language_instruction(), prompt)

    @patch("semanticnews.topics.api.OpenAI")
    def test_suggest_topics_post(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(topics=["Topic X"])
        mock_client.responses.parse.return_value = mock_response

        payload = {"about": "politics", "limit": 1}
        response = self.client.post(
            "/api/topics/suggest",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["Topic X"])
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        prompt = kwargs["input"]
        self.assertIn("Description:\npolitics", prompt)
        self.assertIn(get_default_language_instruction(), prompt)

    @patch("semanticnews.topics.api.OpenAI")
    def test_suggest_topics_uses_topic_context(self, mock_openai):
        topic = Topic.objects.create(title="Existing Topic")
        TopicText.objects.create(topic=topic, content="Contextual information.")

        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(topics=["Topic Y"])
        mock_client.responses.parse.return_value = mock_response

        response = self.client.get("/api/topics/suggest", {"topic_uuid": str(topic.uuid)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ["Topic Y"])
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        prompt = kwargs["input"]
        self.assertIn("Existing topic context:", prompt)
        self.assertIn("Contextual information.", prompt)
        self.assertIn(get_default_language_instruction(), prompt)

    def test_suggest_topics_requires_description_or_context(self):
        response = self.client.get("/api/topics/suggest")

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Provide a description or add content",
            response.json().get("detail", ""),
        )

    def test_suggest_topics_returns_404_for_missing_topic(self):
        response = self.client.get(
            "/api/topics/suggest",
            {"topic_uuid": str(uuid4())},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json().get("detail"), "Topic not found")
