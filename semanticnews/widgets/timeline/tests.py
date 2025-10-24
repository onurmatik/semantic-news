import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from semanticnews.agenda.models import Event
from semanticnews.topics.models import Topic
from semanticnews.widgets.timeline.models import TopicEvent


class TimelineCreateAPITests(TestCase):
    """Tests for relating AI-suggested events to a topic via the API."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(self.user)

    def test_links_selected_events_to_topic(self):
        topic = Topic.objects.create(title="My Topic", created_by=self.user)
        event = Event.objects.create(title="Suggested", date="2024-01-01")

        payload = {
            "topic_uuid": str(topic.uuid),
            "event_uuids": [str(event.uuid)],
        }
        response = self.client.post(
            "/api/topics/timeline/create",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["uuid"], str(event.uuid))

        topic.refresh_from_db()
        self.assertTrue(topic.events.filter(pk=event.pk).exists())
        topic_event = TopicEvent.objects.get(topic=topic, event=event)
        self.assertEqual(topic_event.source, "agent")
        self.assertEqual(topic_event.created_by, self.user)
