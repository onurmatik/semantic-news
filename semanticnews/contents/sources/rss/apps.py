from django.apps import AppConfig


class RssConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.contents.sources.rss'
    label = 'rss_content'
