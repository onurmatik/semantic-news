from django.contrib.auth import get_user_model
from django.test import TestCase

from semanticnews.topics.models import Topic, TopicSection, TopicTitle
from semanticnews.topics.widgets import load_widgets


class TopicWidgetAPITests(TestCase):
    def setUp(self):
        super().setUp()
        load_widgets()
        self.widget_name = "paragraph"
        self.action_name = "summarize"

        User = get_user_model()
        self.user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(self.user)

        self.topic = Topic.objects.create(created_by=self.user)
        TopicTitle.objects.create(topic=self.topic, title="Topic Title")

    def test_list_widgets_returns_registry_definitions(self):
        response = self.client.get("/api/topics/widgets/definitions")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("items", payload)
        identifiers = {item["id"] for item in payload["items"]}
        self.assertIn(self.widget_name, identifiers)

    def test_widget_details_includes_actions(self):
        response = self.client.get(f"/api/topics/widgets/{self.widget_name}/details")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.widget_name)
        action_ids = {action["id"] for action in data.get("actions", [])}
        self.assertIn(self.action_name, action_ids)

    def test_execute_widget_action_records_section_state(self):
        payload = {
            "topic_uuid": str(self.topic.uuid),
            "widget_name": self.widget_name,
            "action": self.action_name,
            "extra_instructions": "  Keep it brief.  ",
            "metadata": {"model": "gpt"},
        }

        response = self.client.post(
            "/api/topics/widgets/execute",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["widget_name"], self.widget_name)
        self.assertEqual(data["action"], self.action_name)
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["extra_instructions"], "Keep it brief.")
        self.assertEqual(data["metadata"], {"model": "gpt"})

        section = TopicSection.objects.get(id=data["section_id"])
        self.assertEqual(section.topic, self.topic)
        self.assertEqual(section.widget_name, self.widget_name)
        self.assertEqual(section.metadata, {"model": "gpt"})
        self.assertEqual(section.execution_state.get("status"), "queued")

    def test_execute_reuses_existing_section(self):
        section = TopicSection.objects.create(topic=self.topic, widget_name=self.widget_name)

        payload = {
            "topic_uuid": str(self.topic.uuid),
            "widget_name": self.widget_name,
            "action": self.action_name,
            "section_id": section.id,
        }

        response = self.client.post(
            "/api/topics/widgets/execute",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["section_id"], section.id)
        self.assertEqual(TopicSection.objects.count(), 1)

    def test_status_endpoint_returns_execution_snapshot(self):
        response = self.client.post(
            "/api/topics/widgets/execute",
            {
                "topic_uuid": str(self.topic.uuid),
                "widget_name": self.widget_name,
                "action": self.action_name,
            },
            content_type="application/json",
        )
        section_id = response.json()["section_id"]

        status_response = self.client.get(
            f"/api/topics/widgets/sections/{section_id}",
            {"topic_uuid": str(self.topic.uuid)},
        )

        self.assertEqual(status_response.status_code, 200)
        snapshot = status_response.json()
        self.assertEqual(snapshot["section_id"], section_id)
        self.assertEqual(snapshot["status"], "queued")

    def test_execute_requires_authentication(self):
        self.client.logout()
        response = self.client.post(
            "/api/topics/widgets/execute",
            {
                "topic_uuid": str(self.topic.uuid),
                "widget_name": self.widget_name,
                "action": self.action_name,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_execute_validates_widget_and_action(self):
        response = self.client.post(
            "/api/topics/widgets/execute",
            {
                "topic_uuid": str(self.topic.uuid),
                "widget_name": "unknown",
                "action": self.action_name,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            "/api/topics/widgets/execute",
            {
                "topic_uuid": str(self.topic.uuid),
                "widget_name": self.widget_name,
                "action": "unknown",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_execute_rejects_section_from_other_topic(self):
        other_topic = Topic.objects.create()
        other_section = TopicSection.objects.create(
            topic=other_topic,
            widget_name=self.widget_name,
        )

        response = self.client.post(
            "/api/topics/widgets/execute",
            {
                "topic_uuid": str(self.topic.uuid),
                "widget_name": self.widget_name,
                "action": self.action_name,
                "section_id": other_section.id,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
