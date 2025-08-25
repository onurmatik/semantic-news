from unittest.mock import MagicMock, patch
import json

from django.test import SimpleTestCase, TestCase

from .api import EventValidationResponse


class ValidateEventTests(SimpleTestCase):
    @patch("semanticnews.agenda.api.OpenAI")
    def test_validate_event_returns_confidence(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.json = {"confidence": 0.91}
        mock_response.output = [MagicMock(content=[mock_content])]
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
        self.assertEqual(response.json(), {"confidence": 0.91})

        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertEqual(kwargs["tools"], [{"type": "web_search_preview"}])
        self.assertEqual(
            kwargs["response_format"]["json_schema"]["schema"],
            EventValidationResponse.model_json_schema(),
        )


class SuggestEventsTests(SimpleTestCase):
    @patch("semanticnews.agenda.api.OpenAI")
    def test_suggest_events_returns_events(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_events = [
            {"title": "Event A", "date": "2024-06-01"},
            {"title": "Event B", "date": "2024-06-15"},
        ]
        mock_content.json = mock_events
        mock_response.output = [MagicMock(content=[mock_content])]
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

    @patch("semanticnews.agenda.api.OpenAI")
    def test_suggest_events_excludes_events(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_events = [
            {"title": "Event A", "date": "2024-06-01"},
            {"title": "Event B", "date": "2024-06-15"},
        ]
        mock_content.json = mock_events
        mock_response.output = [MagicMock(content=[mock_content])]
        mock_client.responses.parse.return_value = mock_response

        exclude = json.dumps([
            {"title": "Event A", "date": "2024-06-01"}
        ])

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
            [{"title": "Event B", "date": "2024-06-15"}],
        )
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn("Do not include the following events", kwargs["input"])
        self.assertIn("Event A on 2024-06-01", kwargs["input"])


class CreateEventTests(TestCase):
    def test_create_event_endpoint_creates_event(self):
        payload = {"title": "My Event", "date": "2024-01-02", "confidence": 0.85}
        response = self.client.post(
            "/api/agenda/create", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "My Event")
        self.assertEqual(data["date"], "2024-01-02")
        self.assertEqual(data["confidence"], 0.85)

        from .models import Event

        self.assertEqual(Event.objects.count(), 1)
        event = Event.objects.first()
        self.assertEqual(data["url"], event.get_absolute_url())
        self.assertEqual(event.confidence, 0.85)
        self.assertEqual(event.status, "published")

    def test_low_confidence_creates_draft_event(self):
        payload = {"title": "Low Confidence", "date": "2024-01-03", "confidence": 0.5}
        response = self.client.post(
            "/api/agenda/create", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        from .models import Event

        self.assertEqual(Event.objects.count(), 1)
        event = Event.objects.first()
        self.assertEqual(event.status, "draft")
