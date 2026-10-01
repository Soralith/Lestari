import io
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import ConsultationSession, HealthNote
from .services import _execute_note_calls
from .hospitals import find_nearby_hospitals


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


class NearbyHospitalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="hospital-user@example.com",
            email="hospital-user@example.com",
            password="secret123",
        )
        self.client.force_login(self.user)

    def test_page_shows_location_search(self):
        response = self.client.get(reverse("konsultasi:rumah_sakit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gunakan lokasi saya")
        self.assertContains(response, "OpenStreetMap")

    def test_api_rejects_out_of_range_coordinates(self):
        response = self.client.post(
            reverse("konsultasi:api_nearby_hospitals"),
            data=json.dumps({"latitude": 91, "longitude": 0}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("konsultasi.views.find_nearby_hospitals")
    def test_api_returns_nearby_results_without_saving_coordinates(self, find_hospitals):
        find_hospitals.return_value = [{"name": "RS Contoh", "distance_meters": 350}]
        response = self.client.post(
            reverse("konsultasi:api_nearby_hospitals"),
            data=json.dumps({"latitude": -6.2, "longitude": 106.8}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["hospitals"][0]["name"], "RS Contoh")
        self.assertEqual(response.json()["radius_meters"], 30_000)
        find_hospitals.assert_called_once_with(-6.2, 106.8)

    @patch("konsultasi.views.find_nearby_hospitals")
    @patch("konsultasi.views.geocode_place")
    def test_api_can_search_by_place_name(self, geocode, find_hospitals):
        geocode.return_value = {
            "latitude": -6.9,
            "longitude": 107.6,
            "label": "SMKN 11 Bandung, Bandung, Jawa Barat",
        }
        find_hospitals.return_value = [{"name": "RS Contoh", "distance_meters": 900}]
        response = self.client.post(
            reverse("konsultasi:api_nearby_hospitals"),
            data=json.dumps({"query": "SMKN 11 Bandung"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["location_label"], "SMKN 11 Bandung, Bandung, Jawa Barat")
        self.assertEqual(response.json()["accuracy_meters"], None)
        geocode.assert_called_once_with("SMKN 11 Bandung")
        find_hospitals.assert_called_once_with(-6.9, 107.6)

    @patch("konsultasi.views.geocode_place", return_value=None)
    def test_api_reports_unrecognized_place(self, geocode):
        response = self.client.post(
            reverse("konsultasi:api_nearby_hospitals"),
            data=json.dumps({"query": "not a real place"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    @patch("konsultasi.hospitals.urllib.request.urlopen")
    def test_lookup_sorts_named_hospitals_by_distance(self, urlopen):
        payload = {
            "elements": [
                {
                    "type": "way", "id": 20, "center": {"lat": 0.01, "lon": 0},
                    "tags": {"name": "Rumah Sakit Lebih Jauh", "amenity": "hospital"},
                },
                {
                    "type": "node", "id": 10, "lat": 0.001, "lon": 0,
                    "tags": {"name": "Rumah Sakit Terdekat", "amenity": "hospital", "phone": "021-123"},
                },
                {"type": "node", "id": 30, "lat": 0.0005, "lon": 0, "tags": {"amenity": "hospital"}},
            ]
        }
        urlopen.return_value = io.BytesIO(json.dumps(payload).encode("utf-8"))

        hospitals = find_nearby_hospitals(0, 0)

        self.assertEqual([hospital["name"] for hospital in hospitals], [
            "Rumah Sakit Terdekat", "Rumah Sakit Lebih Jauh",
        ])
        self.assertLess(hospitals[0]["distance_meters"], hospitals[1]["distance_meters"])
        self.assertEqual(hospitals[0]["phone"], "021-123")
        self.assertIn("openstreetmap.org/node/10", hospitals[0]["osm_url"])


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

        with self.assertLogs("konsultasi.services", level="ERROR") as captured:
            notes = _execute_note_calls(
                calls,
                user=self.user,
                session=self.session,
                conversation_text="percakapan",
                report_generator=failing_generator,
            )
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].content, "## Ringkasan\nBatuk kering.")
        self.assertIn("Failed to generate health note report", captured.output[0])

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
