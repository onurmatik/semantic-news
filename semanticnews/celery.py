import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "semanticnews.settings")

app = Celery("semanticnews")

# Load settings from Django settings, using a CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks.py in all installed apps
app.autodiscover_tasks()
