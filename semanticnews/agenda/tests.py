from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

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
        mock_client.responses.create.return_value = mock_response

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

        mock_client.responses.create.assert_called_once()
        _, kwargs = mock_client.responses.create.call_args
        self.assertEqual(kwargs["tools"], [{"type": "web_search"}])
        self.assertEqual(
            kwargs["response_format"]["json_schema"]["schema"],
            EventValidationResponse.model_json_schema(),
        )
