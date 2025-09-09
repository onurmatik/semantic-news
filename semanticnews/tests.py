from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from semanticnews.topics.models import Topic
from semanticnews.agenda.models import Event


class SearchViewTests(TestCase):
    @patch("semanticnews.views.OpenAI")
    @patch(
        "semanticnews.topics.models.Topic.get_embedding",
        side_effect=[[0.0] * 1536, [1.0] * 1536],
    )
    def test_search_returns_similar_topics_and_events(
        self, mock_topic_embedding, mock_openai
    ):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.0] * 1536)]
        )

        topic1 = Topic.objects.create(title="Topic One", status="published")
        topic2 = Topic.objects.create(title="Topic Two", status="published")

        Event.objects.create(
            title="Event One",
            date="2024-01-01",
            status="published",
            embedding=[0.0] * 1536,
        )
        Event.objects.create(
            title="Event Two",
            date="2024-01-02",
            status="published",
            embedding=[1.0] * 1536,
        )

        response = self.client.get(reverse("search_results"), {"q": "query"})
        self.assertEqual(response.status_code, 200)
        topics = list(response.context["topics"])
        events = list(response.context["events"])
        self.assertEqual(len(topics), 2)
        self.assertEqual(len(events), 2)
        self.assertEqual(topics[0], topic1)
        self.assertEqual(events[0].title, "Event One")
