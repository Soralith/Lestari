from django.urls import path

from . import views

app_name = "konsultasi"

urlpatterns = [
    path("", views.index, name="index"),
    path("konsultasi/<int:session_id>/", views.session_page, name="session_page"),
    path("api/send/", views.api_send_message, name="api_send"),
    path("api/sessions/", views.api_sessions, name="api_sessions"),
    path("api/sessions/<int:session_id>/", views.api_session_detail, name="api_session_detail"),
]
