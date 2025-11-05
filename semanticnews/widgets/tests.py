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
