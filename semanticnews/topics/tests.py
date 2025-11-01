from unittest.mock import patch, AsyncMock, MagicMock
from datetime import timedelta
from types import SimpleNamespace
import tempfile
import shutil
import json
import re

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from semanticnews.agenda.models import Event
from semanticnews.prompting import get_default_language_instruction

from .models import (
    Topic,
    TopicKeyword,
    RelatedTopic,
    RelatedEntity,
    RelatedEvent,
    Source,
    TopicRecap,
    TopicSection,
)
from semanticnews.entities.models import Entity
from semanticnews.keywords.models import Keyword
from semanticnews.widgets.images.models import TopicImage
from semanticnews.widgets.models import Widget, WidgetType
from semanticnews.widgets.mcps.models import MCPServer
from semanticnews.widgets.data.models import TopicData, TopicDataInsight, TopicDataVisualization
from .publishing import publish_topic
from .api import RelatedEntityInput


class TopicEmbeddingTests(TestCase):
    """Tests for topic embedding generation."""

    def test_get_embedding_skips_api_for_empty_context(self):
        """Avoid requesting embeddings when the context is empty."""

        with patch("semanticnews.topics.models.OpenAI") as mock_openai:
            topic = Topic.objects.create()
            mock_openai.reset_mock()

            embedding = topic.get_embedding(force=True)

        self.assertIsNone(embedding)
        mock_openai.assert_not_called()


class CreateTopicAPITests(TestCase):
    """Tests for the topic creation API endpoint."""

    def test_requires_authentication(self):
        """Unauthenticated requests should be rejected."""

        response = self.client.post("/api/topics/create", {}, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_creates_topic_for_user(self, mock_get_embedding):
        """Authenticated users can create topics."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        response = self.client.post(
            "/api/topics/create", {}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data.keys()), {"uuid"})
        self.assertTrue(data["uuid"])

        self.assertEqual(Topic.objects.count(), 1)
        topic = Topic.objects.first()
        self.assertEqual(topic.created_by, user)
        self.assertEqual(str(topic.uuid), data["uuid"])

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_allows_creating_topic_without_title(self, mock_get_embedding):
        """Users can create draft topics without providing a title."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        response = self.client.post(
            "/api/topics/create", {}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data.keys()), {"uuid"})

        topic = Topic.objects.get()
        self.assertIsNone(topic.title)
        self.assertEqual(topic.status, "draft")


class TopicCreateViewTests(TestCase):
    """Tests for the view that creates topics via the UI flow."""

    def setUp(self):
        self.User = get_user_model()

    def test_requires_authentication(self):
        """Anonymous users are redirected to the login page."""

        response = self.client.get(reverse("topics_create"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_redirects_without_creating_topic(self):
        """Visiting the legacy endpoint no longer creates a topic."""

        user = self.User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        response = self.client.get(reverse("topics_create"), {"title": "My Draft Topic"})

        self.assertRedirects(response, reverse("topics_list"))
        self.assertFalse(Topic.objects.exists())


class TopicDetailRedirectViewTests(TestCase):
    """Tests for redirecting UUID-based topic URLs to slug URLs."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user("user", "user@example.com", "password")

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_redirects_to_slug_detail(self, mock_embedding):
        topic = Topic.objects.create(title="Example", created_by=self.user)

        response = self.client.get(
            reverse(
                "topics_detail_redirect",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.user.username},
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "topics_detail",
                kwargs={"slug": topic.slug, "username": self.user.username},
            ),
        )

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_returns_404_when_slug_missing(self, mock_embedding):
        topic = Topic.objects.create(created_by=self.user)

        response = self.client.get(
            reverse(
                "topics_detail_redirect",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.user.username},
            )
        )

        self.assertEqual(response.status_code, 404)


class TopicDetailEditViewTests(TestCase):
    """Tests for the topic edit view."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user("user", "user@example.com", "password")

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_edit_page_links_to_preview(self, mock_embedding):
        topic = Topic.objects.create(title="Example", created_by=self.user)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                "topics_detail_edit",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.user.username},
            )
        )

        self.assertContains(
            response,
            reverse(
                "topics_detail_preview",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.user.username},
            ),
        )
        self.assertContains(response, ">Preview<")


class TopicDetailPreviewViewTests(TestCase):
    """Tests for the topic preview view."""

    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user("owner", "owner@example.com", "password")
        self.other = self.User.objects.create_user("other", "other@example.com", "password")

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_owner_can_view_preview(self, mock_embedding):
        topic = Topic.objects.create(title="Previewable", created_by=self.owner)

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "topics_detail_preview",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.owner.username},
            )
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("data-topic-status-button", content)
        self.assertIn(
            reverse(
                "topics_detail_edit",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.owner.username},
            ),
            content,
        )

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_non_owner_cannot_preview(self, mock_embedding):
        topic = Topic.objects.create(title="Hidden", created_by=self.owner)

        self.client.force_login(self.other)
        response = self.client.get(
            reverse(
                "topics_detail_preview",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.owner.username},
            )
        )

        self.assertEqual(response.status_code, 403)


