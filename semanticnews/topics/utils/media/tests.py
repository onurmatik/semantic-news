from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ...models import Topic
from .models import TopicYoutubeVideo, TopicVimeoVideo


class TopicMediaAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("alice", "alice@example.com", "pwd12345")
        self.client.force_login(self.user)
        with patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536):
            self.topic = Topic.objects.create(title="Test Topic", created_by=self.user)

    @patch("semanticnews.topics.utils.media.api.yt_dlp.YoutubeDL.extract_info")
    def test_add_media(self, mock_extract_info):
        mock_extract_info.return_value = {
            "title": "Sample Title",
            "description": "Sample description",
            "thumbnail": "http://example.com/thumb.jpg",
            "timestamp": 1609459200,  # 2021-01-01 00:00:00 UTC
        }

        payload = {
            "topic_uuid": str(self.topic.uuid),
            "media_type": "youtube",
            "url": "https://youtu.be/dQw4w9WgXcQ",
        }
        response = self.client.post(
            "/api/topics/media/add",
            payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TopicYoutubeVideo.objects.count(), 1)
        media = TopicYoutubeVideo.objects.first()
        self.assertEqual(media.url, payload["url"])
        self.assertEqual(media.video_id, "dQw4w9WgXcQ")
        self.assertEqual(media.title, "Sample Title")
        self.assertEqual(media.description, "Sample description")
        self.assertEqual(media.thumbnail, "http://example.com/thumb.jpg")
        self.assertEqual(media.published_at.year, 2021)
        self.assertEqual(media.status, "finished")

    @patch("semanticnews.topics.utils.media.api.yt_dlp.YoutubeDL.extract_info")
    def test_add_vimeo_media(self, mock_extract_info):
        mock_extract_info.return_value = {
            "title": "Vimeo Title",
            "description": "Vimeo description",
            "thumbnail": "http://example.com/vimeo.jpg",
            "timestamp": 1609459200,
        }

        payload = {
            "topic_uuid": str(self.topic.uuid),
            "media_type": "vimeo",
            "url": "https://vimeo.com/123456",
        }
        response = self.client.post(
            "/api/topics/media/add",
            payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TopicVimeoVideo.objects.count(), 1)
        media = TopicVimeoVideo.objects.first()
        self.assertEqual(media.url, payload["url"])
        self.assertEqual(media.video_id, "123456")
        self.assertEqual(media.title, "Vimeo Title")
        self.assertEqual(media.description, "Vimeo description")
        self.assertEqual(media.thumbnail, "http://example.com/vimeo.jpg")
        self.assertEqual(media.published_at.year, 2021)
        self.assertEqual(media.status, "finished")


class TopicMediaDisplayTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("bob", "bob@example.com", "pwd12345")
        with patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536):
            self.topic = Topic.objects.create(title="Display", created_by=self.user)
        TopicYoutubeVideo.objects.create(
            topic=self.topic,
            url="https://youtu.be/vid123",
            video_id="vid123",
            title="Video",
            description="",
            thumbnail="",
            published_at=timezone.now(),
            status="finished",
        )
        TopicVimeoVideo.objects.create(
            topic=self.topic,
            url="https://vimeo.com/987654",
            video_id="987654",
            title="Vimeo",
            description="",
            thumbnail="",
            published_at=timezone.now(),
            status="finished",
        )

    def test_detail_displays_video(self):
        response = self.client.get(self.topic.get_absolute_url())
        self.assertContains(response, "youtube.com/embed/vid123")

    def test_detail_displays_vimeo(self):
        TopicYoutubeVideo.objects.all().delete()
        response = self.client.get(self.topic.get_absolute_url())
        self.assertContains(response, "player.vimeo.com/video/987654")

    def test_edit_displays_video(self):
        self.client.force_login(self.user)
        url = reverse(
            "topics_detail_edit",
            kwargs={"username": self.user.username, "slug": self.topic.slug},
        )
        response = self.client.get(url)
        self.assertContains(response, "youtube.com/embed/vid123")

    def test_edit_displays_vimeo(self):
        self.client.force_login(self.user)
        TopicYoutubeVideo.objects.all().delete()
        url = reverse(
            "topics_detail_edit",
            kwargs={"username": self.user.username, "slug": self.topic.slug},
        )
        response = self.client.get(url)
        self.assertContains(response, "player.vimeo.com/video/987654")
