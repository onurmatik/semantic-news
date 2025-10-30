from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone

from .models import Topic, TopicContent
from semanticnews.widgets.data.models import TopicData, TopicDataInsight, TopicDataVisualization
from semanticnews.widgets.timeline.models import TopicEvent
from semanticnews.widgets.recaps.models import TopicRecap
from semanticnews.widgets.text.models import TopicText
from semanticnews.widgets.images.models import TopicImage
from semanticnews.widgets.relations.models import TopicEntityRelation


def touch_topic(topic_id):
    """Update the timestamp and embedding for the given Topic.

    When related objects change we want the topic's representation to stay in
    sync. Recompute the embedding using the latest data and update the
    ``updated_at`` field so the change is tracked.
    """
    topic = Topic.objects.filter(pk=topic_id).first()
    if not topic:
        return

    embedding = topic.get_embedding(force=True)
    Topic.objects.filter(pk=topic_id).update(
        updated_at=timezone.now(),
        embedding=embedding,
    )
    topic.embedding = embedding


@receiver([post_save, post_delete], sender=TopicEvent)
def update_topic_timestamp_from_event(sender, instance, **kwargs):
    touch_topic(instance.topic_id)


@receiver([post_save, post_delete], sender=TopicContent)
def update_topic_timestamp_from_content(sender, instance, **kwargs):
    touch_topic(instance.topic_id)


@receiver([post_save, post_delete], sender=TopicRecap)
def update_topic_timestamp_from_recap(sender, instance, **kwargs):
    touch_topic(instance.topic_id)


@receiver([post_save, post_delete], sender=TopicText)
def update_topic_timestamp_from_text(sender, instance, **kwargs):
    touch_topic(instance.topic_id)


@receiver([post_save, post_delete], sender=TopicImage)
def update_topic_timestamp_from_image(sender, instance, **kwargs):
    if instance.topic_id:
        touch_topic(instance.topic_id)


@receiver([post_save, post_delete], sender=TopicEntityRelation)
def update_topic_timestamp_from_relation(sender, instance, **kwargs):
    touch_topic(instance.topic_id)


@receiver([post_save, post_delete], sender=TopicData)
def update_topic_timestamp_from_data(sender, instance, **kwargs):
    touch_topic(instance.topic_id)


@receiver([post_save, post_delete], sender=TopicDataInsight)
def update_topic_timestamp_from_data_insight(sender, instance, **kwargs):
    touch_topic(instance.topic_id)


@receiver([post_save, post_delete], sender=TopicDataVisualization)
def update_topic_timestamp_from_data_visualization(sender, instance, **kwargs):
    touch_topic(instance.topic_id)


@receiver(m2m_changed, sender=Topic.events.through)
def topic_events_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        if reverse:
            for pk in pk_set:
                touch_topic(pk)
        else:
            touch_topic(instance.pk)


@receiver(m2m_changed, sender=Topic.contents.through)
def topic_contents_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        if reverse:
            for pk in pk_set:
                touch_topic(pk)
        else:
            touch_topic(instance.pk)
