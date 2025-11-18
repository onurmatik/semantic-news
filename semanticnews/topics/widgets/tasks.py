from semanticnews.celery import app
from semanticnews.topics.widgets import get_widget
from semanticnews.topics.widgets.execution import (
    WidgetExecutionError,
    resolve_widget_action,
)


@app.task
def execute_widget_action_task(
    topic_uuid: str,
    widget_name: str,
    action: str,
    section_id: int | None = None,
    extra_instructions: str | None = None,
    metadata: dict | None = None,
):
    """
    Celery a task to execute a widget action.
    """
    from semanticnews.topics.models import Topic, TopicSection
    from semanticnews.topics.widgets.services import TopicWidgetExecutionService
    from .helpers import execute_widget_action as run_widget_execution

    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        raise WidgetExecutionError("Topic not found")

    widget = get_widget(widget_name)
    action = resolve_widget_action(widget, action)

    section: TopicSection | None = None
    if section_id is not None:
        try:
            section = TopicSection.objects.get(id=section_id, topic=topic)
        except TopicSection.DoesNotExist:
            raise WidgetExecutionError("Topic section not found")

    execution_service = TopicWidgetExecutionService()
    execution = execution_service.queue_execution(
        topic=topic,
        widget=widget,
        action=action,
        section=section,
        metadata=metadata or {},
        extra_instructions=extra_instructions,
    )

    result = run_widget_execution.apply(kwargs={"execution_id": execution.section.id})
    if result.failed():
        raise result.result
