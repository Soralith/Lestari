from django.contrib import admin

from .models import ConsultationMessage, ConsultationSession, HealthNote, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "avatar_url")


@admin.register(ConsultationSession)
class ConsultationSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "mode", "created_at", "updated_at")


@admin.register(ConsultationMessage)
class ConsultationMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "is_emergency", "created_at")


@admin.register(HealthNote)
class HealthNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "session", "created_at", "updated_at")