class SetTopicTitleAPITests(TestCase):
    """Tests for updating a topic title via the API."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user("user", "user@example.com", "password")

    def test_requires_authentication(self):
        """Unauthenticated requests should be rejected."""

        with patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536):
            topic = Topic.objects.create(created_by=self.user)

        payload = {"topic_uuid": str(topic.uuid), "title": "Updated"}
        response = self.client.post(
            "/api/topics/set-title", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 401)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_updates_title_and_slug(self, mock_embedding):
        """Owners can rename their topics."""

        topic = Topic.objects.create(title="Original", created_by=self.user)
        self.client.force_login(self.user)

        payload = {"topic_uuid": str(topic.uuid), "title": "Updated Title"}
        response = self.client.post(
            "/api/topics/set-title", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        topic.refresh_from_db()
        self.assertEqual(topic.title, "Updated Title")
        self.assertEqual(topic.slug, "updated-title")

        data = response.json()
        self.assertEqual(data["slug"], topic.slug)
        self.assertEqual(
            data["edit_url"],
            reverse(
                "topics_detail_edit",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.user.username},
            ),
        )
        self.assertEqual(
            data["detail_url"],
            reverse(
                "topics_detail_redirect",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.user.username},
            ),
        )

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_allows_clearing_title(self, mock_embedding):
        """Clearing the title removes the slug while keeping the topic editable."""

        topic = Topic.objects.create(title="Named", created_by=self.user)
        self.client.force_login(self.user)

        payload = {"topic_uuid": str(topic.uuid), "title": "   "}
        response = self.client.post(
            "/api/topics/set-title", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        topic.refresh_from_db()
        self.assertIsNone(topic.title)
        self.assertIsNone(topic.slug)

        data = response.json()
        self.assertIsNone(data["slug"])
        self.assertIsNone(data["detail_url"])

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_forbids_updating_other_users_topic(self, mock_embedding):
        """Users cannot rename topics they do not own."""

        other_user = self.User.objects.create_user("other", "other@example.com", "password")
        topic = Topic.objects.create(title="Original", created_by=other_user)

        self.client.force_login(self.user)

        payload = {"topic_uuid": str(topic.uuid), "title": "Updated"}
        response = self.client.post(
            "/api/topics/set-title", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)


class AddEventToTopicAPITests(TestCase):
    """Tests for the endpoint that relates events to topics."""

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_requires_authentication(self, mock_event_embedding, mock_topic_embedding):
        """Unauthenticated requests should be rejected."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        topic = Topic.objects.create(title="My Topic", created_by=user)
        event = Event.objects.create(title="An Event", date="2024-01-01")

        payload = {"topic_uuid": str(topic.uuid), "event_uuid": str(event.uuid)}
        response = self.client.post(
            "/api/topics/add-event", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_adds_event_to_topic(self, mock_event_embedding, mock_topic_embedding):
        """Authenticated users can add events to their topics."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        event = Event.objects.create(title="An Event", date="2024-01-01")

        payload = {"topic_uuid": str(topic.uuid), "event_uuid": str(event.uuid)}
        response = self.client.post(
            "/api/topics/add-event", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(topic.events.count(), 1)
        self.assertEqual(topic.events.first(), event)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_clones_topic_if_not_owner(self, mock_event_embedding, mock_topic_embedding):
        """Adding to someone else's topic clones it for the user."""

        User = get_user_model()
        owner = User.objects.create_user("owner", "owner@example.com", "password")
        other = User.objects.create_user("other", "other@example.com", "password")
        topic = Topic.objects.create(title="Owner Topic", created_by=owner)
        event = Event.objects.create(title="An Event", date="2024-01-01")
        self.client.force_login(other)

        payload = {"topic_uuid": str(topic.uuid), "event_uuid": str(event.uuid)}
        response = self.client.post(
            "/api/topics/add-event", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        cloned = Topic.objects.get(created_by=other, based_on=topic)
        self.assertEqual(cloned.events.count(), 1)
        self.assertEqual(cloned.events.first(), event)


class RemoveEventFromTopicAPITests(TestCase):
    """Tests for the endpoint that removes events from topics."""

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_requires_authentication(self, mock_event_embedding, mock_topic_embedding):
        """Unauthenticated requests should be rejected."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        topic = Topic.objects.create(title="My Topic", created_by=user)
        event = Event.objects.create(title="An Event", date="2024-01-01")
        RelatedEvent.objects.create(topic=topic, event=event, source=Source.USER)

        payload = {"topic_uuid": str(topic.uuid), "event_uuid": str(event.uuid)}
        response = self.client.post(
            "/api/topics/remove-event", payload, content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_removes_event_from_topic(self, mock_event_embedding, mock_topic_embedding):
        """Authenticated users can remove events from their topics."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        event = Event.objects.create(title="An Event", date="2024-01-01")
        RelatedEvent.objects.create(topic=topic, event=event, source=Source.USER)

        payload = {"topic_uuid": str(topic.uuid), "event_uuid": str(event.uuid)}
        response = self.client.post(
            "/api/topics/remove-event", payload, content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(topic.events.count(), 0)


class SetTopicStatusAPITests(TestCase):
    """Tests for the endpoint that updates a topic's status."""

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_requires_authentication(self, mock_topic_embedding):
        """Unauthenticated requests should be rejected."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        topic = Topic.objects.create(title="My Topic", created_by=user)

        payload = {"topic_uuid": str(topic.uuid), "status": "published"}
        response = self.client.post(
            "/api/topics/set-status", payload, content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_creator_can_publish_topic(self, mock_topic_embedding):
        """Topic creators can update the status of their topics."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        TopicRecap.objects.create(topic=topic, recap="Recap", status="finished")

        payload = {"topic_uuid": str(topic.uuid), "status": "published"}
        response = self.client.post(
            "/api/topics/set-status", payload, content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        topic.refresh_from_db()
        self.assertEqual(topic.status, "published")

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_cannot_publish_topic_without_title(self, mock_topic_embedding):
        """Publishing a topic without a title should be rejected."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title=None, created_by=user)

        payload = {"topic_uuid": str(topic.uuid), "status": "published"}
        response = self.client.post(
            "/api/topics/set-status", payload, content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json().get("detail"),
            "A title is required to publish a topic.",
        )
        topic.refresh_from_db()
        self.assertEqual(topic.status, "draft")

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_cannot_publish_topic_without_recap(self, mock_topic_embedding):
        """Publishing requires at least one completed recap."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)

        payload = {"topic_uuid": str(topic.uuid), "status": "published"}
        response = self.client.post(
            "/api/topics/set-status", payload, content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json().get("detail"),
            "A recap is required to publish a topic.",
        )
        topic.refresh_from_db()
        self.assertEqual(topic.status, "draft")

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_cannot_publish_topic_without_recap(self, mock_topic_embedding):
        """Publishing requires at least one completed recap."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)

        payload = {"topic_uuid": str(topic.uuid), "status": "published"}
        response = self.client.post(
            "/api/topics/set-status", payload, content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        topic.refresh_from_db()
        self.assertEqual(topic.status, "draft")

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_non_creator_cannot_publish_topic(self, mock_topic_embedding):
        """Only the creator can change the topic status."""

        User = get_user_model()
        creator = User.objects.create_user("creator", "creator@example.com", "password")
        other = User.objects.create_user("other", "other@example.com", "password")

        topic = Topic.objects.create(title="My Topic", created_by=creator)

        self.client.force_login(other)

        payload = {"topic_uuid": str(topic.uuid), "status": "published"}
        response = self.client.post(
            "/api/topics/set-status", payload, content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        topic.refresh_from_db()
        self.assertEqual(topic.status, "draft")


class CreateRecapAPITests(TestCase):
    """Tests for the recap creation API endpoint."""

    @patch("semanticnews.topics.recaps.api.OpenAI")
    @patch(
        "semanticnews.topics.models.Topic.get_embedding",
        return_value=[0.0] * 1536,
    )
    def test_returns_ai_suggestion_and_updates_recap(
        self, mock_topic_embedding, mock_openai
    ):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = {"recap": "Recap"}
        mock_client.responses.parse.return_value = mock_response

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)

        payload = {"topic_uuid": str(topic.uuid)}
        response = self.client.post(
            "/api/topics/recap/create", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"recap": "Recap"})
        self.assertEqual(TopicRecap.objects.count(), 1)
        recap = TopicRecap.objects.first()
        self.assertEqual(recap.recap, "Recap")
        self.assertEqual(recap.status, "finished")
        self.assertIsNone(recap.published_at)

    def test_creates_recap_with_provided_text(self):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)

        payload = {"topic_uuid": str(topic.uuid), "recap": "My recap"}
        response = self.client.post(
            "/api/topics/recap/create", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"recap": "My recap"})
        self.assertEqual(TopicRecap.objects.count(), 1)
        self.assertEqual(TopicRecap.objects.first().recap, "My recap")

    def test_subsequent_manual_updates_reuse_existing_recap(self):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)

        payload = {"topic_uuid": str(topic.uuid), "recap": "Initial recap"}
        self.client.post(
            "/api/topics/recap/create", payload, content_type="application/json"
        )

        payload["recap"] = "Updated recap"
        response = self.client.post(
            "/api/topics/recap/create", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"recap": "Updated recap"})
        self.assertEqual(TopicRecap.objects.count(), 1)
        recap = TopicRecap.objects.first()
        self.assertEqual(recap.recap, "Updated recap")
        self.assertIsNone(recap.published_at)


class AnalyzeDataAPITests(TestCase):
    """Tests for the data analysis API endpoint."""

    @patch("semanticnews.widgets.data.api.OpenAI")
    @patch(
        "semanticnews.topics.models.Topic.get_embedding",
        return_value=[0.0] * 1536,
    )
    def test_passes_extra_instructions_to_ai(self, mock_embedding, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = {"insights": ["I1"]}
        mock_client.responses.parse.return_value = mock_response

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        data = TopicData.objects.create(
            topic=topic,
            url="http://example.com",
            data={"headers": ["A"], "rows": [["1"]]},
        )

        payload = {
            "topic_uuid": str(topic.uuid),
            "data_ids": [data.id],
            "instructions": "Focus on anomalies",
        }
        self.client.post(
            "/api/topics/data/analyze", payload, content_type="application/json"
        )

        args, kwargs = mock_client.responses.parse.call_args
        self.assertIn("Focus on anomalies", kwargs["input"])
        self.assertIn(get_default_language_instruction(), kwargs["input"])

    @patch("semanticnews.widgets.data.api.OpenAI")
    @patch(
        "semanticnews.topics.models.Topic.get_embedding",
        return_value=[0.0] * 1536,
    )
    def test_returns_ai_insights_without_saving(self, mock_embedding, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = {"insights": ["I1", "I2"]}
        mock_client.responses.parse.return_value = mock_response

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        data = TopicData.objects.create(
            topic=topic,
            url="http://example.com",
            data={"headers": ["A"], "rows": [["1"]]},
        )

        payload = {"topic_uuid": str(topic.uuid), "data_ids": [data.id]}
        response = self.client.post(
            "/api/topics/data/analyze", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"insights": ["I1", "I2"]})
        self.assertEqual(topic.data_insights.count(), 0)

    @patch("semanticnews.widgets.data.api.OpenAI")
    @patch(
        "semanticnews.topics.models.Topic.get_embedding",
        return_value=[0.0] * 1536,
    )
    def test_limits_number_of_insights(self, mock_embedding, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = {
            "insights": ["I1", "I2", "I3", "I4"]
        }
        mock_client.responses.parse.return_value = mock_response

        User = get_user_model()
        user = User.objects.create_user(
            "user", "user@example.com", "password"
        )
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        data = TopicData.objects.create(
            topic=topic,
            url="http://example.com",
            data={"headers": ["A"], "rows": [["1"]]},
        )

        payload = {"topic_uuid": str(topic.uuid), "data_ids": [data.id]}
        response = self.client.post(
            "/api/topics/data/analyze", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"insights": ["I1", "I2", "I3"]})

    @patch(
        "semanticnews.topics.models.Topic.get_embedding",
        return_value=[0.0] * 1536,
    )
    def test_saves_provided_insights(self, mock_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        data = TopicData.objects.create(
            topic=topic,
            url="http://example.com",
            data={"headers": ["A"], "rows": [["1"]]},
        )

        payload = {
            "topic_uuid": str(topic.uuid),
            "data_ids": [data.id],
            "insights": ["Insight A", "Insight B"],
        }
        response = self.client.post(
            "/api/topics/data/analyze", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(topic.data_insights.count(), 2)
        self.assertListEqual(
            list(topic.data_insights.values_list("insight", flat=True)),
            ["Insight A", "Insight B"],
        )
        for insight in topic.data_insights.all():
            self.assertListEqual(
                list(insight.sources.values_list("id", flat=True)),
                [data.id],
            )


class VisualizeDataAPITests(TestCase):
    """Tests for the data visualization API endpoint."""

    @patch("semanticnews.widgets.data.api.OpenAI")
    def test_creates_visualization(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = {
            "chart_type": "bar",
            "data": {"labels": ["A"], "datasets": [{"label": "Values", "data": [1]}]},
        }
        mock_client.responses.parse.return_value = mock_response

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        data = TopicData.objects.create(
            topic=topic,
            url="http://example.com",
            data={"headers": ["A"], "rows": [["1"]]},
        )
        insight = TopicDataInsight.objects.create(topic=topic, insight="Insight")
        insight.sources.add(data)

        payload = {
            "topic_uuid": str(topic.uuid),
            "insight_id": insight.id,
            "instructions": "Highlight revenue trends.",
        }
        response = self.client.post(
            "/api/topics/data/visualize", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TopicDataVisualization.objects.count(), 1)
        viz = TopicDataVisualization.objects.first()
        self.assertEqual(viz.chart_type, "bar")
        self.assertEqual(viz.display_order, 1)
        self.assertEqual(response.json(), {
            "id": viz.id,
            "insight": "Insight",
            "chart_type": "bar",
            "chart_data": {"labels": ["A"], "datasets": [{"label": "Values", "data": [1]}]},
        })
        called_kwargs = mock_client.responses.parse.call_args.kwargs
        self.assertIn("Highlight revenue trends.", called_kwargs["input"])

    @patch("semanticnews.widgets.data.api.OpenAI")
    def test_creates_visualization_with_chart_type(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = {
            "chart_type": "pie",
            "data": {"labels": ["A"], "datasets": [{"label": "Values", "data": [1]}]},
        }
        mock_client.responses.parse.return_value = mock_response

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        data = TopicData.objects.create(
            topic=topic,
            url="http://example.com",
            data={"headers": ["A"], "rows": [["1"]]},
        )
        insight = TopicDataInsight.objects.create(topic=topic, insight="Insight")
        insight.sources.add(data)

        payload = {"topic_uuid": str(topic.uuid), "insight_id": insight.id, "chart_type": "pie"}
        response = self.client.post(
            "/api/topics/data/visualize", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TopicDataVisualization.objects.count(), 1)
        viz = TopicDataVisualization.objects.first()
        self.assertEqual(viz.chart_type, "pie")
        self.assertEqual(viz.display_order, 1)
        self.assertEqual(response.json(), {
            "id": viz.id,
            "insight": "Insight",
            "chart_type": "pie",
            "chart_data": {"labels": ["A"], "datasets": [{"label": "Values", "data": [1]}]},
        })

    @patch("semanticnews.widgets.data.api.OpenAI")
    def test_visualizes_custom_insight(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = {
            "chart_type": "bar",
            "data": {"labels": ["A"], "datasets": [{"label": "Values", "data": [1]}]},
        }
        mock_client.responses.parse.return_value = mock_response

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        TopicData.objects.create(
            topic=topic,
            url="http://example.com",
            data={"headers": ["A"], "rows": [["1"]]},
        )

        payload = {"topic_uuid": str(topic.uuid), "insight": "Custom"}
        response = self.client.post(
            "/api/topics/data/visualize", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TopicDataVisualization.objects.count(), 1)
        viz = TopicDataVisualization.objects.first()
        self.assertEqual(viz.chart_type, "bar")
        self.assertIsNone(viz.insight)
        self.assertEqual(viz.display_order, 1)
        self.assertEqual(response.json(), {
            "id": viz.id,
            "insight": "Custom",
            "chart_type": "bar",
            "chart_data": {"labels": ["A"], "datasets": [{"label": "Values", "data": [1]}]},
        })


class TopicDetailViewTests(TestCase):
    """Tests for the topic detail view."""

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_shows_related_and_suggested_events(self, mock_event_embedding, mock_topic_embedding):
        """The view lists related and suggested agenda events."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        topic = Topic.objects.create(title="My Topic", created_by=user)

        related = Event.objects.create(title="Related", date="2024-01-01")
        RelatedEvent.objects.create(topic=topic, event=related, source=Source.USER)

        suggested = Event.objects.create(title="Suggested", date="2024-01-02")

        response = self.client.get(topic.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertIn(related, response.context["related_events"])
        self.assertIn(suggested, response.context["suggested_events"])
        self.assertNotIn(related, response.context["suggested_events"])

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_related_event_buttons_depends_on_topic_owner(self, mock_event_embedding, mock_topic_embedding):
        """Topic owners can remove related events; others can add them to their topics."""

        User = get_user_model()
        owner = User.objects.create_user("owner", "owner@example.com", "password")
        other = User.objects.create_user("other", "other@example.com", "password")

        topic = Topic.objects.create(title="My Topic", created_by=owner)
        other_topic = Topic.objects.create(title="Other Topic", created_by=other)

        related = Event.objects.create(title="Rel Event", date="2024-01-01", created_by=other)
        RelatedEvent.objects.create(topic=topic, event=related, source=Source.USER)

        suggested = Event.objects.create(title="Sug Event", date="2024-02-01", created_by=other)

        # Owner view: should see remove button for related event and add button for suggested
        self.client.force_login(owner)
        response = self.client.get(topic.get_absolute_url())
        content = response.content.decode()
        self.assertRegex(
            content,
            rf'(?s)<button[^>]*class="[^"]*remove-event-btn[^"]*"[^>]*data-event-uuid="{related.uuid}"',
        )
        self.assertNotRegex(
            content,
            rf'(?s)<a[^>]*class="[^"]*add-to-topic[^"]*"[^>]*data-event-uuid="{related.uuid}"',
        )
        self.assertRegex(
            content,
            rf'(?s)<a[^>]*class="[^"]*add-to-topic[^"]*"[^>]*data-event-uuid="{suggested.uuid}"',
        )

        # Other user view: should see add button, not remove button, for related event
        self.client.force_login(other)
        response = self.client.get(topic.get_absolute_url())
        content = response.content.decode()
        self.assertNotRegex(
            content,
            rf'(?s)<button[^>]*class="[^"]*remove-event-btn[^"]*"[^>]*data-event-uuid="{related.uuid}"',
        )
        self.assertRegex(
            content,
            rf'(?s)<a[^>]*class="[^"]*add-to-topic[^"]*"[^>]*data-event-uuid="{related.uuid}"',
        )

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_latest_recap_displayed(self, mock_event_embedding, mock_topic_embedding):
        """The most recent recap is shown on the detail page."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        topic = Topic.objects.create(title="My Topic", created_by=user)
        TopicRecap.objects.create(topic=topic, recap="Old recap")
        latest = TopicRecap.objects.create(topic=topic, recap="New recap")

        response = self.client.get(topic.get_absolute_url())
        content = response.content.decode()

        self.assertEqual(response.context["latest_recap"], latest)
        self.assertIn("New recap", content)
        self.assertNotIn("Old recap", content)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_recap_rendered_as_markdown(self, mock_event_embedding, mock_topic_embedding):
        """Recap text is rendered using the markdown filter."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        topic = Topic.objects.create(title="My Topic", created_by=user)
        TopicRecap.objects.create(topic=topic, recap="**Bold** text")

        response = self.client.get(topic.get_absolute_url())
        content = response.content.decode()

        self.assertIn("<strong>Bold</strong> text", content)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_mcp_servers_dropdown_lists_active_servers(
        self, mock_event_embedding, mock_topic_embedding
    ):
        """Context dropdown lists only active MCP servers."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        MCPServer.objects.create(name="Active", url="http://a")
        MCPServer.objects.create(name="Inactive", url="http://b", active=False)

        response = self.client.get(topic.get_absolute_url())
        content = response.content.decode()

        self.assertIn("Context", content)
        self.assertIn("Active", content)
        self.assertNotIn("Inactive", content)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_shows_based_on_reference(self, mock_topic_embedding):
        """Detail view shows link to original when topic is based on another."""

        User = get_user_model()
        owner = User.objects.create_user("owner", "owner@example.com", "password")
        cloner = User.objects.create_user("cloner", "cloner@example.com", "password")

        original = Topic.objects.create(title="Original", created_by=owner)
        derived = Topic.objects.create(title="Derived", created_by=cloner, based_on=original)

        response = self.client.get(derived.get_absolute_url())
        content = response.content.decode()

        self.assertIn(
            f'based on <a class="text-info-emphasis" href="{original.get_absolute_url()}">@{owner.username}\'s version</a>',
            content,
        )

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_topic_image_displayed(self, mock_topic_embedding):
        """The topic image is shown at the top of the content area when present."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)
        override = self.settings(MEDIA_ROOT=tmpdir)
        override.enable()
        self.addCleanup(override.disable)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        image_bytes = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        TopicImage.objects.create(
            topic=topic,
            image=SimpleUploadedFile("image.gif", image_bytes, content_type="image/gif"),
            is_hero=True,
        )

        response = self.client.get(topic.get_absolute_url())
        content = response.content.decode()

        self.assertIn(topic.images.first().image.url, content)


class TopicAddEventViewTests(TestCase):
    """Tests for adding suggested events to a topic via the view."""

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_user_can_add_suggested_event(self, mock_event_embedding, mock_topic_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        event = Event.objects.create(title="Suggested", date="2024-01-01")

        url = reverse(
            "topics_add_event",
            kwargs={"username": user.username, "slug": topic.slug, "event_uuid": event.uuid},
        )
        response = self.client.post(url)

        self.assertRedirects(response, topic.get_absolute_url())
        self.assertIn(event, topic.events.all())


class TopicRemoveEventViewTests(TestCase):
    """Tests for removing related events from a topic via the view."""

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_user_can_remove_related_event(self, mock_event_embedding, mock_topic_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        event = Event.objects.create(title="Related", date="2024-01-01")
        RelatedEvent.objects.create(topic=topic, event=event, source=Source.USER)

        url = reverse(
            "topics_remove_event",
            kwargs={"username": user.username, "slug": topic.slug, "event_uuid": event.uuid},
        )
        response = self.client.post(url)

        self.assertRedirects(response, topic.get_absolute_url())
        self.assertNotIn(event, topic.events.all())


class TopicCloneTests(TestCase):
    """Tests for cloning a topic and its related content."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir)
        override = self.settings(MEDIA_ROOT=self.tmpdir)
        override.enable()
        self.addCleanup(override.disable)

        User = get_user_model()
        self.owner = User.objects.create_user("owner", "owner@example.com", "password")
        self.cloner = User.objects.create_user("cloner", "cloner@example.com", "password")

        self.topic = Topic.objects.create(title="Original", created_by=self.owner, embedding=[0.0] * 1536)

        self.event = Event.objects.create(title="Event", date="2024-01-01", embedding=[0.0] * 1536)
        RelatedEvent.objects.create(
            topic=self.topic,
            event=self.event,
            source=Source.USER,
        )

        TopicRecap.objects.create(topic=self.topic, recap="Recap")

        image_data = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
            b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02L\x01\x00;"
        )
        image_file = SimpleUploadedFile("image.gif", image_data, content_type="image/gif")
        TopicImage.objects.create(topic=self.topic, image=image_file, is_hero=True)

        keyword = Keyword.objects.create(name="Keyword")
        TopicKeyword.objects.create(topic=self.topic, keyword=keyword, created_by=self.owner)

    def test_clone_creates_copy_with_related_objects(self):
        self.client.force_login(self.cloner)
        url = reverse(
            "topics_clone",
            kwargs={"username": self.owner.username, "slug": self.topic.slug},
        )
        response = self.client.get(url)
        self.assertRedirects(
            response,
            reverse(
                "topics_detail",
                kwargs={"username": self.cloner.username, "slug": self.topic.slug},
            ),
        )

        cloned = Topic.objects.get(created_by=self.cloner)
        self.assertEqual(cloned.based_on, self.topic)
        self.assertEqual(cloned.events.count(), 1)
        self.assertEqual(cloned.recaps.count(), 1)
        self.assertEqual(cloned.images.count(), 1)
        self.assertEqual(cloned.keywords.count(), 1)

    def test_clone_button_visible_for_non_creator(self):
        self.client.force_login(self.cloner)
        response = self.client.get(self.topic.get_absolute_url())
        clone_url = reverse(
            "topics_clone",
            kwargs={"username": self.owner.username, "slug": self.topic.slug},
        )
        self.assertContains(response, clone_url)


class TopicSectionRenderingTests(TestCase):
    """Ensure topic sections are rendered via the unified widget templates."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            "author", "author@example.com", "password"
        )
        self.client.force_login(self.user)
        self.widget = Widget.objects.create(
            name="Summary",
            type=WidgetType.TEXT,
            response_format={"type": "markdown", "sections": ["summary"]},
        )

    def test_detail_view_renders_section_content(self):
        topic = Topic.objects.create(
            title="My Topic", created_by=self.user, status="published"
        )
        TopicSection.objects.create(
            topic=topic,
            widget=self.widget,
            content={"summary": "**Key finding**"},
            status="finished",
            published_at=timezone.now(),
        )

        response = self.client.get(topic.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Key finding")

    def test_edit_view_shows_unpublished_sections(self):
        topic = Topic.objects.create(title="Draft", created_by=self.user)
        TopicSection.objects.create(
            topic=topic,
            widget=self.widget,
            content={"summary": "Draft block"},
            status="in_progress",
        )

        response = self.client.get(
            reverse(
                "topics_detail_edit",
                kwargs={
                    "username": self.user.username,
                    "topic_uuid": topic.uuid,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Draft block")


class TopicEmbeddingUpdateTests(TestCase):
    """Ensure the topic embedding is refreshed when the topic changes."""

    @patch("semanticnews.topics.models.Topic.get_embedding", side_effect=[[0.0] * 1536, [1.0] * 1536])
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_embedding_recomputed_when_event_added(self, mock_event_embedding, mock_topic_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        topic = Topic.objects.create(title="My Topic", created_by=user)
        event = Event.objects.create(title="An Event", date="2024-01-01")

        # Adding an event should trigger a recomputation of the embedding
        RelatedEvent.objects.create(topic=topic, event=event, source=Source.USER)

        topic.refresh_from_db()
        self.assertEqual(topic.embedding, [1.0] * 1536)

    @patch("semanticnews.topics.models.Topic.get_embedding", side_effect=[[0.0] * 1536, [1.0] * 1536])
    def test_embedding_recomputed_on_save(self, mock_topic_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        topic = Topic.objects.create(title="Old", created_by=user)

        topic.title = "New"
        topic.save()

        self.assertEqual(topic.embedding, [1.0] * 1536)


class TopicListViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("alice", "alice@example.com", "password")

    def test_lists_only_published_topics(self):
        Topic.objects.create(title="Draft Topic", created_by=self.user, status="draft")
        published = Topic.objects.create(
            title="Published Topic",
            created_by=self.user,
            status="published",
        )

        response = self.client.get(reverse("topics_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, published.title)
        self.assertNotContains(response, "Draft Topic")


class RelatedTopicModelTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            "owner", "owner@example.com", "password"
        )
        self.other = self.User.objects.create_user(
            "other", "other@example.com", "password"
        )

    def test_active_related_topic_links_excludes_deleted(self):
        topic = Topic.objects.create(title="Primary", created_by=self.owner)
        related_a = Topic.objects.create(title="A", created_by=self.other, status="published")
        related_b = Topic.objects.create(title="B", created_by=self.other, status="published")

        active = RelatedTopic.objects.create(
            topic=topic,
            related_topic=related_a,
            created_by=self.owner,
        )
        RelatedTopic.objects.create(
            topic=topic,
            related_topic=related_b,
            created_by=self.owner,
            is_deleted=True,
        )

        links = list(topic.active_related_topic_links)
        self.assertEqual(links, [active])
        active_topics = list(topic.active_related_topics)
        self.assertEqual(active_topics, [related_a])

    def test_clone_for_user_copies_active_links(self):
        topic = Topic.objects.create(title="Original", created_by=self.owner)
        related = Topic.objects.create(title="Linked", created_by=self.other, status="published")
        RelatedTopic.objects.create(
            topic=topic,
            related_topic=related,
            created_by=self.owner,
        )
        RelatedTopic.objects.create(
            topic=topic,
            related_topic=Topic.objects.create(
                title="Ignored", created_by=self.other, status="published"
            ),
            created_by=self.owner,
            is_deleted=True,
        )

        clone_user = self.User.objects.create_user(
            "clone", "clone@example.com", "password"
        )
        clone = topic.clone_for_user(clone_user)

        links = clone.topic_related_topics.all()
        self.assertEqual(links.count(), 1)
        link = links.first()
        self.assertEqual(link.related_topic, related)
        self.assertEqual(link.source, RelatedTopic.Source.MANUAL)
        self.assertEqual(link.created_by, clone_user)

    def test_build_context_ignores_related_topics(self):
        topic = Topic.objects.create(title="Primary", created_by=self.owner)
        related = Topic.objects.create(title="Sensitive", created_by=self.other, status="published")
        RelatedTopic.objects.create(
            topic=topic,
            related_topic=related,
            created_by=self.owner,
        )

        context = topic.build_context()
        self.assertNotIn("Sensitive", context)


class TopicSectionModelTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            "owner", "owner@example.com", "password"
        )
        self.topic = Topic.objects.create(title="Primary", created_by=self.owner)
        self.widget = Widget.objects.create(
            name="Summary",
            type=WidgetType.TEXT,
            response_format={"type": "markdown", "sections": ["summary"]},
        )

    def test_active_queryset_filters_deleted(self):
        active_section = TopicSection.objects.create(
            topic=self.topic,
            widget=self.widget,
            display_order=1,
            content={"summary": "Hello"},
            status="finished",
        )
        TopicSection.objects.create(
            topic=self.topic,
            widget=self.widget,
            display_order=2,
            content={"summary": "Discarded"},
            is_deleted=True,
            status="finished",
        )

        sections = list(self.topic.sections.active())
        self.assertEqual(sections, [active_section])

    def test_validation_enforces_required_sections(self):
        section = TopicSection(
            topic=self.topic,
            widget=self.widget,
            content={"details": "Missing summary"},
            status="finished",
        )

        with self.assertRaises(ValidationError) as exc:
            section.full_clean()

        self.assertIn("Missing required sections", exc.exception.messages[0])

    def test_validation_enforces_max_items(self):
        widget = Widget.objects.create(
            name="Links",
            type=WidgetType.WEBCONTENT,
            response_format={"type": "link_list", "max_items": 1},
        )
        section = TopicSection(
            topic=self.topic,
            widget=widget,
            content=[{"title": "First"}, {"title": "Second"}],
            status="finished",
        )

        with self.assertRaises(ValidationError) as exc:
            section.full_clean()

        self.assertIn("A maximum of 1 items are allowed.", exc.exception.messages[0])


class RelatedTopicPublishTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            "publisher", "publisher@example.com", "password"
        )

    def _create_topic(self, title="Primary", status="draft"):
        topic = Topic.objects.create(title=title, created_by=self.owner, status=status)
        TopicRecap.objects.create(topic=topic, recap="Summary", status="finished")
        return topic

    @patch("semanticnews.topics.publishing.Topic.get_similar_topics")
    def test_publish_seeds_auto_links_when_missing_manual(self, mock_similar):
        topic = self._create_topic()
        similar_a = Topic.objects.create(
            title="Similar A", created_by=self.owner, status="published"
        )
        similar_b = Topic.objects.create(
            title="Similar B", created_by=self.owner, status="published"
        )
        mock_similar.return_value = [similar_a, similar_b]

        publish_topic(topic, self.owner)

        links = RelatedTopic.objects.filter(topic=topic).order_by("related_topic__title")
        self.assertEqual(links.count(), 2)
        for link in links:
            self.assertEqual(link.source, RelatedTopic.Source.AUTO)
            self.assertEqual(link.created_by, self.owner)
            self.assertIsNotNone(link.published_at)

    @patch("semanticnews.topics.publishing.Topic.get_similar_topics")
    def test_publish_does_not_seed_when_manual_exists(self, mock_similar):
        topic = self._create_topic()
        manual_target = Topic.objects.create(
            title="Manual", created_by=self.owner, status="published"
        )
        RelatedTopic.objects.create(
            topic=topic,
            related_topic=manual_target,
            created_by=self.owner,
            source=RelatedTopic.Source.MANUAL,
        )

        publish_topic(topic, self.owner)

        mock_similar.assert_not_called()
        link = RelatedTopic.objects.get(topic=topic, related_topic=manual_target)
        self.assertEqual(link.source, RelatedTopic.Source.MANUAL)
        self.assertIsNotNone(link.published_at)


class TopicRecapPublishFlowTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            "recapper", "recapper@example.com", "password"
        )

    def _topic_with_recap(self) -> Topic:
        topic = Topic.objects.create(title="Story", created_by=self.owner)
        TopicRecap.objects.create(topic=topic, recap="Initial", status="finished")
        return topic

    def test_publish_marks_current_recap_and_creates_new_draft(self):
        topic = self._topic_with_recap()

        publish_topic(topic, self.owner)

        recaps = list(topic.recaps.order_by("created_at"))
        self.assertEqual(len(recaps), 2)

        published = recaps[0]
        draft = recaps[1]

        self.assertIsNotNone(published.published_at)
        self.assertEqual(published.status, "finished")
        self.assertEqual(published.recap, "Initial")

        self.assertIsNone(draft.published_at)
        self.assertEqual(draft.status, "finished")
        self.assertEqual(draft.recap, "Initial")

    def test_publish_does_not_create_duplicate_draft_when_one_exists(self):
        topic = Topic.objects.create(title="Story", created_by=self.owner)
        published_recap = TopicRecap.objects.create(
            topic=topic,
            recap="Old",
            status="finished",
            published_at=timezone.now(),
        )
        current = TopicRecap.objects.create(topic=topic, recap="Working", status="finished")
        existing_draft = TopicRecap.objects.create(
            topic=topic,
            recap="Future",
            status="finished",
        )

        publish_topic(topic, self.owner)

        recaps = topic.recaps.order_by("created_at")
        self.assertEqual(recaps.count(), 3)

        current.refresh_from_db()
        self.assertIsNotNone(current.published_at)
        self.assertEqual(current.recap, "Working")

        existing_draft.refresh_from_db()
        self.assertIsNone(existing_draft.published_at)
        self.assertEqual(existing_draft.recap, "Future")

        published_recap.refresh_from_db()
        self.assertIsNotNone(published_recap.published_at)

class TopicPublishSnapshotImageTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            "owner", "owner@example.com", "password"
        )

    def _create_topic(self):
        topic = Topic.objects.create(title="Primary", created_by=self.owner)
        TopicRecap.objects.create(topic=topic, recap="Summary", status="finished")
        return topic

    def _create_image(self, topic, **overrides):
        image_bytes = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        defaults = {
            "image": SimpleUploadedFile("test.gif", image_bytes, content_type="image/gif"),
            "status": "finished",
            "is_hero": False,
        }
        defaults.update(overrides)
        return TopicImage.objects.create(topic=topic, **defaults)

    @patch("semanticnews.topics.publishing.Topic.get_similar_topics", return_value=[])
    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_publish_excludes_cleared_hero_image(
        self, _mock_embedding, _mock_similar
    ):
        topic = self._create_topic()
        self._create_image(topic, is_hero=False)

        publication = publish_topic(topic, self.owner)

        self.assertIsNone(publication.context_snapshot.get("image"))
        self.assertEqual(len(publication.context_snapshot.get("images", [])), 1)
        self.assertFalse(publication.context_snapshot["images"][0].get("is_hero"))

    @patch("semanticnews.topics.publishing.Topic.get_similar_topics", return_value=[])
    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_publish_marks_active_hero_image(
        self, _mock_embedding, _mock_similar
    ):
        topic = self._create_topic()
        self._create_image(topic, is_hero=True)

        publication = publish_topic(topic, self.owner)

        hero_image = publication.context_snapshot.get("image")
        self.assertIsNotNone(hero_image)
        self.assertTrue(hero_image.get("is_hero"))
        self.assertTrue(publication.context_snapshot["images"][0].get("is_hero"))


class RelatedTopicsAPITests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            "owner", "owner@example.com", "password"
        )
        self.other = self.User.objects.create_user(
            "viewer", "viewer@example.com", "password"
        )
        self.topic = Topic.objects.create(title="Primary", created_by=self.owner)
        self.related = Topic.objects.create(
            title="Related", created_by=self.owner, status="published"
        )

    def _list_endpoint(self):
        return f"/api/topics/{self.topic.uuid}/related-topics"

    def _search_endpoint(self, query):
        return f"/api/topics/{self.topic.uuid}/related-topics/search?query={query}"

    def test_owner_can_list_related_topics(self):
        RelatedTopic.objects.create(
            topic=self.topic,
            related_topic=self.related,
            created_by=self.owner,
        )
        another = Topic.objects.create(title="Other", created_by=self.owner, status="published")
        RelatedTopic.objects.create(
            topic=self.topic,
            related_topic=another,
            created_by=self.owner,
            is_deleted=True,
        )
        self.client.force_login(self.owner)

        response = self.client.get(self._list_endpoint())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        active = next(item for item in data if not item["is_deleted"])
        self.assertEqual(active["title"], "Related")

    def test_search_marks_existing_links(self):
        RelatedTopic.objects.create(
            topic=self.topic,
            related_topic=self.related,
            created_by=self.owner,
        )
        self.client.force_login(self.owner)

        response = self.client.get(self._search_endpoint("Rel"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any(item["is_already_linked"] for item in data))

    def test_add_related_topic_creates_manual_link(self):
        self.client.force_login(self.owner)
        payload = {"related_topic_uuid": str(self.related.uuid)}
        response = self.client.post(
            self._list_endpoint(),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        link = RelatedTopic.objects.get(topic=self.topic, related_topic=self.related)
        self.assertEqual(link.source, RelatedTopic.Source.MANUAL)
        self.assertFalse(link.is_deleted)

    def test_add_related_topic_rejects_duplicates(self):
        RelatedTopic.objects.create(
            topic=self.topic,
            related_topic=self.related,
            created_by=self.owner,
        )
        self.client.force_login(self.owner)
        payload = {"related_topic_uuid": str(self.related.uuid)}
        response = self.client.post(
            self._list_endpoint(),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_remove_and_restore_related_topic(self):
        link = RelatedTopic.objects.create(
            topic=self.topic,
            related_topic=self.related,
            created_by=self.owner,
        )
        self.client.force_login(self.owner)

        response = self.client.delete(f"{self._list_endpoint()}/{link.id}")
        self.assertEqual(response.status_code, 200)
        link.refresh_from_db()
        self.assertTrue(link.is_deleted)

        response = self.client.post(f"{self._list_endpoint()}/{link.id}/restore")
        self.assertEqual(response.status_code, 200)
        link.refresh_from_db()
        self.assertFalse(link.is_deleted)

    def test_non_owner_cannot_manage_related_topics(self):
        self.client.force_login(self.other)
        response = self.client.get(self._list_endpoint())
        self.assertEqual(response.status_code, 403)


class RelatedTopicsTemplateTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            "owner", "owner@example.com", "password"
        )
        self.viewer = self.User.objects.create_user(
            "viewer", "viewer@example.com", "password"
        )

    def _prepare_topic_with_related(self):
        topic = Topic.objects.create(title="Primary", created_by=self.owner)
        TopicRecap.objects.create(topic=topic, recap="Recap", status="finished")
        related = Topic.objects.create(
            title="Linked Topic", created_by=self.viewer, status="published"
        )
        RelatedTopic.objects.create(
            topic=topic,
            related_topic=related,
            created_by=self.owner,
        )
        publish_topic(topic, self.owner)
        return topic, related

    def test_detail_view_renders_related_topics(self):
        topic, related = self._prepare_topic_with_related()
        response = self.client.get(
            reverse(
                "topics_detail",
                kwargs={"slug": topic.slug, "username": self.owner.username},
            )
        )
        self.assertContains(response, "Related topics")
        self.assertContains(response, related.title)

    @patch("semanticnews.topics.publishing.Topic.get_similar_topics", return_value=[])
    def test_detail_view_hides_related_topics_without_links(self, _mock_similar):
        topic = Topic.objects.create(title="Primary", created_by=self.owner)
        TopicRecap.objects.create(topic=topic, recap="Recap", status="finished")

        publish_topic(topic, self.owner)

        response = self.client.get(
            reverse(
                "topics_detail",
                kwargs={"slug": topic.slug, "username": self.owner.username},
            )
        )
        self.assertNotContains(response, "Related topics")
        self.assertNotContains(response, 'data-module="related_topics"')

    def test_edit_view_includes_related_topics_module(self):
        topic, related = self._prepare_topic_with_related()
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "topics_detail_edit",
                kwargs={"topic_uuid": str(topic.uuid), "username": self.owner.username},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-related-topics-card")




class RelatedEntityAPITests(TestCase):
    """Tests for the topic related entity API endpoints."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("owner", "owner@example.com", "password")
        self.other = User.objects.create_user("other", "other@example.com", "password")
        self.topic = Topic.objects.create(created_by=self.user)

    def test_extract_requires_authentication(self):
        payload = {"topic_uuid": str(self.topic.uuid), "entities": [{"name": "Alice"}]}
        response = self.client.post(
            "/api/topics/relation/extract",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_list_requires_owner(self):
        response = self.client.get(f"/api/topics/relation/{self.topic.uuid}/list")
        self.assertEqual(response.status_code, 401)

        self.client.force_login(self.other)
        response = self.client.get(f"/api/topics/relation/{self.topic.uuid}/list")
        self.assertEqual(response.status_code, 403)

    def test_create_list_and_delete_entities(self):
        self.client.force_login(self.user)
        payload = {
            "topic_uuid": str(self.topic.uuid),
            "entities": [
                {"name": "Alice", "role": "Speaker"},
                {"name": "Bob", "disambiguation": "Journalist"},
            ],
        }

        response = self.client.post(
            "/api/topics/relation/extract",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data.get("entities", [])), 2)

        relations = RelatedEntity.objects.filter(topic=self.topic, is_deleted=False)
        self.assertEqual(relations.count(), 2)
        names = set(rel.entity.name for rel in relations)
        self.assertEqual(names, {"Alice", "Bob"})

        list_response = self.client.get(f"/api/topics/relation/{self.topic.uuid}/list")
        self.assertEqual(list_response.status_code, 200)
        list_data = list_response.json()
        self.assertEqual(list_data.get("total"), 2)

        # Delete one entity and ensure it no longer appears in the list
        entity_id = data["entities"][0]["id"]
        delete_response = self.client.delete(f"/api/topics/relation/{entity_id}")
        self.assertEqual(delete_response.status_code, 204)

        list_response = self.client.get(f"/api/topics/relation/{self.topic.uuid}/list")
        remaining = list_response.json().get("items", [])
        self.assertEqual(len(remaining), 1)
        self.assertNotEqual(remaining[0]["id"], entity_id)

        # Ensure the underlying relation is soft deleted
        self.assertTrue(RelatedEntity.objects.filter(id=entity_id, is_deleted=True).exists())

    def test_suggestions_replace_existing(self):
        self.client.force_login(self.user)
        Entity.objects.create(name="Existing", slug="existing")
        RelatedEntity.objects.create(topic=self.topic, entity=Entity.objects.first())

        with patch("semanticnews.topics.api._suggest_related_entities") as mock_suggest:
            mock_suggest.return_value = [
                RelatedEntityInput(name="Suggested", role="Analyst"),
            ]
            response = self.client.post(
                "/api/topics/relation/extract",
                data=json.dumps({"topic_uuid": str(self.topic.uuid)}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data.get("entities", [])), 1)
        self.assertEqual(data["entities"][0]["entity_name"], "Suggested")

        active_relations = RelatedEntity.objects.filter(topic=self.topic, is_deleted=False)
        self.assertEqual(active_relations.count(), 1)
        self.assertEqual(active_relations.first().entity.name, "Suggested")

    def test_repeated_updates_reuse_existing_relations(self):
        self.client.force_login(self.user)
        payload = {
            "topic_uuid": str(self.topic.uuid),
            "entities": [
                {"name": "Alice", "role": "Speaker"},
            ],
        }

        first_response = self.client.post(
            "/api/topics/relation/extract",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(first_response.status_code, 200)
        first_entity = first_response.json()["entities"][0]
        original_relation_id = first_entity["id"]

        updated_payload = {
            "topic_uuid": str(self.topic.uuid),
            "entities": [
                {"name": "Alice", "role": "Moderator"},
            ],
        }

        second_response = self.client.post(
            "/api/topics/relation/extract",
            data=json.dumps(updated_payload),
            content_type="application/json",
        )
        self.assertEqual(second_response.status_code, 200)
        second_entity = second_response.json()["entities"][0]
        self.assertEqual(second_entity["id"], original_relation_id)
        self.assertEqual(second_entity["role"], "Moderator")

        relations = RelatedEntity.objects.filter(topic=self.topic)
        self.assertEqual(relations.count(), 1)
        relation = relations.first()
        self.assertFalse(relation.is_deleted)
        self.assertEqual(relation.role, "Moderator")
