import json
from datetime import datetime
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from semanticnews.topics.models import Topic

from .models import TopicDocument, TopicTweet, TopicWebpage, TopicYoutubeVideo


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

    def json(self):  # pragma: no cover - exercised indirectly
        return json.loads(self._text or '{}')

    def raise_for_status(self):  # pragma: no cover - exercised indirectly
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


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
            '/api/topics/webcontent/document/create', payload, content_type='application/json'
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
            '/api/topics/webcontent/document/create', payload, content_type='application/json'
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
                '/api/topics/webcontent/document/create', payload, content_type='application/json'
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
            '/api/topics/webcontent/document/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 401)

    def test_list_documents(self):
        TopicDocument.objects.create(topic=self.topic, url='https://example.com/a', created_by=self.user)
        TopicDocument.objects.create(topic=self.topic, url='https://example.com/b', created_by=self.user)

        response = self.client.get(f'/api/topics/webcontent/document/{self.topic.uuid}/list')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 2)

    def test_list_documents_uses_file_name_when_title_missing(self):
        TopicDocument.objects.create(topic=self.topic, url='https://example.com/a', title='', created_by=self.user)

        response = self.client.get(f'/api/topics/webcontent/document/{self.topic.uuid}/list')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'][0]['title'], 'example.com')

    def test_delete_document_marks_flag(self):
        document = TopicDocument.objects.create(topic=self.topic, url='https://example.com/a', created_by=self.user)

        response = self.client.delete(f'/api/topics/webcontent/document/{document.id}')
        self.assertEqual(response.status_code, 204)
        document.refresh_from_db()
        self.assertTrue(document.is_deleted)

    def test_create_webpage(self):
        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/article',
            'title': 'News article',
            'description': 'Long-form story',
        }

        response = self.client.post(
            '/api/topics/webcontent/webpage/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'News article')

    def test_create_webpage_populates_metadata(self):
        self.mock_requests_get.return_value = build_mock_html_response(
            title='Fetched Webpage Title', description='Fetched webpage description'
        )

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/article',
        }

        response = self.client.post(
            '/api/topics/webcontent/webpage/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'Fetched Webpage Title')
        self.assertEqual(response.json()['description'], 'Fetched webpage description')

    def test_create_webpage_rejects_unreachable_url(self):
        self.mock_requests_get.side_effect = requests.RequestException('boom')

        try:
            payload = {
                'topic_uuid': str(self.topic.uuid),
                'url': 'https://example.com/missing-report',
            }

            response = self.client.post(
                '/api/topics/webcontent/webpage/create', payload, content_type='application/json'
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['detail'], 'Unable to fetch URL')
        finally:
            self.mock_requests_get.side_effect = None
            self.mock_requests_get.return_value = build_mock_html_response()

    def test_list_webpages(self):
        TopicWebpage.objects.create(topic=self.topic, url='https://example.com/article', created_by=self.user)

        response = self.client.get(f'/api/topics/webcontent/webpage/{self.topic.uuid}/list')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 1)

    def test_delete_webpage_marks_flag(self):
        webpage = TopicWebpage.objects.create(topic=self.topic, url='https://example.com/article', created_by=self.user)

        response = self.client.delete(f'/api/topics/webcontent/webpage/{webpage.id}')
        self.assertEqual(response.status_code, 204)
        webpage.refresh_from_db()
        self.assertTrue(webpage.is_deleted)


class TopicEmbedAPITests(TestCase):
    """API tests for tweet and video embeds."""

    def setUp(self):
        super().setUp()
        self.embedding_patcher = patch(
            'semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536
        )
        self.embedding_patcher.start()
        self.addCleanup(self.embedding_patcher.stop)

        self.user = get_user_model().objects.create_user('embedder', 'embed@example.com', 'password')
        self.client.force_login(self.user)
        self.topic = Topic.objects.create(title='Embed Topic', created_by=self.user)

    @patch('semanticnews.widgets.webcontent.api.requests.get')
    def test_add_tweet_embed(self, mock_get):
        mock_get.return_value = MockResponse(content_type='application/json', text='{"html": "<p>Tweet</p>"}')

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://twitter.com/user/status/1234567890',
        }

        response = self.client.post(
            '/api/topics/webcontent/tweet/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['tweet_id'], '1234567890')
        self.assertEqual(TopicTweet.objects.count(), 1)

    @patch('semanticnews.widgets.webcontent.api.requests.get')
    def test_add_tweet_embed_rejects_duplicate(self, mock_get):
        mock_get.return_value = MockResponse(content_type='application/json', text='{"html": "<p>Tweet</p>"}')
        TopicTweet.objects.create(
            topic=self.topic,
            tweet_id='1234567890',
            url='https://twitter.com/user/status/1234567890',
            html='<p>Tweet</p>',
        )

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://twitter.com/user/status/1234567890',
        }

        response = self.client.post(
            '/api/topics/webcontent/tweet/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], 'Tweet already added')

    @patch('semanticnews.widgets.webcontent.api.requests.get')
    def test_add_tweet_embed_requires_valid_url(self, mock_get):
        mock_get.return_value = MockResponse(content_type='application/json', text='{"html": "<p>Tweet</p>"}')

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/not-a-tweet',
        }

        response = self.client.post(
            '/api/topics/webcontent/tweet/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], 'Invalid tweet URL')

    @patch('semanticnews.widgets.webcontent.api.requests.get')
    def test_add_tweet_embed_requires_authentication(self, mock_get):
        mock_get.return_value = MockResponse(content_type='application/json', text='{"html": "<p>Tweet</p>"}')
        self.client.logout()

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://twitter.com/user/status/1234567890',
        }

        response = self.client.post(
            '/api/topics/webcontent/tweet/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 401)

    @patch('semanticnews.widgets.webcontent.api.yt_dlp.YoutubeDL.extract_info')
    def test_add_video_embed(self, mock_extract_info):
        mock_extract_info.return_value = {
            'title': 'Video Title',
            'description': 'Video description',
            'thumbnail': 'https://example.com/thumb.jpg',
            'timestamp': int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp()),
        }

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        }

        response = self.client.post(
            '/api/topics/webcontent/video/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['video_id'], 'dQw4w9WgXcQ')
        self.assertEqual(TopicYoutubeVideo.objects.count(), 1)

    @patch('semanticnews.widgets.webcontent.api.yt_dlp.YoutubeDL.extract_info')
    def test_add_video_embed_rejects_invalid_url(self, mock_extract_info):
        mock_extract_info.return_value = {}

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/video',
        }

        response = self.client.post(
            '/api/topics/webcontent/video/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], 'Invalid YouTube URL')

    @patch('semanticnews.widgets.webcontent.api.yt_dlp.YoutubeDL.extract_info')
    def test_add_video_embed_requires_authentication(self, mock_extract_info):
        mock_extract_info.return_value = {}
        self.client.logout()

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        }

        response = self.client.post(
            '/api/topics/webcontent/video/add', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 401)
