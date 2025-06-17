from django.apps import AppConfig


class RecapConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.annotations.recaps'
    label = 'topic_recaps'
