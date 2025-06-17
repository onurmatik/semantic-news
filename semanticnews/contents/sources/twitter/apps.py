from django.apps import AppConfig


class TwitterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticnews.contents.sources.twitter'
    label = 'twitter_content'
