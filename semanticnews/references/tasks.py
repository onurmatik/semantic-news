from celery import shared_task

from semanticnews.topics.models import Topic
from semanticnews.topics.tasks import generate_section_suggestions

from .models import Reference


def _refresh_stale_references_for_topic(topic: Topic) -> list[Reference]:
    references = (
        Reference.objects.filter(topic_links__topic=topic, topic_links__is_deleted=False)
        .distinct()
        .order_by("id")
    )
    refreshed: list[Reference] = []
    for reference in references:
        if reference.should_refresh():
            reference.refresh_metadata()
            refreshed.append(reference)
    return refreshed


@shared_task(name="references.refresh_stale_references")
def refresh_stale_references(topic_uuid: str) -> dict:
    try:
        topic = Topic.objects.get(uuid=topic_uuid)
    except Topic.DoesNotExist:
        return {"success": False, "message": "Topic not found.", "refreshed_count": 0}

    refreshed = _refresh_stale_references_for_topic(topic)
    return {"success": True, "refreshed_count": len(refreshed)}


@shared_task(name="references.generate_reference_suggestions")
def generate_reference_suggestions(topic_uuid: str, simulate_failure: bool = False):
    if simulate_failure:
        raise ValueError("Unable to generate reference suggestions.")

    return generate_section_suggestions(topic_uuid)
