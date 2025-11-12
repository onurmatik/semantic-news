from unittest import mock

from django.test import TestCase
from django.utils import timezone

from semanticnews.topics.models import Topic, TopicSection, TopicTitle
from semanticnews.topics.widgets import load_widgets
from semanticnews.topics.widgets.execution import (
    WidgetExecutionLogEntry,
    WidgetExecutionPipeline,
    WidgetExecutionRequest,
    WidgetExecutionResult,
)
from semanticnews.topics.widgets.paragraph import ParagraphWidget, SummarizeAction
from semanticnews.widgets.tasks import execute_widget_action


class WidgetExecutionPipelineTests(TestCase):
    def setUp(self):
        super().setUp()
        load_widgets()
        self.topic = Topic.objects.create()
        TopicTitle.objects.create(topic=self.topic, title="Topic Title")
        self.section = TopicSection.objects.create(topic=self.topic, widget_name="paragraph")
        self.widget = ParagraphWidget()
        self.action = SummarizeAction()
        self.pipeline = WidgetExecutionPipeline()

    @mock.patch("semanticnews.topics.widgets.execution.OpenAI")
    def test_pipeline_executes_action(self, mock_openai):
        parsed_payload = {"summary": "Concise"}
        response_mock = mock.MagicMock()
        response_mock.output_parsed = parsed_payload
        response_mock.model_dump.return_value = {"raw": True}
        client_mock = mock_openai.return_value.__enter__.return_value
        client_mock.responses.parse.return_value = response_mock

        request = WidgetExecutionRequest(
            section=self.section,
            widget=self.widget,
            action=self.action,
            metadata={"text": "Long form content."},
        )

        result = self.pipeline.execute(request)

        client_mock.responses.parse.assert_called_once()
        self.assertIn("Topic Title", result.prompt)
        self.assertEqual(result.parsed_response, parsed_payload)
        self.assertEqual(dict(result.content), parsed_payload)
        self.assertIsNotNone(result.log_entry)
        self.assertEqual(result.log_entry.status, "success")
        self.assertEqual(result.metadata.get("model"), self.pipeline.default_model)


class ExecuteWidgetActionTaskTests(TestCase):
    def setUp(self):
        super().setUp()
        load_widgets()
        self.topic = Topic.objects.create()
        TopicTitle.objects.create(topic=self.topic, title="Topic Title")
        self.section = TopicSection.objects.create(topic=self.topic, widget_name="paragraph")
        self.section.metadata = {"text": "Body"}
        self.section.execution_state = {"action": "summarize", "status": "queued"}
        self.section.save()

    @mock.patch("semanticnews.widgets.tasks.WidgetExecutionPipeline")
    def test_execute_widget_action_updates_section(self, pipeline_mock):
        pipeline_instance = pipeline_mock.return_value
        log_entry = WidgetExecutionLogEntry(
            status="success",
            created_at=timezone.now(),
            prompt="Prompt",
            model="gpt-test",
            tools=[],
            raw_response={"raw": True},
            parsed_response={"summary": "Body"},
        )
        pipeline_instance.execute.return_value = WidgetExecutionResult(
            content={"summary": "Body"},
            metadata={"model": "gpt-test"},
            context={"topic": "Topic Title"},
            prompt="Prompt",
            model="gpt-test",
            tools=[],
            raw_response={"raw": True},
            parsed_response={"summary": "Body"},
            log_entry=log_entry,
        )

        payload = execute_widget_action(execution_id=self.section.id)

        self.section.refresh_from_db()
        self.assertEqual(self.section.execution_state.get("status"), "finished")
        self.assertEqual(self.section.content, {"summary": "Body"})
        self.assertEqual(self.section.metadata.get("model"), "gpt-test")
        self.assertTrue(self.section.metadata.get("execution_logs"))
        self.assertEqual(payload["status"], "finished")
        self.assertEqual(payload["section_id"], self.section.id)
