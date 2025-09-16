from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from semanticnews.topics.models import Topic

from .models import TopicDocument, TopicWebpage


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
