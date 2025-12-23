from time import sleep

from celery import shared_task


@shared_task(name="references.generate_reference_suggestions")
def generate_reference_suggestions(topic_uuid: str, simulate_failure: bool = False):
    """Mock task to generate reference suggestions for a topic."""

    # Simulate a short processing delay
    sleep(1)

    if simulate_failure:
        raise ValueError("Unable to generate reference suggestions.")

    return {
        "success": True,
        "message": "Reference suggestions generated successfully.",
        "topic_uuid": topic_uuid,
    }
