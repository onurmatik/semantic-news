from unittest.mock import patch, AsyncMock, MagicMock
from datetime import timedelta
from types import SimpleNamespace
import tempfile
import shutil

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from semanticnews.agenda.models import Event
from semanticnews.contents.models import Content

from .models import Topic, TopicEvent, TopicContent
from .utils.recaps.models import TopicRecap
from .utils.images.models import TopicImage
from .utils.keywords.models import Keyword, TopicKeyword
from .utils.mcps.models import MCPServer


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

        payload = {"topic_uuid": str(topic.uuid), "status": "published"}
        response = self.client.post(
            "/api/topics/set-status", payload, content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        topic.refresh_from_db()
        self.assertEqual(topic.status, "published")

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

    @patch("semanticnews.topics.utils.recaps.api.OpenAI")
    @patch(
        "semanticnews.topics.models.Topic.get_embedding",
        return_value=[0.0] * 1536,
    )
    def test_accepts_optional_length_and_instructions(
        self, mock_topic_embedding, mock_openai
    ):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = {"recap_en": "Recap"}
        mock_client.responses.parse.return_value = mock_response

        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)

        payload = {
            "topic_uuid": str(topic.uuid),
            "websearch": True,
            "length": "short",
            "instructions": "Extra details",
        }
        response = self.client.post(
            "/api/topics/recap/create", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"recap": "Recap"})
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertEqual(kwargs["tools"], [{"type": "web_search_preview"}])
        self.assertIn("Write a short recap.", kwargs["input"])
        self.assertIn("Extra details", kwargs["input"])


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
        TopicEvent.objects.create(topic=self.topic, event=self.event, created_by=self.owner)

        self.content = Content.objects.create(content_type="text", embedding=[0.0] * 1536)
        TopicContent.objects.create(topic=self.topic, content=self.content, created_by=self.owner)

        TopicRecap.objects.create(topic=self.topic, recap="Recap")

        image_data = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
            b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02L\x01\x00;"
        )
        image_file = SimpleUploadedFile("image.gif", image_data, content_type="image/gif")
        TopicImage.objects.create(topic=self.topic, image=image_file)

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
        self.assertEqual(cloned.contents.count(), 1)
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

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_updated_at_changes_when_recap_added(self, mock_topic_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        start = timezone.now()
        later = start + timedelta(days=1)

        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = start
            topic = Topic.objects.create(title="My Topic", created_by=user)
            initial = topic.updated_at

            mock_now.return_value = later
            TopicRecap.objects.create(topic=topic, recap="A recap")

            topic.refresh_from_db()
            self.assertNotEqual(initial, topic.updated_at)
            self.assertEqual(topic.updated_at, later)

    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_updated_at_changes_when_image_added(self, mock_topic_embedding):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")

        start = timezone.now()
        later = start + timedelta(days=1)

        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = start
            topic = Topic.objects.create(title="My Topic", created_by=user)
            initial = topic.updated_at

            mock_now.return_value = later
            image_bytes = (
                b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
                b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            )
            TopicImage.objects.create(
                topic=topic,
                image=SimpleUploadedFile("test.gif", image_bytes, content_type="image/gif"),
            )

            topic.refresh_from_db()
            self.assertNotEqual(initial, topic.updated_at)
            self.assertEqual(topic.updated_at, later)

