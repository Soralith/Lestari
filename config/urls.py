"""
URL configuration for config project.

All non-admin URLs are routed to the `konsultasi` app.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("konsultasi.urls")),
]
