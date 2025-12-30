from django.contrib import admin
from .models import (
    Profile,
    TopicBookmark,
    UserReference,
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


@admin.register(UserReference)
class UserReferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'reference', 'added_at')
    search_fields = ('user__username', 'user__email', 'reference__url')
    list_filter = ('user',)
