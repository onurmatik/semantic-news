from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import MagicMock, patch

from semanticnews.topics.models import Topic
from .models import TopicSocialEmbed


class SocialEmbedAPITests(TestCase):
    """Tests for embedding social media posts."""

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    @patch('semanticnews.topics.utils.embeds.api.requests.get')
    def test_create_tweet_embed(self, mock_get, mock_embedding):
        User = get_user_model()
        user = User.objects.create_user('user', 'user@example.com', 'password')
        self.client.force_login(user)

        topic = Topic.objects.create(title='My Topic', created_by=user)

        mock_response = MagicMock()
        mock_response.json.return_value = {'html': '<blockquote>tweet</blockquote>'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        payload = {
            'topic_uuid': str(topic.uuid),
            'url': 'https://twitter.com/test/status/1',
        }
        response = self.client.post(
            '/api/topics/embed/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['provider'], 'twitter')
        self.assertEqual(data['html'], '<blockquote>tweet</blockquote>')
        self.assertEqual(TopicSocialEmbed.objects.count(), 1)

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    def test_requires_authentication(self, mock_embedding):
        User = get_user_model()
        user = User.objects.create_user('user', 'user@example.com', 'password')
        topic = Topic.objects.create(title='My Topic', created_by=user)

        payload = {
            'topic_uuid': str(topic.uuid),
            'url': 'https://twitter.com/test/status/1',
        }
        response = self.client.post(
            '/api/topics/embed/create', payload, content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
