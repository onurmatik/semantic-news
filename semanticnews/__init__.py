"""Semantic News Django project package."""

from .celery import app as celery_app

__all__ = ["__version__", "celery_app"]

__version__ = "0.1.0"
