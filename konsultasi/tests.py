import io
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    ConsultationSession,
    GeocodeCache,
    HealthNote,
    HospitalSearchCache,
)
from .services import (
    _execute_hospital_tool,
    _execute_note_calls,
    get_ai_response,
)
from .hospitals import (
    HospitalSearchError,
    find_nearby_hospitals,
    geocode_place,
)
from .places import find_known_place


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

    @override_settings(GEOAPIFY_API_KEY="test-key")
    def test_page_shows_geoapify_attribution(self):
        response = self.client.get(reverse("konsultasi:rumah_sakit"))
        self.assertContains(response, "Geoapify")

    @override_settings(GEOAPIFY_API_KEY="")
    def test_page_hides_geoapify_attribution_without_key(self):
        response = self.client.get(reverse("konsultasi:rumah_sakit"))
        self.assertNotContains(response, "Geoapify")

    @patch("konsultasi.views.find_nearby_hospitals")
    def test_api_resolves_curated_school_alias(self, find_hospitals):
        find_hospitals.return_value = [{"name": "RS Contoh", "distance_meters": 900}]
        response = self.client.post(
            reverse("konsultasi:api_nearby_hospitals"),
            data=json.dumps({"query": "SMKN 11 Bandung"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("SMK Negeri 11 Bandung", response.json()["location_label"])
        find_hospitals.assert_called_once_with(-6.8902892, 107.5583826)

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

    @override_settings(GEOAPIFY_API_KEY="")
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


class KnownPlaceTests(SimpleTestCase):
    def test_smkn_11_aliases_resolve(self):
        for query in (
            "SMKN 11 Bandung",
            "SMK Negeri 11 Bandung",
            "SMK N 11 Bandung",
            "smk 11 bandung",
            "SMKN 11 Kota Bandung",
        ):
            place = find_known_place(query)
            self.assertIsNotNone(place, query)
            self.assertAlmostEqual(place["latitude"], -6.8902892)
            self.assertAlmostEqual(place["longitude"], 107.5583826)
            self.assertEqual(place["source"], "curated")

    def test_unknown_place_returns_none(self):
        self.assertIsNone(find_known_place("tempat yang tidak dikenal"))


class GeocodePlaceTests(TestCase):
    @patch("konsultasi.hospitals._geocode_nominatim")
    @patch("konsultasi.hospitals._geocode_photon")
    @patch("konsultasi.hospitals._geocode_geoapify")
    def test_curated_alias_skips_network(self, geoapify, photon, nominatim):
        place = geocode_place("SMK Negeri 11 Bandung")

        self.assertEqual(place["source"], "curated")
        geoapify.assert_not_called()
        photon.assert_not_called()
        nominatim.assert_not_called()

    @patch("konsultasi.hospitals._geocode_nominatim")
    @patch("konsultasi.hospitals._geocode_photon")
    @patch("konsultasi.hospitals._geocode_geoapify")
    def test_geoapify_result_is_cached(self, geoapify, photon, nominatim):
        geoapify.return_value = {
            "latitude": -6.2,
            "longitude": 106.8,
            "label": "Jakarta Pusat",
            "source": "geoapify",
        }

        first = geocode_place("jakarta pusat")
        second = geocode_place("jakarta pusat")

        self.assertEqual(first, second)
        geoapify.assert_called_once()
        photon.assert_not_called()
        nominatim.assert_not_called()

    @patch("konsultasi.hospitals._geocode_nominatim")
    @patch("konsultasi.hospitals._geocode_photon")
    @patch("konsultasi.hospitals._geocode_geoapify")
    def test_falls_back_to_photon(self, geoapify, photon, nominatim):
        geoapify.side_effect = HospitalSearchError("down")
        photon.return_value = {
            "latitude": -6.9,
            "longitude": 107.6,
            "label": "Bandung",
            "source": "photon",
        }

        place = geocode_place("tempat uji photon")

        self.assertEqual(place["source"], "photon")
        nominatim.assert_not_called()

    @patch("konsultasi.hospitals._geocode_nominatim")
    @patch("konsultasi.hospitals._geocode_photon")
    @patch("konsultasi.hospitals._geocode_geoapify")
    def test_falls_back_to_nominatim(self, geoapify, photon, nominatim):
        geoapify.return_value = None
        photon.return_value = None
        nominatim.return_value = {
            "latitude": -6.9,
            "longitude": 107.6,
            "label": "Bandung",
            "source": "nominatim",
        }

        place = geocode_place("tempat uji nominatim")

        self.assertEqual(place["source"], "nominatim")

    @patch("konsultasi.hospitals._geocode_nominatim")
    @patch("konsultasi.hospitals._geocode_photon")
    @patch("konsultasi.hospitals._geocode_geoapify")
    def test_negative_result_is_cached(self, geoapify, photon, nominatim):
        geoapify.return_value = None
        photon.return_value = None
        nominatim.return_value = None

        self.assertIsNone(geocode_place("tempat tidak ditemukan"))
        self.assertIsNone(geocode_place("tempat tidak ditemukan"))

        geoapify.assert_called_once()
        photon.assert_called_once()
        nominatim.assert_called_once()

    @patch("konsultasi.hospitals._geocode_nominatim")
    @patch("konsultasi.hospitals._geocode_photon")
    @patch("konsultasi.hospitals._geocode_geoapify")
    def test_all_providers_failing_raises(self, geoapify, photon, nominatim):
        geoapify.side_effect = HospitalSearchError("down")
        photon.side_effect = HospitalSearchError("down")
        nominatim.side_effect = HospitalSearchError("down")

        with self.assertRaises(HospitalSearchError):
            geocode_place("tempat tanpa koneksi")

    @patch("konsultasi.hospitals._geocode_nominatim")
    @patch("konsultasi.hospitals._geocode_photon")
    @patch("konsultasi.hospitals._geocode_geoapify")
    def test_stale_positive_result_served_on_outage(self, geoapify, photon, nominatim):
        query = "tempat cache lama"
        GeocodeCache.objects.create(
            query=query,
            payload={
                "latitude": -6.9,
                "longitude": 107.6,
                "label": "Tempat Cache Lama",
                "source": "geoapify",
            },
        )
        GeocodeCache.objects.filter(pk=query).update(
            fetched_at=timezone.now() - timedelta(days=40)
        )
        geoapify.side_effect = HospitalSearchError("down")
        photon.side_effect = HospitalSearchError("down")
        nominatim.side_effect = HospitalSearchError("down")

        place = geocode_place(query)

        self.assertEqual(place["label"], "Tempat Cache Lama")


class HospitalSearchReliabilityTests(TestCase):
    def _raw_hospital(self, latitude=0.001, longitude=0.0, name="RS Uji"):
        return {
            "name": name,
            "address": "Jalan Uji",
            "phone": "021-123",
            "latitude": latitude,
            "longitude": longitude,
            "source": "osm",
            "osm_type": "node",
            "osm_id": 1,
        }

    @override_settings(
        OVERPASS_URLS=("https://first.example", "https://second.example"),
        GEOAPIFY_API_KEY="",
    )
    @patch("konsultasi.hospitals._fetch_overpass_endpoint")
    def test_overpass_endpoint_failover(self, fetch_endpoint):
        fetch_endpoint.side_effect = [
            HospitalSearchError("down"),
            [self._raw_hospital()],
        ]

        hospitals = find_nearby_hospitals(0, 0)

        self.assertEqual([hospital["name"] for hospital in hospitals], ["RS Uji"])
        self.assertEqual(fetch_endpoint.call_count, 2)

    @override_settings(
        OVERPASS_URLS=("https://only.example",),
        GEOAPIFY_API_KEY="test-key",
    )
    @patch("konsultasi.hospitals._fetch_geoapify_places")
    @patch("konsultasi.hospitals._fetch_overpass_endpoint")
    def test_geoapify_places_is_primary(self, fetch_endpoint, fetch_geoapify):
        fetch_geoapify.return_value = [self._raw_hospital()]

        hospitals = find_nearby_hospitals(0, 0)

        self.assertEqual(hospitals[0]["name"], "RS Uji")
        fetch_geoapify.assert_called_once()
        fetch_endpoint.assert_not_called()

    @override_settings(
        OVERPASS_URLS=("https://only.example",),
        GEOAPIFY_API_KEY="test-key",
    )
    @patch("konsultasi.hospitals._fetch_geoapify_places")
    @patch("konsultasi.hospitals._fetch_overpass_endpoint")
    def test_overpass_fallback_when_geoapify_fails(self, fetch_endpoint, fetch_geoapify):
        fetch_geoapify.side_effect = HospitalSearchError("down")
        fetch_endpoint.return_value = [self._raw_hospital()]

        hospitals = find_nearby_hospitals(0, 0)

        self.assertEqual(hospitals[0]["name"], "RS Uji")
        fetch_endpoint.assert_called_once()

    @patch("konsultasi.hospitals._fetch_hospitals")
    def test_cache_recomputes_distance_for_each_request(self, fetch_hospitals):
        fetch_hospitals.return_value = [self._raw_hospital(latitude=0.01)]

        first = find_nearby_hospitals(0, 0)
        second = find_nearby_hospitals(0.004, 0)

        fetch_hospitals.assert_called_once()
        self.assertLess(second[0]["distance_meters"], first[0]["distance_meters"])

    @patch("konsultasi.hospitals._fetch_hospitals")
    def test_cache_does_not_store_exact_device_coordinates(self, fetch_hospitals):
        fetch_hospitals.return_value = [self._raw_hospital(latitude=0.01)]

        find_nearby_hospitals(-6.891234, 107.561234)

        cached = HospitalSearchCache.objects.get()
        self.assertEqual(cached.area, "-6.89,107.56")
        payload = json.dumps(cached.payload)
        self.assertNotIn("-6.891234", payload)
        self.assertNotIn("107.561234", payload)
        self.assertNotIn("directions_url", payload)

    @patch("konsultasi.hospitals._fetch_hospitals")
    def test_stale_hospital_cache_served_on_outage(self, fetch_hospitals):
        HospitalSearchCache.objects.create(
            area="-6.90,107.55",
            payload=[self._raw_hospital(latitude=-6.9, longitude=107.55)],
        )
        HospitalSearchCache.objects.filter(pk="-6.90,107.55").update(
            fetched_at=timezone.now() - timedelta(days=2)
        )
        fetch_hospitals.side_effect = HospitalSearchError("down")

        hospitals = find_nearby_hospitals(-6.901, 107.551)

        self.assertEqual(hospitals[0]["name"], "RS Uji")

    @patch("konsultasi.hospitals._fetch_hospitals")
    def test_all_sources_failing_without_cache_raises(self, fetch_hospitals):
        fetch_hospitals.side_effect = HospitalSearchError("down")

        with self.assertRaises(HospitalSearchError):
            find_nearby_hospitals(-7.1, 107.2)


class HospitalToolTests(TestCase):
    def _hospitals(self):
        return [
            {
                "name": "RS Uji",
                "address": "Jalan Uji",
                "phone": "021-123",
                "distance_meters": 900,
                "latitude": -6.9,
                "longitude": 107.6,
                "osm_url": "https://www.openstreetmap.org/node/1",
                "directions_url": "https://www.openstreetmap.org/directions",
            }
        ]

    @patch("konsultasi.services.find_nearby_hospitals")
    def test_device_location_is_used_for_generic_location(self, find_hospitals):
        find_hospitals.return_value = self._hospitals()

        result = _execute_hospital_tool(
            {"location": "lokasi saya"},
            {"latitude": -6.9, "longitude": 107.6},
        )

        find_hospitals.assert_called_once_with(-6.9, 107.6)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["used_device_location"])
        self.assertEqual(result["location_label"], "Lokasi perangkat (perkiraan)")
        self.assertNotIn("directions_url", result["hospitals"][0])

    @patch("konsultasi.services.find_nearby_hospitals")
    @patch("konsultasi.services.geocode_place")
    def test_named_location_is_geocoded(self, geocode, find_hospitals):
        geocode.return_value = {
            "latitude": -6.8902892,
            "longitude": 107.5583826,
            "label": "SMK Negeri 11 Bandung",
        }
        find_hospitals.return_value = self._hospitals()

        result = _execute_hospital_tool({"location": "SMKN 11 Bandung"})

        geocode.assert_called_once_with("SMKN 11 Bandung")
        find_hospitals.assert_called_once_with(-6.8902892, 107.5583826)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["used_device_location"])

    @patch("konsultasi.services.geocode_place", return_value=None)
    def test_unknown_location_returns_not_found(self, geocode):
        result = _execute_hospital_tool({"location": "tempat fiktif"})

        self.assertEqual(result["status"], "not_found")
        self.assertIn("tidak ditemukan", result["message"])

    @patch("konsultasi.services.find_nearby_hospitals")
    def test_missing_location_returns_location_required(self, find_hospitals):
        result = _execute_hospital_tool({})

        self.assertEqual(result["status"], "location_required")
        find_hospitals.assert_not_called()

    @patch("konsultasi.services.find_nearby_hospitals")
    def test_hospital_lookup_failure_is_reported(self, find_hospitals):
        find_hospitals.side_effect = HospitalSearchError("down")

        result = _execute_hospital_tool(
            {},
            {"latitude": -6.9, "longitude": 107.6},
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "upstream_unavailable")


class AIHospitalToolCallTests(TestCase):
    def _function_call(self, args=None):
        return SimpleNamespace(name="find_nearby_hospitals", args=args or {})

    def _client(self, responses):
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=Mock(side_effect=responses),
            )
        )
        return client

    @patch("konsultasi.services.GEMINI_API_KEY", "test-key")
    @patch("konsultasi.services._get_client")
    @patch("konsultasi.services._execute_hospital_tool")
    def test_hospital_results_are_rendered_directly(
        self,
        execute_hospital,
        get_client,
    ):
        execute_hospital.return_value = {
            "status": "ok",
            "location_label": "SMK Negeri 11 Bandung",
            "radius_meters": 30_000,
            "used_device_location": False,
            "hospitals": [
                {
                    "name": "RS Uji",
                    "address": "Jalan Uji",
                    "phone": "021-123",
                    "distance_meters": 1200,
                    "osm_url": "https://www.openstreetmap.org/node/1",
                    "directions_url": "https://www.openstreetmap.org/directions",
                }
            ],
        }
        first = SimpleNamespace(
            function_calls=[self._function_call({"location": "SMKN 11 Bandung"})],
            text=None,
            candidates=[],
        )
        client = self._client([first])
        get_client.return_value = client

        result = get_ai_response("Rumah sakit terdekat dari SMKN 11 Bandung?")

        self.assertFalse(result["error"])
        self.assertIn("RS Uji", result["text"])
        self.assertIn("1,2 km", result["text"])
        self.assertIn("[Peta]", result["text"])
        self.assertIn("/rumah-sakit/", result["text"])
        self.assertIn("119", result["text"])
        self.assertNotIn("openstreetmap.org/directions", result["text"])
        self.assertEqual(client.models.generate_content.call_count, 1)
        execute_hospital.assert_called_once_with(
            {"location": "SMKN 11 Bandung"},
            None,
        )

    @patch("konsultasi.services.GEMINI_API_KEY", "test-key")
    @patch("konsultasi.services._get_client")
    @patch("konsultasi.services._execute_hospital_tool")
    def test_device_location_is_forwarded_to_tool(
        self,
        execute_hospital,
        get_client,
    ):
        execute_hospital.return_value = {
            "status": "ok",
            "location_label": "Lokasi perangkat (perkiraan)",
            "radius_meters": 30_000,
            "used_device_location": True,
            "hospitals": [
                {
                    "name": "RS Uji",
                    "distance_meters": 900,
                }
            ],
        }
        first = SimpleNamespace(
            function_calls=[self._function_call()],
            text=None,
            candidates=[],
        )
        get_client.return_value = self._client([first])

        result = get_ai_response(
            "Rumah sakit terdekat?",
            device_location={"latitude": -6.9, "longitude": 107.6},
        )

        self.assertFalse(result["error"])
        self.assertIn("RS Uji", result["text"])
        execute_hospital.assert_called_once_with(
            {},
            {"latitude": -6.9, "longitude": 107.6},
        )
        config = get_client.return_value.models.generate_content.call_args_list[0].kwargs["config"]
        self.assertIn("coordinates are available", config.system_instruction)

    @patch("konsultasi.services.GEMINI_API_KEY", "test-key")
    @patch("konsultasi.services._get_client")
    @patch("konsultasi.services._execute_note_calls")
    def test_note_tool_still_returns_confirmation(
        self,
        execute_notes,
        get_client,
    ):
        execute_notes.return_value = [SimpleNamespace(title="Demam")]
        first = SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    name="create_health_note",
                    args={"title": "Demam"},
                )
            ],
            text=None,
            candidates=[],
        )
        get_client.return_value = self._client([first])

        result = get_ai_response("Buatkan catatan kesehatannya.")

        self.assertTrue(result["note_created"])
        self.assertIn("berhasil disimpan", result["text"])
        execute_notes.assert_called_once()

    @patch("konsultasi.services.GEMINI_API_KEY", "test-key")
    @patch("konsultasi.services._get_client")
    @patch("konsultasi.services._execute_hospital_tool")
    def test_empty_hospital_results_are_reported(
        self,
        execute_hospital,
        get_client,
    ):
        execute_hospital.return_value = {
            "status": "ok",
            "location_label": "SMK Negeri 11 Bandung",
            "radius_meters": 30_000,
            "used_device_location": False,
            "hospitals": [],
        }
        first = SimpleNamespace(
            function_calls=[self._function_call({"location": "SMKN 11 Bandung"})],
            text=None,
            candidates=[],
        )
        get_client.return_value = self._client([first])

        result = get_ai_response("Rumah sakit terdekat dari SMKN 11 Bandung?")

        self.assertFalse(result["error"])
        self.assertIn("Belum ada rumah sakit terdata", result["text"])
        self.assertIn("/rumah-sakit/", result["text"])

    @patch("konsultasi.services.GEMINI_API_KEY", "test-key")
    @patch("konsultasi.services._get_client")
    @patch("konsultasi.services._execute_hospital_tool")
    def test_emergency_banner_precedes_hospital_results(
        self,
        execute_hospital,
        get_client,
    ):
        execute_hospital.return_value = {
            "status": "ok",
            "location_label": "SMK Negeri 11 Bandung",
            "radius_meters": 30_000,
            "used_device_location": False,
            "hospitals": [{"name": "RS Uji", "distance_meters": 900}],
        }
        first = SimpleNamespace(
            function_calls=[self._function_call({"location": "SMKN 11 Bandung"})],
            text=None,
            candidates=[],
        )
        get_client.return_value = self._client([first])

        result = get_ai_response(
            "Nyeri dada hebat, rumah sakit terdekat dari SMKN 11 Bandung?"
        )

        self.assertTrue(result["is_emergency"])
        self.assertIn("kegawatdaruratan", result["text"])
        self.assertIn("119", result["text"])


class ChatHospitalApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="chat-user@example.com",
            email="chat-user@example.com",
            password="secret123",
        )
        self.client.force_login(self.user)
        self.ai_result = {
            "text": "Berikut rumah sakit terdekat.",
            "is_emergency": False,
            "note_created": False,
            "error": False,
            "error_message": "",
        }

    @patch("konsultasi.views.get_ai_response")
    def test_chat_passes_device_location(self, get_ai_response):
        get_ai_response.return_value = self.ai_result

        response = self.client.post(
            reverse("konsultasi:api_send"),
            data=json.dumps({
                "message": "Rumah sakit terdekat?",
                "latitude": -6.9,
                "longitude": 107.6,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            get_ai_response.call_args.kwargs["device_location"],
            {"latitude": -6.9, "longitude": 107.6},
        )

    @patch("konsultasi.views.get_ai_response")
    def test_chat_accepts_form_location_strings(self, get_ai_response):
        get_ai_response.return_value = self.ai_result

        response = self.client.post(
            reverse("konsultasi:api_send"),
            data={
                "message": "Rumah sakit terdekat?",
                "latitude": "-6.9",
                "longitude": "107.6",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            get_ai_response.call_args.kwargs["device_location"],
            {"latitude": -6.9, "longitude": 107.6},
        )

    @patch("konsultasi.views.get_ai_response")
    def test_chat_rejects_invalid_device_location(self, get_ai_response):
        response = self.client.post(
            reverse("konsultasi:api_send"),
            data=json.dumps({
                "message": "Rumah sakit terdekat?",
                "latitude": 91,
                "longitude": 0,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        get_ai_response.assert_not_called()


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
