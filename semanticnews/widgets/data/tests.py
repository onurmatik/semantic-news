import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import MagicMock, patch

from semanticnews.prompting import get_default_language_instruction
from semanticnews.topics.models import Topic
from .models import TopicData, TopicDataInsight, TopicDataVisualization


class TopicDataSearchAPITests(TestCase):
    """Tests for the data search API endpoint."""

    @patch("semanticnews.widgets.data.tasks.OpenAI")
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

    @patch("semanticnews.widgets.data.tasks.OpenAI")
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

    @patch("semanticnews.widgets.data.tasks.OpenAI")
    def test_search_data_allows_empty_results(self, mock_openai):
        User = get_user_model()
        user = User.objects.create_user("user3", "user3@example.com", "password")
        self.client.force_login(user)
        topic = Topic.objects.create(title="Empty", created_by=user)

        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(
            headers=[],
            rows=[],
            name=None,
            sources=[],
            explanation="No relevant data was found",
        )
        mock_client.responses.parse.return_value = mock_response

        payload = {
            "topic_uuid": str(topic.uuid),
            "description": "Dataset that does not exist",
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
                "headers": [],
                "rows": [],
                "sources": [],
                "explanation": "No relevant data was found",
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


class TopicDataVisualizationDeleteTests(TestCase):
    """Tests for deleting topic data visualizations."""

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("owner", "owner@example.com", "password")
        self.other = User.objects.create_user("viewer", "viewer@example.com", "password")
        self.topic = Topic.objects.create(title="My Topic", created_by=self.owner)
        self.insight = TopicDataInsight.objects.create(topic=self.topic, insight="Insight text")
        self.visualization = TopicDataVisualization.objects.create(
            topic=self.topic,
            insight=self.insight,
            chart_type="bar",
            chart_data={"labels": ["A"], "datasets": [{"label": "Values", "data": [1]}]},
            display_order=1,
        )

    def test_owner_can_delete_visualization(self):
        self.client.force_login(self.owner)

        response = self.client.delete(f"/api/topics/data/visualization/{self.visualization.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})
        self.visualization.refresh_from_db()
        self.assertTrue(self.visualization.is_deleted)

    def test_other_user_cannot_delete_visualization(self):
        self.client.force_login(self.other)

        response = self.client.delete(f"/api/topics/data/visualization/{self.visualization.id}")

        self.assertEqual(response.status_code, 403)
        self.visualization.refresh_from_db()
        self.assertFalse(self.visualization.is_deleted)


class TopicDataReorderAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("editor", "editor@example.com", "password")
        self.topic = Topic.objects.create(title="Topic", created_by=self.user)
        self.client.force_login(self.user)

    def _post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def test_reorder_updates_display_order(self):
        data_one = TopicData.objects.create(
            topic=self.topic,
            data={"headers": ["A"], "rows": [["1"]]},
            display_order=1,
        )
        data_two = TopicData.objects.create(
            topic=self.topic,
            data={"headers": ["B"], "rows": [["2"]]},
            display_order=2,
        )
        viz_one = TopicDataVisualization.objects.create(
            topic=self.topic,
            insight=None,
            chart_type="bar",
            chart_data={"labels": ["A"], "datasets": []},
            display_order=1,
        )
        viz_two = TopicDataVisualization.objects.create(
            topic=self.topic,
            insight=None,
            chart_type="line",
            chart_data={"labels": ["B"], "datasets": []},
            display_order=2,
        )

        response = self._post_json(
            "/api/topics/data/reorder",
            {
                "topic_uuid": str(self.topic.uuid),
                "data_items": [
                    {"id": data_two.id, "display_order": 0},
                    {"id": data_one.id, "display_order": 1},
                ],
                "visualization_items": [
                    {"id": viz_two.id, "display_order": 0},
                    {"id": viz_one.id, "display_order": 1},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})

        data_one.refresh_from_db()
        data_two.refresh_from_db()
        viz_one.refresh_from_db()
        viz_two.refresh_from_db()

        self.assertEqual(data_one.display_order, 2)
        self.assertEqual(data_two.display_order, 1)
        self.assertEqual(viz_one.display_order, 2)
        self.assertEqual(viz_two.display_order, 1)

    def test_reorder_requires_authentication(self):
        self.client.logout()
        response = self._post_json(
            "/api/topics/data/reorder",
            {"topic_uuid": str(self.topic.uuid), "data_items": [], "visualization_items": []},
        )
        self.assertEqual(response.status_code, 401)
