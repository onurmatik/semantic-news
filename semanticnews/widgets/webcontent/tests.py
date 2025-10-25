"""Tests for the web content widget collection."""

from unittest.mock import MagicMock, patch
import requests

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from semanticnews.topics.models import Topic

from .models import (
    TopicDocument,
    TopicTweet,
    TopicWebpage,
    TopicYoutubeVideo,
)


class MockResponse:
    """Simple mock response for simulating ``requests.get`` calls."""

    def __init__(self, *, status_code=200, text="", headers=None, content_type="text/html; charset=utf-8"):
        self.status_code = status_code
        self._text = text
        self.headers = {"Content-Type": content_type}
        if headers:
            self.headers.update(headers)
        self.encoding = "utf-8"

    def iter_content(self, chunk_size=2048, decode_unicode=False):
        if decode_unicode:
            data = self._text
        else:
            data = self._text.encode(self.encoding)

        if not data:
            return

        for index in range(0, len(data), chunk_size):
            yield data[index : index + chunk_size]

    def close(self):  # pragma: no cover - included for API compatibility
        return None


def build_mock_html_response(title="Fetched Title", description="Fetched description") -> MockResponse:
    """Create a mocked HTML response containing metadata."""

    html = (
        "<html><head>"
        f"<title>{title}</title>"
        f"<meta name=\"description\" content=\"{description}\"/>"
        "</head><body></body></html>"
    )
    return MockResponse(text=html)


class TopicDocumentTests(TestCase):
    """Tests for the TopicDocument model."""

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    def test_document_type_is_inferred_from_url(self, _mock_embedding):
        user = get_user_model().objects.create_user('user', 'user@example.com', 'password')
        topic = Topic.objects.create(title='Test topic', created_by=user)

        link = TopicDocument.objects.create(
            topic=topic,
            url='https://example.com/files/report.PDF',
            title='Quarterly report',
        )

        self.assertEqual(link.document_type, 'pdf')

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    def test_unknown_extension_defaults_to_other(self, _mock_embedding):
        user = get_user_model().objects.create_user('user2', 'user2@example.com', 'password')
        topic = Topic.objects.create(title='Another topic', created_by=user)

        link = TopicDocument.objects.create(
            topic=topic,
            url='https://example.com/files/summary',
        )

        self.assertEqual(link.document_type, 'other')

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    def test_file_name_property_returns_url_basename(self, _mock_embedding):
        user = get_user_model().objects.create_user('user3', 'user3@example.com', 'password')
        topic = Topic.objects.create(title='Topic for filenames', created_by=user)

        link = TopicDocument.objects.create(
            topic=topic,
            url='https://example.com/documents/Annual%20Report.pdf',
            title='',
        )

        self.assertEqual(link.file_name, 'Annual Report.pdf')
        self.assertEqual(link.display_title, 'Annual Report.pdf')

        trailing = TopicDocument.objects.create(
            topic=topic,
            url='https://example.com/',
            title='',
        )

        self.assertEqual(trailing.file_name, 'example.com')
        self.assertEqual(trailing.display_title, 'example.com')


class TopicWebpageTests(TestCase):
    """Tests for the TopicWebpage model."""

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    def test_domain_property_returns_hostname(self, _mock_embedding):
        user = get_user_model().objects.create_user('viewer', 'viewer@example.com', 'password')
        topic = Topic.objects.create(title='Topic with webpage', created_by=user)

        link = TopicWebpage.objects.create(
            topic=topic,
            url='https://example.com/articles/interesting-story',
        )

        self.assertEqual(link.domain, 'example.com')


