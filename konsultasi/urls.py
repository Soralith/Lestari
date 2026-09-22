from django.urls import path

from . import views

app_name = "konsultasi"

urlpatterns = [
    path("", views.landing_page, name="landing"),
    path("login/", views.login_page, name="login"),
    path("signup/", views.signup_page, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("konsultasi/", views.index, name="index"),
    path("konsultasi/<int:session_id>/", views.session_page, name="session_page"),
    path("api/send/", views.api_send_message, name="api_send"),
    path("api/sessions/", views.api_sessions, name="api_sessions"),
    path("api/sessions/<int:session_id>/", views.api_session_detail, name="api_session_detail"),
    path("api/profile/avatar/", views.api_upload_avatar, name="api_upload_avatar"),
]
