from unittest.mock import MagicMock, patch
import json

from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model

from semanticnews.prompting import get_default_language_instruction
from .api import EventValidationResponse, AgendaEventList, AgendaEventResponse
from .models import Event


class ValidateEventTests(SimpleTestCase):
    @patch("semanticnews.agenda.api.OpenAI")
    def test_validate_event_returns_details(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.json = {
            "confidence": 0.91,
            "title": "Sample Event",
            "date": "2024-05-01",
            "sources": ["http://example.com"],
            "categories": ["Politics"],
        }
        mock_response.output = [MagicMock(content=[mock_content])]
        mock_response.output_parsed = mock_content.json
        mock_client.responses.parse.return_value = mock_response

        payload = {
            "title": "Sample Event",
            "date": "2024-05-01",
        }

        response = self.client.post(
            "/api/agenda/validate",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "confidence": 0.91,
                "title": "Sample Event",
                "date": "2024-05-01",
                "sources": ["http://example.com"],
                "categories": ["Politics"],
            },
        )

        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertEqual(kwargs["tools"], [{"type": "web_search_preview"}])
        self.assertEqual(
            kwargs["response_format"]["json_schema"]["schema"],
            EventValidationResponse.model_json_schema(),
        )
        self.assertIn(get_default_language_instruction(), kwargs["input"])


