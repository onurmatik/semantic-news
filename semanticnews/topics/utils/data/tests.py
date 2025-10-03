from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import MagicMock, patch

from semanticnews.prompting import get_default_language_instruction
from semanticnews.topics.models import Topic


class TopicDataSearchAPITests(TestCase):
    """Tests for the data search API endpoint."""

    @patch("semanticnews.topics.utils.data.tasks.OpenAI")
    def test_search_data_returns_table_and_sources(self, mock_openai):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)
        topic = Topic.objects.create(title="My Topic", created_by=user)

        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(
            headers=["Year", "USD/TL"],
            rows=[["2023", "1.1"]],
            name="USD/TL Rates",
            sources=["https://example.com/data"],
            explanation=None,
        )
        mock_client.responses.parse.return_value = mock_response

        payload = {
            "topic_uuid": str(topic.uuid),
            "description": "year over year USD/TL for the last 10 years",
        }
        response = self.client.post(
            "/api/topics/data/search",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "headers": ["Year", "USD/TL"],
                "rows": [["2023", "1.1"]],
                "name": "USD/TL Rates",
                "sources": ["https://example.com/data"],
                "source": "https://example.com/data",
            },
        )
        self.assertNotIn("explanation", response.json())
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn(get_default_language_instruction(), kwargs["input"])

    @patch("semanticnews.topics.utils.data.tasks.OpenAI")
    def test_search_data_returns_explanation_when_needed(self, mock_openai):
        User = get_user_model()
        user = User.objects.create_user("user2", "user2@example.com", "password")
        self.client.force_login(user)
        topic = Topic.objects.create(title="Another", created_by=user)

        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(
            headers=["Year", "USD/TL"],
            rows=[["2019", "5.7"]],
            name=None,
            sources=["https://example.com/partial", "https://example.com/archive"],
            explanation="Only five years of data were found",
        )
        mock_client.responses.parse.return_value = mock_response

        payload = {
            "topic_uuid": str(topic.uuid),
            "description": "USD/TL for last 10 years",
        }
        response = self.client.post(
            "/api/topics/data/search",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "headers": ["Year", "USD/TL"],
                "rows": [["2019", "5.7"]],
                "sources": [
                    "https://example.com/partial",
                    "https://example.com/archive",
                ],
                "source": "https://example.com/partial",
                "explanation": "Only five years of data were found",
            },
        )
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn(get_default_language_instruction(), kwargs["input"])

    def test_search_requires_authentication(self):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        topic = Topic.objects.create(title="Topic", created_by=user)

        payload = {
            "topic_uuid": str(topic.uuid),
            "description": "year over year USD/TL",
        }
        response = self.client.post(
            "/api/topics/data/search",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
