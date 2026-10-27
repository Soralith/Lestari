"""Nearby hospital search using OpenStreetMap and optional Geoapify fallbacks.

Place geocoding tries a curated alias first, then (when configured) Geoapify,
Photon, and finally Nominatim. Hospital lookups use Geoapify Places when a key
is configured, then fall back to the public Overpass API across several
mirrors.

Results are cached in the database so the free services' rate limits are
respected and repeated searches stay fast on serverless deployments.
"""

import json
import logging
import math
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import GeocodeCache, HospitalSearchCache
from .places import find_known_place, normalize_query

logger = logging.getLogger(__name__)

GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PHOTON_URL = "https://photon.komoot.io/api/"
DEFAULT_OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
SEARCH_RADIUS_METERS = 30_000
QUERY_RADIUS_METERS = 32_000
EARTH_RADIUS_METERS = 6_371_000

GEOCODE_TTL = timedelta(days=30)
GEOCODE_NEGATIVE_TTL = timedelta(days=1)
HOSPITAL_TTL = timedelta(hours=12)
HOSPITAL_STALE_TTL = timedelta(days=7)

_geocode_lock = threading.Lock()
_last_nominatim_request = 0.0


class HospitalSearchError(Exception):
    """Raised when every configured upstream search service is unavailable."""


class _ProviderSkipped(Exception):
    """Internal marker for providers that are not configured."""


def _geoapify_key() -> str:
    return getattr(settings, "GEOAPIFY_API_KEY", "") or ""


def _overpass_urls() -> tuple[str, ...]:
    urls = getattr(settings, "OVERPASS_URLS", None)
    if urls:
        return tuple(urls)
    return DEFAULT_OVERPASS_URLS


def _user_agent() -> str:
    return getattr(
        settings,
        "NOMINATIM_USER_AGENT",
        "Lestari/1.0 (healthcare location finder)",
    )


def _read_json(request: urllib.request.Request, timeout: int):
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        UnicodeError,
        OSError,
    ) as exc:
        raise HospitalSearchError("upstream_unavailable") from exc


def _valid_coordinates(latitude: float, longitude: float) -> bool:
    return (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def _matches_query(label: str, query: str) -> bool:
    """Reject results that drop significant numbers from the query.

    This prevents fuzzy geocoders from resolving "SMKN 11 Bandung" to
    "SMKN 15 Bandung" or "SMKN 7 Bandung" when the exact place is missing.
    """
    query_digits = set(re.findall(r"\d+", query))
    if not query_digits:
        return True
    label_digits = set(re.findall(r"\d+", label.casefold()))
    return query_digits.issubset(label_digits)


def geocode_place(query: str) -> dict | None:
    """Resolve an Indonesian place/address, using cached and fallback providers."""
    normalized = normalize_query(query)
    if not normalized:
        return None

    known_place = find_known_place(normalized)
    if known_place:
        return known_place

    cache_key = normalized[:255]
    now = timezone.now()
    cached = GeocodeCache.objects.filter(pk=cache_key).first()
    if cached is not None:
        ttl = GEOCODE_TTL if cached.payload else GEOCODE_NEGATIVE_TTL
        if now - cached.fetched_at < ttl:
            return cached.payload or None

    responded = False
    deadline = time.monotonic() + 9
    for provider_name, provider in (
        ("geoapify", _geocode_geoapify),
        ("photon", _geocode_photon),
        ("nominatim", _geocode_nominatim),
    ):
        remaining = deadline - time.monotonic()
        if remaining < 1:
            logger.warning("Geocoding time budget exhausted before %s", provider_name)
            break
        try:
            place = provider(normalized, timeout=max(1, min(8, int(remaining))))
        except _ProviderSkipped:
            continue
        except HospitalSearchError as exc:
            logger.warning("Geocoding provider %s failed: %s", provider_name, exc)
            continue

        responded = True
        if place:
            GeocodeCache.objects.update_or_create(
                query=cache_key,
                defaults={"payload": place},
            )
            return place

    if not responded and cached is not None:
        return cached.payload or None
    if not responded:
        raise HospitalSearchError("upstream_unavailable")

    GeocodeCache.objects.update_or_create(
        query=cache_key,
        defaults={"payload": {}},
    )
    return None


def _geocode_geoapify(query: str, timeout: int = 8) -> dict | None:
    api_key = _geoapify_key()
    if not api_key:
        raise _ProviderSkipped

    url = f"{GEOAPIFY_GEOCODE_URL}?{urllib.parse.urlencode({
        'text': query,
        'filter': 'countrycode:id',
        'lang': 'id',
        'limit': 5,
        'apiKey': api_key,
    })}"
    request = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    data = _read_json(request, timeout=timeout)
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        return None

    for feature in features:
        properties = feature.get("properties") or {}
        label = properties.get("formatted") or ""
        if not _matches_query(label, query):
            continue
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        try:
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
        except (IndexError, KeyError, TypeError, ValueError):
            continue
        if not _valid_coordinates(latitude, longitude):
            continue
        return {
            "latitude": latitude,
            "longitude": longitude,
            "label": label or query,
            "source": "geoapify",
        }
    return None


