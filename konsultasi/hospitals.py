"""Nearby hospital search using OpenStreetMap's public Overpass API."""

import json
import hashlib
import logging
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
SEARCH_RADIUS_METERS = 30_000
EARTH_RADIUS_METERS = 6_371_000
USER_AGENT = "Lestari/1.0 (healthcare location finder)"
PLACE_CACHE_SECONDS = 6 * 60 * 60

_geocode_lock = threading.Lock()
_last_geocode_request = 0.0


class HospitalSearchError(Exception):
    """Raised when the public OpenStreetMap search service is unavailable."""


def geocode_place(query: str) -> dict | None:
    """Resolve a user-entered Indonesian place/address with Nominatim."""
    global _last_geocode_request
    normalized = " ".join(query.split())
    if not normalized:
        return None

    cache_key = "lestari:osm-geocode:" + hashlib.sha256(
        normalized.casefold().encode("utf-8")
    ).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    # Nominatim's public service asks applications to keep requests to at most
    # one per second. The cache avoids repeat lookups for recently used places.
    with _geocode_lock:
        delay = 1.0 - (time.monotonic() - _last_geocode_request)
        if delay > 0:
            time.sleep(delay)
        _last_geocode_request = time.monotonic()

    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode({
        'q': normalized,
        'format': 'jsonv2',
        'limit': 1,
        'countrycodes': 'id',
    })}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            results = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeError, OSError) as exc:
        logger.warning("OpenStreetMap place lookup failed: %s", exc)
        raise HospitalSearchError("upstream_unavailable") from exc

    place = None
    if isinstance(results, list) and results:
        item = results[0]
        try:
            latitude, longitude = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError):
            latitude, longitude = float("nan"), float("nan")
        if (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            place = {
                "latitude": latitude,
                "longitude": longitude,
                "label": item.get("display_name") or normalized,
            }

    # Cache not-found results too, represented by an empty object.
    cache.set(cache_key, place or {}, PLACE_CACHE_SECONDS)
    return place


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two coordinates."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _element_coordinates(element: dict) -> tuple[float, float] | None:
    """Get a node's coordinates or an OSM way/relation's center point."""
    point = element if "lat" in element and "lon" in element else element.get("center")
    if not isinstance(point, dict):
        return None
    try:
        lat, lon = float(point["lat"]), float(point["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(lat) or not math.isfinite(lon):
        return None
    return lat, lon


def _format_hospital(element: dict, user_lat: float, user_lon: float) -> dict | None:
    coords = _element_coordinates(element)
    tags = element.get("tags") or {}
    name = (tags.get("name") or "").strip()
    if not coords or not name:
        return None

    lat, lon = coords
    address = tags.get("addr:full") or ", ".join(
        part
        for part in (
            " ".join(filter(None, [tags.get("addr:street"), tags.get("addr:housenumber")])),
            tags.get("addr:suburb") or tags.get("addr:district"),
            tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
        )
        if part
    )
    element_type = element.get("type")
    element_id = element.get("id")
    if element_type not in {"node", "way", "relation"} or not element_id:
        return None

    return {
        "name": name,
        "address": address,
        "phone": tags.get("phone") or tags.get("contact:phone") or "",
        "distance_meters": round(_distance_meters(user_lat, user_lon, lat, lon)),
        "latitude": lat,
        "longitude": lon,
        "osm_url": f"https://www.openstreetmap.org/{element_type}/{element_id}",
        "directions_url": (
            "https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route="
            f"{user_lat:.6f}%2C{user_lon:.6f}%3B{lat:.6f}%2C{lon:.6f}"
        ),
    }


def find_nearby_hospitals(latitude: float, longitude: float, limit: int = 8) -> list[dict]:
    """Find named hospitals within 30 km and sort by straight-line distance."""
    lat = f"{latitude:.6f}"
    lon = f"{longitude:.6f}"
    radius = SEARCH_RADIUS_METERS
    query = f"""[out:json][timeout:20];
(
  nwr[\"amenity\"=\"hospital\"](around:{radius},{lat},{lon});
  nwr[\"healthcare\"=\"hospital\"](around:{radius},{lat},{lon});
);
out center tags;"""
    request = urllib.request.Request(
        OVERPASS_URL,
        data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeError, OSError) as exc:
        logger.warning("OpenStreetMap hospital lookup failed: %s", exc)
        raise HospitalSearchError("upstream_unavailable") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise HospitalSearchError("invalid_upstream_response")

    hospitals = []
    for element in payload.get("elements", []):
        hospital = _format_hospital(element, latitude, longitude)
        if hospital and hospital["distance_meters"] <= SEARCH_RADIUS_METERS:
            hospitals.append(hospital)
    hospitals.sort(key=lambda item: item["distance_meters"])
    return hospitals[:limit]
