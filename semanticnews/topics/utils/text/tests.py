import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from semanticnews.topics.models import Topic, TopicModuleLayout
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