def _geocode_photon(query: str, timeout: int = 8) -> dict | None:
    url = f"{PHOTON_URL}?{urllib.parse.urlencode({
        'q': query,
        'limit': 5,
        'lang': 'en',
    })}"
    request = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    data = _read_json(request, timeout=timeout)
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        return None

    for feature in features:
        properties = feature.get("properties") or {}
        if str(properties.get("countrycode", "")).upper() != "ID":
            continue
        label = ", ".join(
            part
            for part in (
                properties.get("name"),
                properties.get("street"),
                properties.get("district") or properties.get("city"),
                properties.get("state"),
                properties.get("country"),
            )
            if part
        )
        if not label or not _matches_query(label, query):
            continue
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        try:
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
        except (IndexError, KeyError, TypeError, ValueError):
            continue
        if not _valid_coordinates(latitude, longitude):
            continue
        return {
            "latitude": latitude,
            "longitude": longitude,
            "label": label,
            "source": "photon",
        }
    return None


def _geocode_nominatim(query: str, timeout: int = 8) -> dict | None:
    global _last_nominatim_request

    with _geocode_lock:
        delay = 1.0 - (time.monotonic() - _last_nominatim_request)
        if delay > 0:
            time.sleep(delay)
        _last_nominatim_request = time.monotonic()

    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode({
        'q': query,
        'format': 'jsonv2',
        'limit': 5,
        'countrycodes': 'id',
    })}"
    request = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    data = _read_json(request, timeout=timeout)
    if not isinstance(data, list):
        return None

    for item in data:
        label = item.get("display_name") or ""
        if not _matches_query(label, query):
            continue
        try:
            latitude, longitude = float(item["lat"]), float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not _valid_coordinates(latitude, longitude):
            continue
        return {
            "latitude": latitude,
            "longitude": longitude,
            "label": label or query,
            "source": "nominatim",
        }
    return None


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
    if not _valid_coordinates(lat, lon):
        return None
    return lat, lon


def _address_from_tags(tags: dict) -> str:
    return tags.get("addr:full") or ", ".join(
        part
        for part in (
            " ".join(
                filter(
                    None,
                    [tags.get("addr:street"), tags.get("addr:housenumber")],
                )
            ),
            tags.get("addr:suburb") or tags.get("addr:district"),
            tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
        )
        if part
    )


def _raw_from_osm(element: dict) -> dict | None:
    coords = _element_coordinates(element)
    tags = element.get("tags") or {}
    name = (tags.get("name") or "").strip()
    if not coords or not name:
        return None

    element_type = element.get("type")
    element_id = element.get("id")
    if element_type not in {"node", "way", "relation"} or not element_id:
        return None

    latitude, longitude = coords
    return {
        "name": name,
        "address": _address_from_tags(tags),
        "phone": tags.get("phone") or tags.get("contact:phone") or "",
        "latitude": latitude,
        "longitude": longitude,
        "source": "osm",
        "osm_type": element_type,
        "osm_id": element_id,
    }


