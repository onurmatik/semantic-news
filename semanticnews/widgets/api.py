"""API endpoints for managing topic widgets and executions."""

import logging
from typing import List
from ninja import Router, Schema
from semanticnews.widgets.models import Widget, WidgetActionExecution

logger = logging.getLogger(__name__)

router = Router()


class WidgetDefinition(Schema):
    id: int
    name: str


class WidgetDefinitionListResponse(Schema):
    total: int
    items: List[WidgetDefinition]


class WidgetActionExecutionCreateRequest(Schema):
    ...


class WidgetActionExecutionStatusResponse(Schema):
    ...


@router.get("", response=WidgetDefinitionListResponse)
def list_widgets(request):
    widgets = Widget.objects.all().order_by("name")
    items = [_serialize_widget(widget) for widget in widgets]
    return WidgetDefinitionListResponse(total=len(items), items=items)


@router.post("/execute", response=WidgetActionExecutionStatusResponse)
def execute_widget_action(request, payload: WidgetActionExecutionCreateRequest):
    """Execute the action via the LLM and populate the topic section"""


@router.get("/executions/{execution_id}", response=WidgetActionExecutionStatusResponse)
def get_execution_status(request, execution_id: int, topic_uuid: str):
    """Get and update the execution status"""
