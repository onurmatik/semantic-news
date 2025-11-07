from django.contrib import admin

from .models import Widget, WidgetAction, WidgetActionExecution


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "template")
    ordering = ("name",)


@admin.register(WidgetAction)
class WidgetActionAdmin(admin.ModelAdmin):
    list_display = ("name", "widget", "icon")
    search_fields = ("name", "widget__name")
    ordering = ("name",)
    list_filter = ("widget",)


@admin.register(WidgetActionExecution)
class WidgetActionExecutionAdmin(admin.ModelAdmin):
    list_display = ("action", "status", "created_at", "updated_at")
    search_fields = ("action__name", "action__widget__name")
    ordering = ("-created_at",)
    list_filter = ("status", "action__widget")
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at")

