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

from .models import Topic, TopicEvent, TopicContent, TopicKeyword
from semanticnews.keywords.models import Keyword
from .utils.recaps.models import TopicRecap
from .utils.images.models import TopicImage
from .utils.mcps.models import MCPServer
from .utils.data.models import TopicData, TopicDataInsight


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
    def test_returns_ai_suggestion_without_saving(
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
        self.assertEqual(TopicRecap.objects.count(), 0)

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


class AnalyzeDataAPITests(TestCase):
    """Tests for the data analysis API endpoint."""

    @patch("semanticnews.topics.utils.data.api.OpenAI")
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

    @patch("semanticnews.topics.utils.data.api.OpenAI")
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
    def test_related_event_buttons_depends_on_topic_owner(self, mock_event_embedding, mock_topic_embedding):
        """Topic owners can remove related events; others can add them to their topics."""

        User = get_user_model()
        owner = User.objects.create_user("owner", "owner@example.com", "password")
        other = User.objects.create_user("other", "other@example.com", "password")

        topic = Topic.objects.create(title="My Topic", created_by=owner)
        other_topic = Topic.objects.create(title="Other Topic", created_by=other)

        related = Event.objects.create(title="Rel Event", date="2024-01-01", created_by=other)
        topic.events.add(related, through_defaults={"relevance": 0.5})

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
        topic.events.add(event, through_defaults={"created_by": user})

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

