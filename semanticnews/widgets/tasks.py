"""Celery tasks for executing widget actions."""

import logging
from typing import Any, Dict

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def execute_widget_action(self, *, execution_id: int) -> Dict[str, Any]:
    """Execute a widget action."""
