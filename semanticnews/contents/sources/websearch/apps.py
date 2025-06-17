from django.apps import AppConfig


class WebsearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.contents.sources.websearch'
    label = 'websearch_content'
