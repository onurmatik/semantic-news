from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import MagicMock, patch

from semanticnews.topics.models import Topic
from .models import MCPServer


class MCPContextAPITests(TestCase):
    """Tests for the MCP context API endpoint."""

    @patch("semanticnews.topics.utils.mcps.api.requests.post")
    def test_fetches_context(self, mock_post):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(user)

        topic = Topic.objects.create(title="My Topic", created_by=user)
        server = MCPServer.objects.create(name="Server", url="http://example.com", description="Desc")

        mock_response = MagicMock()
        mock_response.json.return_value = {"context": "Extra"}
        mock_post.return_value = mock_response

        payload = {"topic_uuid": str(topic.uuid), "server_id": server.id}
        response = self.client.post(
            "/api/topics/mcp/context", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"context": "Extra"})
        mock_post.assert_called_once_with(
            server.url,
            json={"topic": topic.title, "uuid": str(topic.uuid)},
            headers=server.headers,
        )

    def test_requires_authentication(self):
        User = get_user_model()
        user = User.objects.create_user("user", "user@example.com", "password")
        topic = Topic.objects.create(title="My Topic", created_by=user)
        server = MCPServer.objects.create(name="Server", url="http://example.com")

        payload = {"topic_uuid": str(topic.uuid), "server_id": server.id}
        response = self.client.post(
            "/api/topics/mcp/context", payload, content_type="application/json"
        )

        self.assertEqual(response.status_code, 401)
