from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserBookmark


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass


@admin.register(UserBookmark)
class UserBookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic', 'created_at')
    search_fields = ('user__username', 'topic__title')
