from unittest.mock import patch
from datetime import timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from semanticnews.agenda.models import Event
from semanticnews.contents.models import Content

from .models import Topic
from .utils.recaps.models import TopicRecap


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
        topic.events.add(event, through_defaults={"created_by": user})

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
        topic.events.add(event, through_defaults={"created_by": user})

        payload = {"topic_uuid": str(topic.uuid), "event_uuid": str(event.uuid)}
        response = self.client.post(
            "/api/topics/remove-event", payload, content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(topic.events.count(), 0)


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

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_event_buttons_visible_only_to_owner(self, mock_event_embedding, mock_topic_embedding):
        """Add/remove buttons are shown only for events created by the requesting user."""

        User = get_user_model()
        owner = User.objects.create_user("owner", "owner@example.com", "password")
        other = User.objects.create_user("other", "other@example.com", "password")
        self.client.force_login(owner)

        topic = Topic.objects.create(title="My Topic", created_by=owner)

        related_owned = Event.objects.create(title="Rel Owned", date="2024-01-01", created_by=owner)
        related_other = Event.objects.create(title="Rel Other", date="2024-01-02", created_by=other)
        topic.events.add(related_owned, through_defaults={"relevance": 0.5})
        topic.events.add(related_other, through_defaults={"relevance": 0.5})

        suggested_owned = Event.objects.create(title="Sug Owned", date="2024-02-01", created_by=owner)
        suggested_other = Event.objects.create(title="Sug Other", date="2024-02-02", created_by=other)

        response = self.client.get(topic.get_absolute_url())
        content = response.content.decode()

        self.assertRegex(
            content,
            rf'(?s)<button[^>]*class="[^"]*remove-event-btn[^"]*"[^>]*data-event-uuid="{related_owned.uuid}"',
        )
        self.assertNotRegex(
            content,
            rf'(?s)<button[^>]*class="[^"]*remove-event-btn[^"]*"[^>]*data-event-uuid="{related_other.uuid}"',
        )
        self.assertRegex(
            content,
            rf'(?s)<button[^>]*class="[^"]*add-event-btn[^"]*"[^>]*data-event-uuid="{suggested_owned.uuid}"',
        )
        self.assertNotRegex(
            content,
            rf'(?s)<button[^>]*class="[^"]*add-event-btn[^"]*"[^>]*data-event-uuid="{suggested_other.uuid}"',
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


class TopicUpdatedAtTests(TestCase):
    """Tests that topic.updated_at changes when related items change."""

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_updated_at_changes_when_event_added(self, mock_event_embedding, mock_topic_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        start = timezone.now()
        later = start + timedelta(days=1)

        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = start
            topic = Topic.objects.create(title="My Topic", created_by=user)
            initial = topic.updated_at

            event = Event.objects.create(title="An Event", date="2024-01-01")
            mock_now.return_value = later
            topic.events.add(event, through_defaults={"created_by": user})

            topic.refresh_from_db()
            self.assertNotEqual(initial, topic.updated_at)
            self.assertEqual(topic.updated_at, later)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_updated_at_changes_when_content_added(self, mock_topic_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        start = timezone.now()
        later = start + timedelta(days=1)

        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = start
            topic = Topic.objects.create(title="My Topic", created_by=user)
            initial = topic.updated_at

            content = Content.objects.create(url="https://example.com/a", content_type="article")
            mock_now.return_value = later
            topic.contents.add(content, through_defaults={"created_by": user})

            topic.refresh_from_db()
            self.assertNotEqual(initial, topic.updated_at)
            self.assertEqual(topic.updated_at, later)

