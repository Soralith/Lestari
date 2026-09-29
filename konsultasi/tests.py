from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import ConsultationSession, HealthNote
from .services import _execute_note_calls


class HealthNoteApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice@example.com", email="alice@example.com", password="secret123"
        )
        self.other = User.objects.create_user(
            username="bob@example.com", email="bob@example.com", password="secret123"
        )
        self.client.force_login(self.user)

    def test_catatan_page_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("konsultasi:catatan"))
        self.assertRedirects(resp, "/?next=/catatan/")

    def test_notes_list_is_user_scoped(self):
        HealthNote.objects.create(user=self.user, title="Punya saya", content="konten")
        HealthNote.objects.create(user=self.other, title="Punya orang lain", content="konten")
        resp = self.client.get(reverse("konsultasi:api_notes"))
        self.assertEqual(resp.status_code, 200)
        titles = [n["title"] for n in resp.json()["notes"]]
        self.assertEqual(titles, ["Punya saya"])

    def test_delete_own_note(self):
        note = HealthNote.objects.create(user=self.user, title="Hapus ini", content="x")
        resp = self.client.post(reverse("konsultasi:api_note_delete", args=[note.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(HealthNote.objects.filter(id=note.id).exists())

    def test_delete_other_users_note_not_allowed(self):
        note = HealthNote.objects.create(user=self.other, title="Bukan punya saya", content="x")
        resp = self.client.post(reverse("konsultasi:api_note_delete", args=[note.id]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(HealthNote.objects.filter(id=note.id).exists())


class HealthNoteFunctionCallTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="carol@example.com", email="carol@example.com", password="secret123"
        )
        self.session = ConsultationSession.objects.create(title="Konsultasi")

    def _call(self, name="create_health_note", args=None):
        return type("FC", (), {"name": name, "args": args or {}})()

    def test_execute_note_call_creates_note_from_report_generator(self):
        calls = [self._call(args={"title": "Demam"})]
        generator_calls = []

        def fake_generator(conv, title):
            generator_calls.append((conv, title))
            return "## Laporan Analitis\nDemam disertai meriang."

        notes = _execute_note_calls(
            calls,
            user=self.user,
            session=self.session,
            conversation_text="User: demam 3 hari\nLestari AI: ...",
            report_generator=fake_generator,
        )
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertEqual(note.title, "Demam")
        self.assertEqual(note.content, "## Laporan Analitis\nDemam disertai meriang.")
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.session, self.session)
        self.assertEqual(generator_calls, [("User: demam 3 hari\nLestari AI: ...", "Demam")])

    def test_falls_back_to_model_content_when_generator_fails(self):
        calls = [self._call(args={"title": "Batuk", "content": "## Ringkasan\nBatuk kering."})]

        def failing_generator(conv, title):
            raise RuntimeError("network down")

        notes = _execute_note_calls(
            calls,
            user=self.user,
            session=self.session,
            conversation_text="percakapan",
            report_generator=failing_generator,
        )
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].content, "## Ringkasan\nBatuk kering.")

    def test_skips_note_when_generator_returns_empty_and_no_content(self):
        calls = [self._call(args={"title": "Pusing"})]

        def empty_generator(conv, title):
            return ""

        notes = _execute_note_calls(
            calls,
            user=self.user,
            session=self.session,
            conversation_text="percakapan",
            report_generator=empty_generator,
        )
        self.assertEqual(notes, [])
        self.assertEqual(HealthNote.objects.count(), 0)

    def test_execute_skips_empty_and_unknown_calls(self):
        calls = [
            self._call(name="some_other_tool", args={"title": "x", "content": "y"}),
            self._call(args={"title": "", "content": "konten"}),
            self._call(args={"title": "judul", "content": ""}),
        ]
        notes = _execute_note_calls(calls, user=self.user, session=None)
        self.assertEqual(notes, [])
        self.assertEqual(HealthNote.objects.count(), 0)

    def test_execute_without_user_saves_nothing(self):
        calls = [self._call(args={"title": "Judul", "content": "konten"})]
        notes = _execute_note_calls(calls, user=None, session=None)
        self.assertEqual(notes, [])
        self.assertEqual(HealthNote.objects.count(), 0)