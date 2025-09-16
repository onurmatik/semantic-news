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
