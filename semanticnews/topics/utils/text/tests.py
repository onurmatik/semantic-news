import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from semanticnews.topics.models import Topic, TopicModuleLayout
from semanticnews.prompting import get_default_language_instruction
from .models import TopicText


class TopicTextAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='alice', password='password')
        self.topic = Topic.objects.create(created_by=self.user, title='Sample Topic')
        self.client.force_login(self.user)

    def _post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_create_text_creates_layout_entry(self):
        response = self._post_json(
            '/api/topics/text/create',
            {'topic_uuid': str(self.topic.uuid), 'content': 'Hello world'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        text_id = data['id']

        text = TopicText.objects.get(id=text_id)
        self.assertEqual(text.content, 'Hello world')

        layout_key = f'text:{text_id}'
        self.assertTrue(
            TopicModuleLayout.objects.filter(topic=self.topic, module_key=layout_key).exists()
        )

    def test_delete_text_removes_layout_entry(self):
        text = TopicText.objects.create(topic=self.topic, content='To remove', status='finished')
        TopicModuleLayout.objects.create(
            topic=self.topic,
            module_key=f'text:{text.id}',
            placement=TopicModuleLayout.PLACEMENT_PRIMARY,
            display_order=1,
        )

        response = self.client.delete(f'/api/topics/text/{text.id}')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(TopicText.objects.filter(id=text.id).exists())
        self.assertFalse(
            TopicModuleLayout.objects.filter(topic=self.topic, module_key=f'text:{text.id}').exists()
        )

    @patch('semanticnews.topics.utils.text.api.OpenAI')
    def test_revise_text_returns_transformed_content(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(content='Improved text')
        mock_client.responses.parse.return_value = mock_response

        response = self._post_json(
            '/api/topics/text/revise',
            {'topic_uuid': str(self.topic.uuid), 'content': 'Original text'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'content': 'Improved text'})
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn('Original text', kwargs['input'])
        self.assertIn('Revise the text', kwargs['input'])
        self.assertIn('Sample Topic', kwargs['input'])
        self.assertIn(get_default_language_instruction(), kwargs['input'])

    @patch('semanticnews.topics.utils.text.api.OpenAI')
    def test_shorten_text_returns_transformed_content(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(content='Short version')
        mock_client.responses.parse.return_value = mock_response

        response = self._post_json(
            '/api/topics/text/shorten',
            {'topic_uuid': str(self.topic.uuid), 'content': 'Long detailed explanation'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'content': 'Short version'})
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn('Shorten the text', kwargs['input'])
        self.assertIn(get_default_language_instruction(), kwargs['input'])

    @patch('semanticnews.topics.utils.text.api.OpenAI')
    def test_expand_text_returns_transformed_content(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_parsed = MagicMock(content='Expanded version with detail')
        mock_client.responses.parse.return_value = mock_response

        response = self._post_json(
            '/api/topics/text/expand',
            {'topic_uuid': str(self.topic.uuid), 'content': 'Brief summary'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'content': 'Expanded version with detail'})
        mock_client.responses.parse.assert_called_once()
        _, kwargs = mock_client.responses.parse.call_args
        self.assertIn('Expand the text', kwargs['input'])
        self.assertIn(get_default_language_instruction(), kwargs['input'])

    def test_transform_requires_content(self):
        response = self._post_json(
            '/api/topics/text/revise',
            {'topic_uuid': str(self.topic.uuid), 'content': '   '},
        )

        self.assertEqual(response.status_code, 400)
