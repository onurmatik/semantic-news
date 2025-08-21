from django.contrib import admin
from .models import (
    Profile,
    TopicBookmark,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__username', 'user__email')


@admin.register(TopicBookmark)
class TopicBookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic')
    search_fields = ('user__username', 'topic__name')
    list_filter = ('user',)
