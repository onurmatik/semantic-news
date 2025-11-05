from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from semanticnews.topics.models import Topic, TopicSection, TopicTitle
from semanticnews.widgets.models import (
    Widget,
    WidgetAction,
    WidgetActionExecution,
)
from semanticnews.widgets.services import (
    WidgetExecutionRegistry,
    WidgetExecutionService,
    WidgetExecutionStrategy,
)


class DummyStrategy(WidgetExecutionStrategy):
    """Strategy stub that avoids external API calls during tests."""

    def __init__(self):
        super().__init__(response_schema=None)

    def call_model(self, state):  # pragma: no cover - trivial override
        return {"raw": True}, {"result": "ok"}


class WidgetExecutionServiceTests(TestCase):
    def setUp(self):
        super().setUp()
        self.registry = WidgetExecutionRegistry()
        self.strategy = DummyStrategy()

    def _create_topic(self, title: str) -> Topic:
        topic = Topic.objects.create()
        TopicTitle.objects.create(topic=topic, title=title)
        return topic

    def test_execute_uses_action_configuration(self):
        topic = self._create_topic("Sample Topic")
        widget = Widget.objects.create(name="summary")
        action = WidgetAction.objects.create(
            widget=widget,
            name="summary.generate",
            prompt_template="Hello {{ topic.title }}",
            tools=["retrieval"],
        )
        section = TopicSection.objects.create(topic=topic, widget=widget)

        execution = WidgetActionExecution.objects.create(action=action, section=section)
        execution.metadata = {"model": "metadata-model"}
        execution.extra_instructions = "Keep it short."
        execution.response_schema = {"type": "object"}

        self.registry.register(widget.name, self.strategy)
        service = WidgetExecutionService(registry=self.registry)

        state = service.execute(execution)

        self.assertEqual(execution.widget, widget)
        self.assertEqual(state.model_name, "metadata-model")
        self.assertEqual(execution.model_name, "metadata-model")
        self.assertEqual(state.tools, [{"type": "retrieval"}])
        self.assertEqual(execution.tools, [{"type": "retrieval"}])
        self.assertEqual(execution.prompt_template, action.prompt_template)
        self.assertIn("Sample Topic", state.rendered_prompt)
        self.assertIn("Respond in", state.final_prompt)
        self.assertIn("Keep it short.", state.final_prompt)
        self.assertEqual(state.response_schema, {"type": "object"})
        self.assertEqual(execution.response_schema, {"type": "object"})
        self.assertEqual(execution.widget_type, widget.name)
        self.assertIn("rendered_prompt", execution.metadata)
        self.assertEqual(execution.metadata.get("history_count"), 0)
        self.assertEqual(execution.prompt_context.get("topic", {}).get("title"), "Sample Topic")
        self.assertEqual(execution.raw_response, {"raw": True})
        self.assertEqual(execution.parsed_response, {"result": "ok"})


class WidgetActionAPITests(TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user("user", "user@example.com", "password")
        self.client.force_login(self.user)
        self.topic = Topic.objects.create(created_by=self.user)
        TopicTitle.objects.create(topic=self.topic, title="Sample Topic")
        self.widget = Widget.objects.create(name="summary")
        self.action = WidgetAction.objects.create(widget=self.widget, name="summary.generate")

    def test_execute_widget_action_creates_execution_and_section(self):
        payload = {
            "topic_uuid": str(self.topic.uuid),
            "widget_id": self.widget.id,
            "action_id": self.action.id,
            "extra_instructions": "  Keep it brief.  ",
            "metadata": {"model": "gpt"},
        }

        with patch("semanticnews.widgets.api.execute_widget_action_task.delay") as mock_delay:
            response = self.client.post(
                "/api/topics/widget/execute",
                payload,
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], WidgetActionExecution.Status.PENDING)
        self.assertEqual(data["widget_id"], self.widget.id)
        self.assertEqual(data["action_id"], self.action.id)
        self.assertEqual(data["topic_uuid"], str(self.topic.uuid))
        self.assertIsNotNone(data["section_id"])

        execution = WidgetActionExecution.objects.get(id=data["id"])
        self.assertEqual(execution.extra_instructions, "Keep it brief.")
        self.assertEqual(execution.metadata, {"model": "gpt"})
        self.assertEqual(TopicSection.objects.count(), 1)

        mock_delay.assert_called_once_with(execution_id=execution.id)

    def test_execute_widget_action_reuses_existing_section(self):
        section = TopicSection.objects.create(topic=self.topic, widget=self.widget)
        payload = {
            "topic_uuid": str(self.topic.uuid),
            "widget_id": self.widget.id,
            "action_id": self.action.id,
            "section_id": section.id,
        }

        with patch("semanticnews.widgets.api.execute_widget_action_task.delay") as mock_delay:
            response = self.client.post(
                "/api/topics/widget/execute",
                payload,
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["section_id"], section.id)
        self.assertEqual(TopicSection.objects.count(), 1)
        mock_delay.assert_called_once()

    def test_execute_widget_action_validates_section(self):
        other_topic = Topic.objects.create()
        other_section = TopicSection.objects.create(topic=other_topic, widget=self.widget)
        payload = {
            "topic_uuid": str(self.topic.uuid),
            "widget_id": self.widget.id,
            "action_id": self.action.id,
            "section_id": other_section.id,
        }

        response = self.client.post(
            "/api/topics/widget/execute",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(WidgetActionExecution.objects.count(), 0)

    def test_execute_widget_action_requires_authentication(self):
        self.client.logout()
        payload = {
            "topic_uuid": str(self.topic.uuid),
            "widget_id": self.widget.id,
            "action_id": self.action.id,
        }

        response = self.client.post(
            "/api/topics/widget/execute",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(WidgetActionExecution.objects.count(), 0)

    def test_get_execution_status_returns_payload(self):
        section = TopicSection.objects.create(topic=self.topic, widget=self.widget)
        execution = WidgetActionExecution.objects.create(action=self.action, section=section)

        response = self.client.get(
            f"/api/topics/widget/executions/{execution.id}",
            {"topic_uuid": str(self.topic.uuid)},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], execution.id)
        self.assertEqual(data["status"], WidgetActionExecution.Status.PENDING)
        self.assertEqual(data["section_id"], section.id)

    def test_get_execution_status_scopes_to_topic(self):
        section = TopicSection.objects.create(topic=self.topic, widget=self.widget)
        execution = WidgetActionExecution.objects.create(action=self.action, section=section)
        other_topic = Topic.objects.create()

        response = self.client.get(
            f"/api/topics/widget/executions/{execution.id}",
            {"topic_uuid": str(other_topic.uuid)},
        )

        self.assertEqual(response.status_code, 404)