class SuggestEventsTests(SimpleTestCase):
    @patch("semanticnews.agenda.api.OpenAI")
    def test_suggest_events_returns_events(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_events = [
            {
                "title": "Event A",
                "date": "2024-06-01",
                "categories": ["Politics"],
                "sources": ["http://example.com/a"],
            },
            {
                "title": "Event B",
                "date": "2024-06-15",
                "categories": ["Economy", "Business"],
                "sources": ["http://example.com/b"],
            },
        ]
        mock_content.json = mock_events
        mock_response.output = [MagicMock(content=[mock_content])]
        mock_response.output_parsed = mock_events
        mock_client.responses.parse.return_value = mock_response

        response = self.client.get(
            "/api/agenda/suggest",
            {
                "start_date": "2024-06-01",
                "end_date": "2024-06-30",
                "locality": "USA",
                "limit": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_events)
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn(get_default_language_instruction(), kwargs["input"])

    @patch("semanticnews.agenda.api.OpenAI")
    def test_suggest_events_excludes_events(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_events = [
            {
                "title": "Event A",
                "date": "2024-06-01",
                "categories": ["Politics"],
                "sources": ["http://example.com/a"],
            },
            {
                "title": "Event B",
                "date": "2024-06-15",
                "categories": ["Economy"],
                "sources": ["http://example.com/b"],
            },
        ]
        mock_content.json = mock_events
        mock_response.output = [MagicMock(content=[mock_content])]
        mock_response.output_parsed = mock_events
        mock_client.responses.parse.return_value = mock_response

        exclude = json.dumps(
            [
                {
                    "title": "Event A",
                    "date": "2024-06-01",
                    "categories": ["Politics"],
                    "sources": ["http://example.com/a"],
                }
            ]
        )

        response = self.client.get(
            "/api/agenda/suggest",
            {
                "start_date": "2024-06-01",
                "end_date": "2024-06-30",
                "limit": 2,
                "exclude": exclude,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "title": "Event B",
                    "date": "2024-06-15",
                    "categories": ["Economy"],
                    "sources": ["http://example.com/b"],
                }
            ],
        )
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn("Do not include the following events", kwargs["input"])
        self.assertIn("Event A on 2024-06-01", kwargs["input"])
        self.assertIn(get_default_language_instruction(), kwargs["input"])

    @patch("semanticnews.agenda.api.OpenAI")
    def test_suggest_events_post_accepts_exclude_list(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_events = [
            {
                "title": "Event A",
                "date": "2024-06-01",
                "categories": ["Politics"],
                "sources": ["http://example.com/a"],
            },
            {
                "title": "Event B",
                "date": "2024-06-15",
                "categories": ["Economy"],
                "sources": ["http://example.com/b"],
            },
        ]
        mock_content.json = mock_events
        mock_response.output = [MagicMock(content=[mock_content])]
        mock_response.output_parsed = mock_events
        mock_client.responses.parse.return_value = mock_response

        payload = {
            "start_date": "2024-06-01",
            "end_date": "2024-06-30",
            "limit": 2,
            "exclude": [
                {"title": "Event A", "date": "2024-06-01", "categories": ["Politics"]}
            ],
        }

        response = self.client.post(
            "/api/agenda/suggest",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "title": "Event B",
                    "date": "2024-06-15",
                    "categories": ["Economy"],
                    "sources": ["http://example.com/b"],
                }
            ],
        )
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn("Do not include the following events", kwargs["input"])
        self.assertIn("Event A on 2024-06-01", kwargs["input"])

    @patch("semanticnews.agenda.api.OpenAI")
    def test_suggest_events_with_related_event(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_events = [
            {
                "title": "Related Event",
                "date": "2024-07-01",
                "categories": ["Sports"],
                "sources": ["http://example.com/related"],
            }
        ]
        mock_content.json = mock_events
        mock_response.output = [MagicMock(content=[mock_content])]
        mock_response.output_parsed = mock_events
        mock_client.responses.parse.return_value = mock_response

        response = self.client.get(
            "/api/agenda/suggest",
            {"related_event": "2024 Olympics", "limit": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_events)
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn("related to 2024 Olympics", kwargs["input"])


class GetExistingTests(TestCase):
    @patch("semanticnews.agenda.api.OpenAI")
    def test_returns_existing_uuid(self, mock_openai):
        from datetime import date
        from .models import Event

        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )

        event = Event.objects.create(
            title="Existing Event",
            date=date(2024, 1, 1),
            embedding=[0.1] * 1536,
        )

        response = self.client.post(
            "/api/agenda/get-existing",
            {"title": "Existing Event", "date": "2024-01-01"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"existing": str(event.uuid)})

    @patch("semanticnews.agenda.api.OpenAI")
    def test_returns_null_when_missing(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )

        response = self.client.post(
            "/api/agenda/get-existing",
            {"title": "Unknown", "date": "2024-01-01"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"existing": None})


class CreateEventTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client.force_login(self.user)

    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_create_event_endpoint_creates_event(self, mock_get_embedding):
        payload = {
            "title": "My Event",
            "date": "2024-01-02",
            "confidence": 0.85,
            "sources": ["http://example.com/source"],
            "categories": ["Politics"],
        }
        response = self.client.post(
            "/api/agenda/create", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "My Event")
        self.assertEqual(data["date"], "2024-01-02")
        self.assertEqual(data["confidence"], 0.85)

        from .models import Event, Source, Category

        self.assertEqual(Event.objects.count(), 1)
        event = Event.objects.first()
        self.assertEqual(data["url"], event.get_absolute_url())
        self.assertEqual(event.confidence, 0.85)
        self.assertEqual(event.status, "published")
        self.assertEqual(event.sources.count(), 1)
        self.assertEqual(event.sources.first().url, "http://example.com/source")
        self.assertEqual(event.categories.count(), 1)
        self.assertEqual(event.categories.first().name, "Politics")
        self.assertIsNotNone(event.embedding)

    @patch("semanticnews.agenda.models.Event.get_embedding", return_value=[0.0] * 1536)
    def test_low_confidence_creates_draft_event(self, mock_get_embedding):
        payload = {"title": "Low Confidence", "date": "2024-01-03", "confidence": 0.5}
        response = self.client.post(
            "/api/agenda/create", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        from .models import Event

        self.assertEqual(Event.objects.count(), 1)
        event = Event.objects.first()
        self.assertEqual(event.status, "draft")


class PublishEventTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="publisher", password="pass")
        self.client.force_login(self.user)

    def test_publish_endpoint_sets_status(self):
        from datetime import date
        from .models import Event

        event = Event.objects.create(
            title="Draft Event",
            date=date(2024, 1, 1),
            status="draft",
            embedding=[0.0] * 1536,
        )

        payload = {"uuids": [str(event.uuid)]}
        response = self.client.post(
            "/api/agenda/publish", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, "published")


class SuggestViewAdminTests(TestCase):
    @patch("semanticnews.agenda.admin.suggest_events")
    def test_admin_suggest_view_creates_categories(self, mock_suggest):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        from datetime import date
        from .models import Event, Locality

        mock_suggest.return_value = AgendaEventList(
            event_list=[
                AgendaEventResponse(
                    title="Event A",
                    date=date(2024, 6, 1),
                    categories=["Politics", "Economy"],
                )
            ]
        )

        User = get_user_model()
        user = User.objects.create_superuser("admin", "a@example.com", "password")
        self.client.force_login(user)

        locality = Locality.objects.create(name="USA")

        response = self.client.post(
            reverse("admin:agenda_event_suggest"),
            {
                "start_date": "2024-06-01",
                "end_date": "2024-06-30",
                "locality": locality.id,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Event.objects.count(), 1)
        event = Event.objects.first()
        self.assertEqual(
            set(event.categories.values_list("name", flat=True)),
            {"Politics", "Economy"},
        )


class EventDetailTopicTests(TestCase):
    def test_event_detail_shows_topics(self):
        from datetime import date
        from semanticnews.topics.models import Topic
        from semanticnews.topics.utils.timeline.models import TopicEvent

        event = Event.objects.create(
            title="My Event",
            date=date(2024, 1, 1),
            embedding=[0.0] * 1536,
        )
        topic1 = Topic.objects.create(title="Topic One", embedding=[0.0] * 1536)
        topic2 = Topic.objects.create(title="Topic Two", embedding=[0.0] * 1536)
        TopicEvent.objects.create(topic=topic1, event=event)
        TopicEvent.objects.create(topic=topic2, event=event)

        response = self.client.get(event.get_absolute_url())

        self.assertContains(response, "Topic One")
        self.assertContains(response, "Topic Two")


class EventDetailLocalityTests(TestCase):
    def test_locality_select_lists_localities(self):
        from datetime import date
        from .models import Locality, Event

        event = Event.objects.create(
            title="My Event",
            date=date(2024, 1, 1),
            embedding=[0.0] * 1536,
        )
        default_loc = Locality.objects.create(name="USA", is_default=True)
        other_loc = Locality.objects.create(name="France")

        response = self.client.get(event.get_absolute_url())

        self.assertContains(response, '<option value="">Global</option>', html=True)
        content = response.content.decode()
        self.assertLess(content.index(default_loc.name), content.index(other_loc.name))


class EventManagerTests(TestCase):
    """Tests for the :class:`EventManager` semantic get_or_create method."""

    def test_semantic_get_or_create_returns_existing_event(self):
        from datetime import date

        existing = Event.objects.create(
            title="Existing", date=date(2024, 1, 1), embedding=[0.0] * 1536
        )

        obj, created = Event.objects.get_or_create_semantic(
            date=existing.date,
            embedding=[0.0] * 1536,
            defaults={"title": "New"},
        )

        self.assertFalse(created)
        self.assertEqual(obj.id, existing.id)

    def test_semantic_get_or_create_creates_new_event(self):
        from datetime import date

        Event.objects.create(
            title="Existing", date=date(2024, 1, 1), embedding=[0.0] * 1536
        )

        obj, created = Event.objects.get_or_create_semantic(
            date=date(2024, 1, 1),
            embedding=[1.0] * 1536,
            defaults={"title": "Different"},
        )

        self.assertTrue(created)
        self.assertEqual(obj.title, "Different")
