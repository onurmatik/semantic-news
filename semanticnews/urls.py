from django.contrib import admin
from django.urls import path, re_path, include
from django.conf.urls.i18n import i18n_patterns
from django.contrib.auth.views import LoginView, LogoutView

from . import views as core_views
from .profiles import views as profiles_views
from .topics import views as topics_views
from .agenda import views as agenda_views


urlpatterns = [
    path('snAdmin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path("login/", LoginView.as_view(), name="login"),
    path('logout/', LogoutView.as_view(), name='logout'),
]


urlpatterns += i18n_patterns(
    path('', core_views.home, name='home'),
    path('search/', core_views.search_results, name='search_results'),

    re_path(
        r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<slug>[-\w]+)/$',
        agenda_views.entry_detail,
        name='entry_detail',
    ),
    re_path(
        r'^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/$',
        agenda_views.entry_list,
        name='entry_list_day',
    ),
    re_path(
        r'^(?P<year>\d{4})/(?P<month>\d{2})/$',
        agenda_views.entry_list,
        name='entry_list_month',
    ),
    re_path(
        r'^(?P<year>\d{4})/$',
        agenda_views.entry_list,
        name='entry_list_year',
    ),

    path('@<slug:username>/<slug:slug>/', topics_views.topics_detail, name='topics_detail'),

    path('@<slug:username>', profiles_views.user_profile, name='user_profile'),
    path("profile/", profiles_views.profile_settings, name="profile_settings"),

    prefix_default_language=False
)