def _overpass_query(latitude: float, longitude: float) -> str:
    lat = f"{latitude:.6f}"
    lon = f"{longitude:.6f}"
    return f"""[out:json][timeout:25];
(
  nwr["amenity"="hospital"](around:{QUERY_RADIUS_METERS},{lat},{lon});
  nwr["healthcare"="hospital"](around:{QUERY_RADIUS_METERS},{lat},{lon});
);
out center tags;"""


def _fetch_overpass_endpoint(url: str, query: str, timeout: int = 8) -> list[dict]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": _user_agent(),
        },
        method="POST",
    )
    payload = _read_json(request, timeout=timeout)
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise HospitalSearchError("invalid_upstream_response")

    hospitals = []
    for element in payload.get("elements", []):
        raw = _raw_from_osm(element)
        if raw:
            hospitals.append(raw)
    return hospitals


def _fetch_overpass(
    latitude: float,
    longitude: float,
    deadline: float | None = None,
) -> list[dict]:
    query = _overpass_query(latitude, longitude)
    responded = False
    if deadline is None:
        deadline = time.monotonic() + 12
    for url in _overpass_urls():
        remaining = deadline - time.monotonic()
        if remaining < 2:
            logger.warning("Overpass time budget exhausted before %s", url)
            break
        try:
            hospitals = _fetch_overpass_endpoint(
                url,
                query,
                timeout=max(2, min(8, int(remaining))),
            )
        except HospitalSearchError as exc:
            logger.warning("Overpass endpoint %s failed: %s", url, exc)
            continue
        responded = True
        if hospitals:
            return hospitals
    if responded:
        return []
    raise HospitalSearchError("upstream_unavailable")


def _fetch_geoapify_places(
    latitude: float,
    longitude: float,
    timeout: int = 8,
) -> list[dict]:
    api_key = _geoapify_key()
    if not api_key:
        raise _ProviderSkipped

    url = f"{GEOAPIFY_PLACES_URL}?{urllib.parse.urlencode({
        'categories': 'healthcare.hospital',
        'conditions': 'named',
        'filter': f'circle:{longitude:.6f},{latitude:.6f},{QUERY_RADIUS_METERS}',
        'limit': 100,
        'lang': 'id',
        'apiKey': api_key,
    })}"
    request = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    data = _read_json(request, timeout=timeout)
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        raise HospitalSearchError("invalid_upstream_response")

    osm_type_map = {"n": "node", "w": "way", "r": "relation"}
    hospitals = []
    for feature in features:
        properties = feature.get("properties") or {}
        name = (properties.get("name") or "").strip()
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        try:
            longitude_value = float(coordinates[0])
            latitude_value = float(coordinates[1])
        except (IndexError, KeyError, TypeError, ValueError):
            try:
                latitude_value = float(properties["lat"])
                longitude_value = float(properties["lon"])
            except (KeyError, TypeError, ValueError):
                continue
        if not name or not _valid_coordinates(latitude_value, longitude_value):
            continue

        datasource_raw = (properties.get("datasource") or {}).get("raw") or {}
        osm_type = osm_type_map.get(str(datasource_raw.get("osm_type", "")).lower())
        hospitals.append({
            "name": name,
            "address": properties.get("address_line2") or properties.get("formatted") or "",
            "phone": properties.get("phone") or "",
            "latitude": latitude_value,
            "longitude": longitude_value,
            "source": "geoapify",
            "osm_type": osm_type,
            "osm_id": datasource_raw.get("osm_id"),
        })
    return hospitals


def _fetch_hospitals(latitude: float, longitude: float) -> list[dict]:
    # Geoapify is faster and more stable than the public Overpass instances.
    # Use it first when configured; Overpass remains the keyless fallback and
    # also fills in when Geoapify returns no results. A shared deadline keeps
    # the worst case within a typical serverless function timeout.
    deadline = time.monotonic() + 8
    geoapify_hospitals = None
    try:
        geoapify_hospitals = _fetch_geoapify_places(
            latitude,
            longitude,
            timeout=max(2, min(6, int(deadline - time.monotonic()))),
        )
    except _ProviderSkipped:
        pass
    except HospitalSearchError as exc:
        logger.warning("Geoapify hospital lookup failed: %s", exc)

    if geoapify_hospitals:
        return geoapify_hospitals

    overpass_hospitals = None
    try:
        overpass_hospitals = _fetch_overpass(
            latitude,
            longitude,
            deadline=deadline,
        )
    except HospitalSearchError as exc:
        logger.warning("All Overpass endpoints failed: %s", exc)

    if overpass_hospitals:
        return overpass_hospitals
    if geoapify_hospitals is not None:
        return geoapify_hospitals
    if overpass_hospitals is not None:
        return overpass_hospitals
    raise HospitalSearchError("upstream_unavailable")


