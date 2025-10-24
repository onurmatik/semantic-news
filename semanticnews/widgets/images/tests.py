from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from unittest.mock import patch

from semanticnews.topics.models import Topic
from semanticnews.widgets.images.models import TopicImage


class TopicImageAPITests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            'owner', 'owner@example.com', 'password'
        )
        self.embedding_patcher = patch(
            'semanticnews.topics.models.Topic.get_embedding',
            return_value=[0.0] * 1536,
        )
        self.embedding_patcher.start()
        self.addCleanup(self.embedding_patcher.stop)

        self.topic = Topic.objects.create(title='Test topic', created_by=self.user)
        self.client.force_login(self.user)
        self.image_bytes = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )

    def _create_image(self, **overrides):
        defaults = {
            'image': SimpleUploadedFile('test.gif', self.image_bytes, content_type='image/gif'),
            'status': 'finished',
            'is_hero': False,
        }
        defaults.update(overrides)
        return TopicImage.objects.create(topic=self.topic, **defaults)

    def test_select_image_sets_hero(self):
        first_image = self._create_image(is_hero=True)
        second_image = self._create_image()

        response = self.client.post(
            f'/api/topics/image/{self.topic.uuid}/select/{second_image.id}'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'finished')

        first_image.refresh_from_db()
        second_image.refresh_from_db()

        self.assertFalse(first_image.is_hero)
        self.assertTrue(second_image.is_hero)

    def test_select_image_requires_authentication(self):
        image = self._create_image()
        self.client.logout()

        response = self.client.post(
            f'/api/topics/image/{self.topic.uuid}/select/{image.id}'
        )

        self.assertEqual(response.status_code, 401)

    def test_select_image_rejects_other_user(self):
        image = self._create_image()
        other_user = self.User.objects.create_user(
            'other', 'other@example.com', 'password'
        )
        self.client.force_login(other_user)

        response = self.client.post(
            f'/api/topics/image/{self.topic.uuid}/select/{image.id}'
        )

        self.assertEqual(response.status_code, 403)
