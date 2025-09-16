from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from semanticnews.topics.models import Topic
from .models import TopicSocialEmbed, TopicYoutubeVideo


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


class TopicVideoEmbedAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('alice', 'alice@example.com', 'pwd12345')
        self.client.force_login(self.user)
        with patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536):
            self.topic = Topic.objects.create(title='Test Topic', created_by=self.user)

    @patch('semanticnews.topics.utils.embeds.api.yt_dlp.YoutubeDL.extract_info')
    def test_add_video_embed(self, mock_extract_info):
        mock_extract_info.return_value = {
            'title': 'Sample Title',
            'description': 'Sample description',
            'thumbnail': 'http://example.com/thumb.jpg',
            'timestamp': 1609459200,
        }

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://youtu.be/dQw4w9WgXcQ',
        }
        response = self.client.post(
            '/api/topics/embed/video/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TopicYoutubeVideo.objects.count(), 1)
        media = TopicYoutubeVideo.objects.first()
        self.assertEqual(media.url, payload['url'])
        self.assertEqual(media.video_id, 'dQw4w9WgXcQ')
        self.assertEqual(media.title, 'Sample Title')
        self.assertEqual(media.description, 'Sample description')
        self.assertEqual(media.thumbnail, 'http://example.com/thumb.jpg')
        self.assertEqual(media.published_at.year, 2021)
        self.assertEqual(media.status, 'finished')

    def test_video_requires_authentication(self):
        self.client.logout()
        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://youtu.be/dQw4w9WgXcQ',
        }
        response = self.client.post(
            '/api/topics/embed/video/add', payload, content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)


class TopicVideoEmbedDisplayTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('bob', 'bob@example.com', 'pwd12345')
        with patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536):
            self.topic = Topic.objects.create(title='Display', created_by=self.user)
        TopicYoutubeVideo.objects.create(
            topic=self.topic,
            url='https://youtu.be/vid123',
            video_id='vid123',
            title='Video',
            description='',
            thumbnail='',
            published_at=timezone.now(),
            status='finished',
        )

    def test_detail_displays_video(self):
        response = self.client.get(self.topic.get_absolute_url())
        self.assertContains(response, 'youtube.com/embed/vid123')

    def test_edit_displays_video(self):
        self.client.force_login(self.user)
        url = reverse(
            'topics_detail_edit',
            kwargs={'username': self.user.username, 'slug': self.topic.slug},
        )
        response = self.client.get(url)
        self.assertContains(response, 'youtube.com/embed/vid123')
