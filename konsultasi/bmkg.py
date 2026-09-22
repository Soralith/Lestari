"""
BMKG weather integration for the Cuaca page.

Location search goes through the community wrapper `bmkg.irawan.dev`
(`/v1/wilayah/search`) because BMKG's public API has no search endpoint; the
forecast itself is fetched from the official BMKG open-data API
(`api.bmkg.go.id/publik/prakiraan-cuaca`).

Both results are cached in the database so BMKG's rate limit (60 req/min/IP)
is never hit and the community wrapper isn't a hard runtime dependency.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.utils import timezone

from .models import WeatherCache, WeatherSearchCache

logger = logging.getLogger(__name__)

BMKG_FORECAST_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
BMKG_EDGE_SEARCH_URL = "https://bmkg.irawan.dev/v1/wilayah/search"

FORECAST_TTL = timedelta(minutes=10)   # BMKG updates 2x/day
SEARCH_TTL = timedelta(hours=24)       # region codes change rarely

USER_AGENT = "Lestari/1.0"


class BmkgError(Exception):
    """Raised when an upstream weather call fails."""


def _get_json(url: str, timeout: int = 12) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise BmkgError("not_found") from exc
        raise BmkgError(f"upstream_http_{exc.code}") from exc
    except Exception as exc:  # noqa: BLE001 - surface any upstream failure
        raise BmkgError("upstream_unavailable") from exc


def search_locations(query: str) -> list:
    """
    Resolve a place name to a list of BMKG-addressable villages (adm4).

    Returns a list of {"code", "name", "path"} dicts, cached for 24h.
    """
    q = query.strip()
    if not q:
        return []

    try:
        cached = WeatherSearchCache.objects.get(query=q.lower())
        if timezone.now() - cached.fetched_at < SEARCH_TTL:
            return cached.payload
    except WeatherSearchCache.DoesNotExist:
        pass

    url = f"{BMKG_EDGE_SEARCH_URL}?q={urllib.parse.quote(q)}"
    try:
        data = _get_json(url)
        results = [
            {
                "code": item["code"],
                "name": item["name"],
                "path": item.get("path", ""),
            }
            for item in data.get("data", [])
            # BMKG's forecast API only serves level-4 (village) codes.
            if item.get("level") == 4 and item.get("code")
        ]
    except (BmkgError, KeyError, TypeError) as exc:
        logger.warning("Cuaca location search failed: %s", exc)
        return []

    if results:
        WeatherSearchCache.objects.update_or_create(
            query=q.lower(),
            defaults={"payload": results},
        )
    return results


def get_forecast(adm4: str) -> dict:
    """
    Fetch a 3-day forecast for a village code from the official BMKG API.

    Returns {"location": {...}, "days": [{"date", "slots": [...]}]}, cached
    for 10 minutes. Raises BmkgError on upstream failure / unknown code.
    """
    adm4 = adm4.strip()
    try:
        cached = WeatherCache.objects.get(adm4=adm4)
        if timezone.now() - cached.fetched_at < FORECAST_TTL:
            return cached.payload
    except WeatherCache.DoesNotExist:
        pass

    url = f"{BMKG_FORECAST_URL}?adm4={urllib.parse.quote(adm4)}"
    try:
        data = _get_json(url)
    except BmkgError as exc:
        if str(exc) == "not_found":
            raise BmkgError("Data not found untuk lokasi ini.") from exc
        raise

    if not data.get("data"):
        raise BmkgError("Data not found untuk lokasi ini.")

    payload = _normalize_forecast(data)
    WeatherCache.objects.update_or_create(adm4=adm4, defaults={"payload": payload})
    return payload


def _normalize_forecast(data: dict) -> dict:
    lokasi = data.get("lokasi", {}) or {}
    location = {
        "adm4": lokasi.get("adm4", ""),
        "provinsi": lokasi.get("provinsi", ""),
        "kotkab": lokasi.get("kotkab", ""),
        "kecamatan": lokasi.get("kecamatan", ""),
        "desa": lokasi.get("desa", ""),
        "lat": lokasi.get("lat"),
        "lon": lokasi.get("lon"),
        "timezone": lokasi.get("timezone", ""),
    }

    days = []
    cuaca_days = (data.get("data") or [{}])[0].get("cuaca", [])
    for cuaca_day in cuaca_days:
        slots = []
        for s in cuaca_day or []:
            local_dt = s.get("local_datetime") or ""
            slots.append({
                "local_datetime": local_dt,
                "t": s.get("t"),
                "hu": s.get("hu"),
                "weather_desc": s.get("weather_desc"),
                "weather_desc_en": s.get("weather_desc_en"),
                "ws": s.get("ws"),
                "wd": s.get("wd"),
                "wd_to": s.get("wd_to"),
                "tcc": s.get("tcc"),
                "vs_text": s.get("vs_text"),
                "image": s.get("image"),
            })
        if slots:
            days.append({"date": slots[0]["local_datetime"][:10], "slots": slots})

    return {"location": location, "days": days}