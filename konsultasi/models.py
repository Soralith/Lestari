from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Per-user profile data (currently just the avatar picture)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar_url = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return f"Profile: {self.user.email}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


class ConsultationSession(models.Model):
    """One 'Konsultasi AI' conversation between a user and Lestari AI."""

    class Mode(models.TextChoices):
        TRIASE_LENGKAP = "triase_lengkap", "Triase Lengkap"
        KONSULTASI_CEPAT = "konsultasi_cepat", "Konsultasi Cepat"
        TANYA_OBAT = "tanya_obat", "Tanya Obat & Resep"

    title = models.CharField(max_length=200, blank=True)
    mode = models.CharField(
        max_length=30,
        choices=Mode.choices,
        default=Mode.TRIASE_LENGKAP,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Konsultasi #{self.pk}"


class ConsultationMessage(models.Model):
    """A single message inside a consultation session."""

    class Role(models.TextChoices):
        USER = "user", "User"
        AI = "ai", "Lestari AI"

    session = models.ForeignKey(
        ConsultationSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    image_url = models.URLField(max_length=500, blank=True)
    is_emergency = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"


class WeatherCache(models.Model):
    """Cached BMKG forecast for one adm4 location (respects rate limits)."""

    adm4 = models.CharField(max_length=30, primary_key=True)
    payload = models.JSONField()
    fetched_at = models.DateTimeField(auto_now=True)


class WeatherSearchCache(models.Model):
    """Cached location-search results for a query string."""

    query = models.CharField(max_length=120, primary_key=True)
    payload = models.JSONField()
    fetched_at = models.DateTimeField(auto_now=True)


class ArtikelCache(models.Model):
    """Cached Google News article results for a query string."""

    query = models.CharField(max_length=200, primary_key=True)
    payload = models.JSONField()
    fetched_at = models.DateTimeField(auto_now=True)
