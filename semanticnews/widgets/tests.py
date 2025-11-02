from django.core.exceptions import ValidationError
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from semanticnews.topics.models import Topic, TopicSection

from .models import Widget, WidgetAPIExecution
from .services import (
    WidgetExecutionRegistry,
    WidgetExecutionService,
    WidgetExecutionStrategy,
    WidgetRegistryLookupError,
)
from .tasks import execute_widget


class WidgetModelTests(TestCase):
    def test_defaults_are_empty_collections(self):
        widget = Widget(name="Example")
        widget.full_clean()
        widget.save()


class WidgetAPIExecutionModelTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user("user", "user@example.com", "pass")
        self.topic = Topic.objects.create(title="Example", created_by=self.user)
        self.widget = Widget.objects.create(name="Execution widget")

    def test_defaults(self):
        execution = WidgetAPIExecution.objects.create(
            topic=self.topic,
            section=None,
            widget=self.widget,
            user=self.user,
        )

        self.assertEqual(execution.status, WidgetAPIExecution.Status.PENDING)
        self.assertIsNone(execution.started_at)
        self.assertEqual(execution.metadata, {})


class _EchoStrategy(WidgetExecutionStrategy):
    def __init__(self):
        super().__init__(response_schema=None)

    def call_model(self, state):
        raw = {"text": state.final_prompt}
        parsed = {"result": "ok"}
        state.raw_response = raw
        state.parsed_response = parsed
        return raw, parsed


class WidgetExecutionServiceTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user("user", "user@example.com", "pass")
        self.topic = Topic.objects.create(title="Service", created_by=self.user)
        self.widget = Widget.objects.create(
            name="Service Widget",
            prompt_template="Prompt: {{ topic.title }}",
        )
        self.section = TopicSection.objects.create(topic=self.topic, widget=self.widget)

    def test_registry_lookup_error(self):
        registry = WidgetExecutionRegistry()

        with self.assertRaises(WidgetRegistryLookupError):
            registry.get("unknown")

    def test_execute_populates_execution_metadata(self):
        execution = WidgetAPIExecution.objects.create(
            topic=self.topic,
            section=self.section,
            widget=self.widget,
            user=self.user,
        )

        registry = WidgetExecutionRegistry()
        registry.register(self.widget.name, _EchoStrategy())
        service = WidgetExecutionService(registry)

        state = service.execute(execution)

        self.assertEqual(state.parsed_response, {"result": "ok"})
        self.assertIn("topic", execution.prompt_context)
        self.assertTrue(execution.prompt_text.endswith("Respond in English."))
        self.assertEqual(execution.metadata.get("history_count"), 0)
        self.assertEqual(execution.raw_response, {"text": execution.prompt_text})


class ExecuteWidgetTaskTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user("user", "user@example.com", "pass")
        self.topic = Topic.objects.create(title="Task Topic", created_by=self.user)
        self.widget = Widget.objects.create(
            name="Task Widget",
            prompt_template="Prompt: {{ topic.title }}",
        )
        self.section = TopicSection.objects.create(topic=self.topic, widget=self.widget)
        self.execution = WidgetAPIExecution.objects.create(
            topic=self.topic,
            section=self.section,
            widget=self.widget,
            user=self.user,
        )

    def _mock_success_state(self):
        def _fake_execute(execution):
            execution.prompt_template = self.widget.prompt_template
            execution.prompt_context = {"topic": {"title": self.topic.title}}
            execution.prompt_text = "Rendered prompt"
            execution.extra_instructions = ""
            execution.metadata = {"rendered_prompt": "Rendered prompt", "history_count": 0}
            execution.raw_response = {"raw": True}
            execution.parsed_response = {"parsed": True}
            return SimpleNamespace(parsed_response=execution.parsed_response)

        return _fake_execute

    @patch("semanticnews.widgets.tasks.WidgetExecutionService.execute")
    def test_execute_widget_updates_models(self, mock_execute):
        mock_execute.side_effect = self._mock_success_state()

        result = execute_widget.run(execution_id=self.execution.id)

        self.section.refresh_from_db()
        self.execution.refresh_from_db()

        self.assertEqual(result["status"], WidgetAPIExecution.Status.SUCCESS)
        self.assertEqual(self.section.status, "finished")
        self.assertEqual(self.section.content, {"parsed": True})
        self.assertEqual(self.execution.status, WidgetAPIExecution.Status.SUCCESS)
        self.assertIsNotNone(self.execution.completed_at)

    @patch("semanticnews.widgets.tasks.WidgetExecutionService.execute")
    def test_execute_widget_failure_updates_status(self, mock_execute):
        mock_execute.side_effect = WidgetRegistryLookupError("missing")

        with self.assertRaises(WidgetRegistryLookupError):
            execute_widget.run(execution_id=self.execution.id)

        self.section.refresh_from_db()
        self.execution.refresh_from_db()

        self.assertEqual(self.section.status, "error")
        self.assertEqual(self.execution.status, WidgetAPIExecution.Status.FAILURE)
        self.assertEqual(self.execution.error_code, "registry_missing")

        self.assertEqual(widget.response_format, {})
        self.assertEqual(widget.tools, [])

    def test_response_format_must_be_mapping(self):
        widget = Widget(name="Bad response", response_format=["not", "a", "dict"])

        with self.assertRaises(ValidationError) as exc:
            widget.full_clean()

        self.assertIn("response_format", exc.exception.error_dict)

    def test_tools_must_be_list_of_non_empty_strings(self):
        widget = Widget(name="Bad tools", tools=["valid", 7, ""])

        with self.assertRaises(ValidationError) as exc:
            widget.full_clean()

        self.assertIn("tools", exc.exception.error_dict)

    def test_valid_widget_passes_clean(self):
        widget = Widget(
            name="Valid widget",
            prompt_template="Render content",
            response_format={"type": "markdown"},
            tools=["web_search"],
            template="{{ body }}",
        )

        # Should not raise
        widget.full_clean()
        widget.save()
