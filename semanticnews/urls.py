from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path, include
from django.conf.urls.i18n import i18n_patterns
from django.contrib.auth.views import LoginView, LogoutView

from . import views as core_views
from .profiles import views as profiles_views
from .topics import views as topics_views
from .topics.api import api as topics_api
from .agenda import views as agenda_views
from .agenda.api import api as agenda_api


urlpatterns = [
    path('snAdmin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path("login/", LoginView.as_view(), name="login"),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("accounts/", include("django.contrib.auth.urls")),
    path('api/agenda/', agenda_api.urls),
    path('api/topics/', topics_api.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


urlpatterns += i18n_patterns(
    path('', core_views.home, name='home'),
    path('search/', core_views.search_results, name='search_results'),
    path('topics/create/', topics_views.topic_create, name='topics_create'),
    path('topics/', topics_views.topics_list, name='topics_list'),
    path('events/', agenda_views.recent_event_list, name='events_recent_list'),
    path('users/', profiles_views.user_list, name='user_list'),

    re_path(
        r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<slug>[-\w]+)/$',
        agenda_views.event_detail,
        name='event_detail',
    ),
    re_path(
        r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/$',
        agenda_views.event_list,
        name='event_list_day',
    ),
    re_path(
        r'^(?P<year>\d{4})/(?P<month>\d{2})/$',
        agenda_views.event_list,
        name='event_list_month',
    ),
    re_path(
        r'^(?P<year>\d{4})/$',
        agenda_views.event_list,
        name='event_list_year',
    ),

    path('@<slug:username>/<slug:slug>/add-event/<uuid:event_uuid>/', topics_views.topic_add_event, name='topics_add_event'),
    path('@<slug:username>/<slug:slug>/remove-event/<uuid:event_uuid>/', topics_views.topic_remove_event, name='topics_remove_event'),
    path('@<slug:username>/<slug:slug>/clone/', topics_views.topic_clone, name='topics_clone'),
    path('@<slug:username>/<slug:slug>/edit/', topics_views.topics_detail_edit, name='topics_detail_edit'),
    path('@<slug:username>/<slug:slug>/', topics_views.topics_detail, name='topics_detail'),

    path('@<slug:username>/', profiles_views.user_profile, name='user_profile'),
    path("profile/", profiles_views.profile_settings, name="profile_settings"),

    prefix_default_language=False
)


admin.site.index_title = 'Welcome to Semantic News'
admin.site.site_header = 'Semantic News Administration'
admin.site.site_title = 'Semantic News Administration'
