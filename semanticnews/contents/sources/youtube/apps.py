from django.apps import AppConfig


class YoutubeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.contents.sources.youtube'
    label = 'youtube_content'