class TopicDocumentAPITests(TestCase):
    """API tests for creating, listing and deleting topic documents."""

    def setUp(self):
        super().setUp()
        self.embedding_patcher = patch(
            'semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536
        )
        self.embedding_patcher.start()
        self.addCleanup(self.embedding_patcher.stop)

        self.requests_patcher = patch('semanticnews.widgets.webcontent.api.requests.get')
        self.mock_requests_get = self.requests_patcher.start()
        self.addCleanup(self.requests_patcher.stop)
        self.mock_requests_get.return_value = build_mock_html_response()

        self.user = get_user_model().objects.create_user('docuser', 'doc@example.com', 'password')
        self.client.force_login(self.user)
        self.topic = Topic.objects.create(title='Doc Topic', created_by=self.user)

    def test_create_document(self):
        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/report.pdf',
            'title': 'Q1 Report',
            'description': 'Financial summary',
        }

        response = self.client.post(
            '/api/topics/document/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], 'Q1 Report')
        self.assertEqual(data['document_type'], 'pdf')
        self.assertEqual(data['domain'], 'example.com')
        self.assertEqual(TopicDocument.objects.count(), 1)
        document = TopicDocument.objects.first()
        self.assertEqual(document.created_by, self.user)

    def test_create_document_populates_metadata(self):
        self.mock_requests_get.return_value = build_mock_html_response(
            title='Fetched Document Title', description='Fetched document description'
        )

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/report.html',
        }

        response = self.client.post(
            '/api/topics/document/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], 'Fetched Document Title')
        self.assertEqual(data['description'], 'Fetched document description')

    def test_create_document_rejects_unreachable_url(self):
        self.mock_requests_get.side_effect = requests.RequestException('boom')

        try:
            payload = {
                'topic_uuid': str(self.topic.uuid),
                'url': 'https://example.com/missing-report',
            }

            response = self.client.post(
                '/api/topics/document/create', payload, content_type='application/json'
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['detail'], 'Unable to fetch URL')
        finally:
            self.mock_requests_get.side_effect = None
            self.mock_requests_get.return_value = build_mock_html_response()

    def test_create_document_requires_authentication(self):
        self.client.logout()
        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/report.pdf',
        }

        response = self.client.post(
            '/api/topics/document/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 401)

    def test_list_documents(self):
        TopicDocument.objects.create(
            topic=self.topic,
            url='https://example.com/one.pdf',
            title='One',
            description='First',
            created_by=self.user,
        )
        TopicDocument.objects.create(
            topic=self.topic,
            url='https://example.com/two.pdf',
            title='Two',
            description='Second',
            created_by=self.user,
        )

        response = self.client.get(
            f'/api/topics/document/{self.topic.uuid}/list'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 2)
        titles = [item['title'] for item in data['items']]
        self.assertEqual(titles, ['Two', 'One'])

    def test_delete_document(self):
        document = TopicDocument.objects.create(
            topic=self.topic,
            url='https://example.com/delete.pdf',
            title='Delete me',
            created_by=self.user,
        )

        response = self.client.delete(f'/api/topics/document/{document.id}')
        self.assertEqual(response.status_code, 204)
        document.refresh_from_db()
        self.assertTrue(document.is_deleted)


class TopicWebpageAPITests(TestCase):
    """API tests for creating, listing and deleting topic webpages."""

    def setUp(self):
        super().setUp()
        self.embedding_patcher = patch(
            'semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536
        )
        self.embedding_patcher.start()
        self.addCleanup(self.embedding_patcher.stop)

        self.requests_patcher = patch('semanticnews.widgets.webcontent.api.requests.get')
        self.mock_requests_get = self.requests_patcher.start()
        self.addCleanup(self.requests_patcher.stop)
        self.mock_requests_get.return_value = build_mock_html_response()

        self.user = get_user_model().objects.create_user('webuser', 'web@example.com', 'password')
        self.client.force_login(self.user)
        self.topic = Topic.objects.create(title='Web Topic', created_by=self.user)

    def test_create_webpage(self):
        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/story',
        }

        response = self.client.post(
            '/api/topics/document/webpage/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['domain'], 'example.com')
        self.assertEqual(TopicWebpage.objects.count(), 1)

    def test_list_webpages(self):
        TopicWebpage.objects.create(
            topic=self.topic,
            url='https://example.com/a',
            title='A',
            created_by=self.user,
        )
        TopicWebpage.objects.create(
            topic=self.topic,
            url='https://example.com/b',
            title='B',
            created_by=self.user,
        )

        response = self.client.get(
            f'/api/topics/document/webpage/{self.topic.uuid}/list'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 2)

    def test_delete_webpage(self):
        webpage = TopicWebpage.objects.create(
            topic=self.topic,
            url='https://example.com/delete',
            created_by=self.user,
        )

        response = self.client.delete(f'/api/topics/document/webpage/{webpage.id}')
        self.assertEqual(response.status_code, 204)
        webpage.refresh_from_db()
        self.assertTrue(webpage.is_deleted)


class TopicTweetAPITests(TestCase):
    """Tests for embedding tweets."""

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    @patch('semanticnews.widgets.webcontent.api.requests.get')
    def test_create_tweet_embed(self, mock_get, _mock_embedding):
        user = get_user_model().objects.create_user('user', 'user@example.com', 'password')
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
            '/api/topics/embed/tweet/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['tweet_id'], '1')
        self.assertEqual(data['html'], '<blockquote>tweet</blockquote>')
        self.assertEqual(TopicTweet.objects.count(), 1)

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    @patch('semanticnews.widgets.webcontent.api.requests.get')
    def test_prevents_duplicate_tweets(self, mock_get, _mock_embedding):
        user = get_user_model().objects.create_user('user', 'user@example.com', 'password')
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
        self.client.post(
            '/api/topics/embed/tweet/add', payload, content_type='application/json'
        )

        response = self.client.post(
            '/api/topics/embed/tweet/add', payload, content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(TopicTweet.objects.count(), 1)
        self.assertEqual(mock_get.call_count, 1)

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    def test_tweet_requires_authentication(self, _mock_embedding):
        user = get_user_model().objects.create_user('user', 'user@example.com', 'password')
        topic = Topic.objects.create(title='My Topic', created_by=user)

        payload = {
            'topic_uuid': str(topic.uuid),
            'url': 'https://twitter.com/test/status/1',
        }
        response = self.client.post(
            '/api/topics/embed/tweet/add', payload, content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)

    @patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536)
    @patch('semanticnews.widgets.webcontent.api.requests.get')
    def test_invalid_tweet_url(self, mock_get, _mock_embedding):
        user = get_user_model().objects.create_user('user', 'user@example.com', 'password')
        self.client.force_login(user)

        topic = Topic.objects.create(title='My Topic', created_by=user)

        payload = {
            'topic_uuid': str(topic.uuid),
            'url': 'https://example.com/not-a-tweet',
        }
        response = self.client.post(
            '/api/topics/embed/tweet/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        mock_get.assert_not_called()


class TopicVideoEmbedAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('alice', 'alice@example.com', 'pwd12345')
        self.client.force_login(self.user)
        with patch('semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536):
            self.topic = Topic.objects.create(title='Test Topic', created_by=self.user)

    @patch('semanticnews.widgets.webcontent.api.yt_dlp.YoutubeDL.extract_info')
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
            kwargs={'username': self.user.username, 'topic_uuid': str(self.topic.uuid)},
        )
        response = self.client.get(url)
        self.assertContains(response, 'youtube.com/embed/vid123')
