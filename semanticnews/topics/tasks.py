from celery import shared_task
from .models import Topic, Keyword, TopicRecap
from ..utils import translate


@shared_task(
    autoretry_for=(Exception,),   # retry on network errors, etc.
    max_retries=3,
    default_retry_delay=30,
)
def translate_topic_name(topic_id):
    try:
        topic = Topic.objects.get(pk=topic_id)
    except Topic.DoesNotExist:
        return "topic deleted"

    # Already translated?  Exit idempotently.
    if topic.name_en:
        return "already translated"

    translated = translate({"name": topic.name}, from_to='tr_to_en')
    topic.name_en = translated.get("name", topic.name)

    topic.save()


@shared_task(
    autoretry_for=(Exception,),   # retry on network errors, etc.
    max_retries=3,
    default_retry_delay=30,
)
def translate_keyword(keyword_id):
    try:
        keyword = Keyword.objects.get(pk=keyword_id)
    except Keyword.DoesNotExist:
        return "keyword deleted"

    # Already translated?  Exit idempotently.
    if keyword.name_en:
        return "already translated"

    translated = translate({"name": keyword.name}, from_to='tr_to_en')
    keyword.name_en = translated.get("name", keyword.name)

    keyword.save()


@shared_task(
    autoretry_for=(Exception,),   # retry on network errors, etc.
    max_retries=3,
    default_retry_delay=30,
)
def update_topic_recap(topic_id):
    topic = Topic.objects.get(pk=topic_id)
    topic.update_recap()


@shared_task(
    autoretry_for=(Exception,),   # retry on network errors, etc.
    max_retries=3,
    default_retry_delay=30,
)
def create_topic_image(topic_id):
    topic = Topic.objects.get(pk=topic_id)
    topic.create_image()
