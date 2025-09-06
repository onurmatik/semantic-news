from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


class SuggestTopicsAPITests(SimpleTestCase):
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
