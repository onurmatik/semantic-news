from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ...models import Topic
from .models import TopicYoutubeVideo


class TopicMediaAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("alice", "alice@example.com", "pwd12345")
        self.client.force_login(self.user)
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
