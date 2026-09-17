from django.db import models


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
    is_emergency = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"
