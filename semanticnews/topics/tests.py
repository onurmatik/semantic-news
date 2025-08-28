from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from semanticnews.agenda.models import Event

from .models import Topic


class CreateTopicAPITests(TestCase):
    """Tests for the topic creation API endpoint."""

    def test_requires_authentication(self):
        """Unauthenticated requests should be rejected."""

        payload = {"title": "No Auth"}
        response = self.client.post(
            "/api/topics/create", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_creates_topic_for_user(self, mock_get_embedding):
        """Authenticated users can create topics."""

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        payload = {"title": "My Topic"}
        response = self.client.post(
            "/api/topics/create", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "My Topic")

        self.assertEqual(Topic.objects.count(), 1)
        topic = Topic.objects.first()
        self.assertEqual(topic.created_by, user)
        self.assertEqual(str(topic.uuid), data["uuid"])
        

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
        topic.events.add(related, through_defaults={"relevance": 0.5})

        suggested = Event.objects.create(title="Suggested", date="2024-01-02")

        response = self.client.get(topic.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertIn(related, response.context["related_events"])
        self.assertIn(suggested, response.context["suggested_events"])
        self.assertNotIn(related, response.context["suggested_events"])


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
        topic.events.add(event, through_defaults={"relevance": 0.5})

        url = reverse(
            "topics_remove_event",
            kwargs={"username": user.username, "slug": topic.slug, "event_uuid": event.uuid},
        )
        response = self.client.post(url)

        self.assertRedirects(response, topic.get_absolute_url())
        self.assertNotIn(event, topic.events.all())

