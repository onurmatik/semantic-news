from unittest.mock import MagicMock, patch
import tempfile
import shutil

from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from semanticnews.topics.models import Topic
from semanticnews.agenda.models import Event
from semanticnews.topics.utils.images.models import TopicImage
from semanticnews.topics.utils.recaps.models import TopicRecap


class SearchViewTests(TestCase):
    @patch("semanticnews.views.OpenAI")
    @patch(
        "semanticnews.topics.models.Topic.get_embedding",
        side_effect=[[0.0] * 1536, [1.0] * 1536],
    )
    def test_search_returns_similar_topics_and_events(
        self, mock_topic_embedding, mock_openai
    ):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.0] * 1536)]
        )

        topic1 = Topic.objects.create(title="Topic One", status="published")
        topic2 = Topic.objects.create(title="Topic Two", status="published")

        Event.objects.create(
            title="Event One",
            date="2024-01-01",
            status="published",
            embedding=[0.0] * 1536,
        )
        Event.objects.create(
            title="Event Two",
            date="2024-01-02",
            status="published",
            embedding=[1.0] * 1536,
        )

        response = self.client.get(reverse("search_results"), {"q": "query"})
        self.assertEqual(response.status_code, 200)
        topics = list(response.context["topics"])
        events = list(response.context["events"])
        self.assertEqual(len(topics), 2)
        self.assertEqual(len(events), 2)
        self.assertEqual(topics[0], topic1)
        self.assertEqual(events[0].title, "Event One")


class HomeViewTopicListItemTests(TestCase):
    @patch("semanticnews.topics.models.Topic.get_embedding", return_value=[0.0] * 1536)
    def test_home_displays_thumbnail_and_recap(self, mock_embedding):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir)
        override = self.settings(MEDIA_ROOT=tmpdir)
        override.enable()
        self.addCleanup(override.disable)

        topic = Topic.objects.create(title="Topic", status="published")

        image_data = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
            b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00"
            b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02L\x01\x00;"
        )
        image_file = SimpleUploadedFile("image.gif", image_data, content_type="image/gif")
        thumb_file = SimpleUploadedFile("thumb.gif", image_data, content_type="image/gif")
        TopicImage.objects.create(topic=topic, image=image_file, thumbnail=thumb_file)

        TopicRecap.objects.create(topic=topic, recap="My recap", status="finished")

        response = self.client.get(reverse("home"))

        self.assertContains(response, "My recap")
        self.assertContains(response, topic.thumbnail.url)


class LocaleRoutingTests(TestCase):
    def test_homepage_available_with_turkish_prefix(self):
        response = self.client.get("/tr/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.resolver_match.url_name, "home")