def _area_key(latitude: float, longitude: float) -> str:
    """Coarse cache key (~1 km) so exact device coordinates are never stored."""
    return f"{round(latitude, 2):.2f},{round(longitude, 2):.2f}"


def _map_url(hospital: dict) -> str:
    osm_type = hospital.get("osm_type")
    osm_id = hospital.get("osm_id")
    if osm_type in {"node", "way", "relation"} and osm_id:
        return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    return (
        "https://www.openstreetmap.org/"
        f"?mlat={hospital['latitude']:.6f}&mlon={hospital['longitude']:.6f}"
        f"#map=17/{hospital['latitude']:.6f}/{hospital['longitude']:.6f}"
    )


def _format_hospital(
    hospital: dict,
    user_lat: float,
    user_lon: float,
) -> dict | None:
    try:
        latitude = float(hospital["latitude"])
        longitude = float(hospital["longitude"])
        name = str(hospital["name"]).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if not name or not _valid_coordinates(latitude, longitude):
        return None

    distance = round(_distance_meters(user_lat, user_lon, latitude, longitude))
    if distance > SEARCH_RADIUS_METERS:
        return None

    return {
        "name": name,
        "address": hospital.get("address") or "",
        "phone": hospital.get("phone") or "",
        "distance_meters": distance,
        "latitude": latitude,
        "longitude": longitude,
        "source": hospital.get("source") or "osm",
        "osm_url": _map_url(hospital),
        "directions_url": (
            "https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route="
            f"{user_lat:.6f}%2C{user_lon:.6f}%3B{latitude:.6f}%2C{longitude:.6f}"
        ),
    }


def _name_key(name: str) -> str:
    return re.sub(r"[^\w\s]", " ", name.casefold()).strip()


def _dedupe_hospitals(hospitals: list[dict]) -> list[dict]:
    seen: list[tuple[str, float, float]] = []
    unique = []
    for hospital in hospitals:
        key = _name_key(hospital["name"])
        duplicate = any(
            key == seen_key
            and _distance_meters(
                hospital["latitude"],
                hospital["longitude"],
                seen_lat,
                seen_lon,
            ) < 300
            for seen_key, seen_lat, seen_lon in seen
        )
        if duplicate:
            continue
        seen.append((key, hospital["latitude"], hospital["longitude"]))
        unique.append(hospital)
    return unique


def find_nearby_hospitals(
    latitude: float,
    longitude: float,
    limit: int = 8,
) -> list[dict]:
    """Find named hospitals within 30 km and sort by straight-line distance."""
    area = _area_key(latitude, longitude)
    now = timezone.now()
    cached = HospitalSearchCache.objects.filter(pk=area).first()

    if cached is not None and now - cached.fetched_at < HOSPITAL_TTL:
        raw_hospitals = cached.payload
    else:
        try:
            raw_hospitals = _fetch_hospitals(latitude, longitude)
        except HospitalSearchError:
            if cached is not None and now - cached.fetched_at < HOSPITAL_STALE_TTL:
                raw_hospitals = cached.payload
            else:
                raise
        else:
            HospitalSearchCache.objects.update_or_create(
                area=area,
                defaults={"payload": raw_hospitals},
            )

    if not isinstance(raw_hospitals, list):
        raw_hospitals = []

    hospitals = []
    for raw in raw_hospitals:
        if not isinstance(raw, dict):
            continue
        hospital = _format_hospital(raw, latitude, longitude)
        if hospital:
            hospitals.append(hospital)

    hospitals.sort(key=lambda item: item["distance_meters"])
    return _dedupe_hospitals(hospitals)[:limit]
