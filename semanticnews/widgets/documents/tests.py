from unittest.mock import patch

import requests

from django.contrib.auth import get_user_model
from django.test import TestCase

from semanticnews.topics.models import Topic

from .models import TopicDocument, TopicWebpage


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

        self.requests_patcher = patch('semanticnews.widgets.documents.api.requests.get')
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
            url='https://example.com/report.pdf',
            title='Report',
            description='',
            created_by=self.user,
        )
        TopicDocument.objects.create(
            topic=self.topic,
            url='https://example.com/brief.docx',
            title='Brief',
            description='',
            created_by=self.user,
        )

        response = self.client.get(f'/api/topics/document/{self.topic.uuid}/list')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 2)
        urls = {item['url'] for item in data['items']}
        self.assertEqual(urls, {'https://example.com/report.pdf', 'https://example.com/brief.docx'})

    def test_list_documents_uses_file_name_when_title_missing(self):
        TopicDocument.objects.create(
            topic=self.topic,
            url='https://example.com/files/report-final.pdf',
            title='',
            created_by=self.user,
        )

        response = self.client.get(f'/api/topics/document/{self.topic.uuid}/list')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['items'][0]['title'], 'report-final.pdf')

    def test_delete_document(self):
        document = TopicDocument.objects.create(
            topic=self.topic,
            url='https://example.com/report.pdf',
            title='Report',
            created_by=self.user,
        )

        response = self.client.delete(f'/api/topics/document/{document.id}')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(TopicDocument.objects.filter(id=document.id).exists())


class TopicWebpageAPITests(TestCase):
    """API tests for creating, listing and deleting topic webpages."""

    def setUp(self):
        super().setUp()
        self.embedding_patcher = patch(
            'semanticnews.topics.models.Topic.get_embedding', return_value=[0.0] * 1536
        )
        self.embedding_patcher.start()
        self.addCleanup(self.embedding_patcher.stop)

        self.requests_patcher = patch('semanticnews.widgets.documents.api.requests.get')
        self.mock_requests_get = self.requests_patcher.start()
        self.addCleanup(self.requests_patcher.stop)
        self.mock_requests_get.return_value = build_mock_html_response()

        self.user = get_user_model().objects.create_user('webuser', 'web@example.com', 'password')
        self.client.force_login(self.user)
        self.topic = Topic.objects.create(title='Web Topic', created_by=self.user)

    def test_create_webpage(self):
        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/article',
            'title': 'Interesting article',
        }

        response = self.client.post(
            '/api/topics/document/webpage/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], 'Interesting article')
        self.assertEqual(data['domain'], 'example.com')
        self.assertEqual(TopicWebpage.objects.count(), 1)

    def test_create_webpage_populates_metadata(self):
        self.mock_requests_get.return_value = build_mock_html_response(
            title='Fetched Webpage Title', description='Fetched webpage description'
        )

        payload = {
            'topic_uuid': str(self.topic.uuid),
            'url': 'https://example.com/another-article',
        }

        response = self.client.post(
            '/api/topics/document/webpage/create', payload, content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], 'Fetched Webpage Title')
        self.assertEqual(data['description'], 'Fetched webpage description')

    def test_create_webpage_rejects_unreachable_url(self):
        self.mock_requests_get.side_effect = requests.RequestException('boom')

        try:
            payload = {
                'topic_uuid': str(self.topic.uuid),
                'url': 'https://example.com/missing-page',
            }

            response = self.client.post(
                '/api/topics/document/webpage/create', payload, content_type='application/json'
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['detail'], 'Unable to fetch URL')
        finally:
            self.mock_requests_get.side_effect = None
            self.mock_requests_get.return_value = build_mock_html_response()

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

        response = self.client.get(f'/api/topics/document/webpage/{self.topic.uuid}/list')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 2)
        titles = {item['title'] for item in data['items']}
        self.assertEqual(titles, {'A', 'B'})

    def test_delete_webpage(self):
        webpage = TopicWebpage.objects.create(
            topic=self.topic,
            url='https://example.com/a',
            title='A',
            created_by=self.user,
        )

        response = self.client.delete(f'/api/topics/document/webpage/{webpage.id}')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(TopicWebpage.objects.filter(id=webpage.id).exists())
