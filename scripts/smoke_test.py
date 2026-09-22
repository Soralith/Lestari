"""Smoke test for the Lestari Konsultasi AI flow (runs in Django shell)."""
import json

import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client

from konsultasi.models import ConsultationSession, ConsultationMessage

c = Client()

# --- 1. Root serves the Lestari landing page ---
resp = c.get("/")
print("LANDING:", resp.status_code)
assert resp.status_code == 200
assert b"Konsultasi Kesehatan AI" in resp.content

# --- 1b. Login / sign up pages render ---
resp = c.get("/login/")
print("LOGIN PAGE:", resp.status_code)
assert resp.status_code == 200 and b"tab-login" in resp.content
resp = c.get("/signup/")
print("SIGNUP PAGE:", resp.status_code)
assert resp.status_code == 200 and b"signup-form" in resp.content

# --- 2. Sign up with name, email, password → logged in & redirected ---
resp = c.post(
    "/signup/",
    {
        "name": "Sora Test",
        "email": "sora@example.com",
        "password": "lestari1234",
        "confirm_password": "lestari1234",
    },
)
print("SIGNUP:", resp.status_code, "redirect:", resp.get("Location"))
assert resp.status_code == 302 and resp.get("Location") == "/konsultasi/"

# --- 3. Konsultasi index renders for the logged-in user ---
resp = c.get("/konsultasi/")
print("INDEX:", resp.status_code)
assert resp.status_code == 200
assert b"Ada keluhan kesehatan apa hari ini?" in resp.content

# --- 4. Health question → real Gemini call ---
def send(payload):
    cookie = c.cookies["csrftoken"].value
    return c.post(
        "/api/send/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=cookie,
    )

health = send({"message": "Sudah 3 hari demam 38.5C dan badan terasa lemas, apa yang mungkin terjadi?"})
health_data = health.json()
print("HEALTH STATUS:", health.status_code)
print("EMERGENCY FLAG:", health_data.get("ai_message", {}).get("is_emergency"))
text = health_data.get("ai_message", {}).get("content", "")
print("HEALTH ANSWER (first 300 chars):")
print(text[:300])
print("...")

# --- 3. Follow-up in the same session keeps context ---
followup = send({
    "message": "Kalau begitu boleh kah Paracetamol? Berapa dosisnya untuk orang dewasa?",
    "session_id": health_data["session_id"],
})
followup_text = followup.json().get("ai_message", {}).get("content", "")
print("FOLLOWUP:", followup_text[:200] if followup_text else "FAILED")

# --- 4. Off-topic question → refusal ---
offtopic = send({"message": "Rekomendasi film terbaik 2025 apa?"})
offtopic_data = offtopic.json()
print("OFFTOPIC ANSWER:")
print(offtopic_data.get("ai_message", {}).get("content", "")[:200])

# --- 5. Session listing works ---
resp = c.get("/api/sessions/")
print("SESSIONS:", resp.status_code, "count:", len(resp.json()["sessions"]))

print("\nALL SMOKE TESTS DONE")
