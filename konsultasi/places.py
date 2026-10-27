"""Curated place aliases for locations missing from OpenStreetMap.

The public geocoders used by Lestari (Nominatim, Photon, Geoapify) are all
OpenStreetMap-backed, so places that have not been mapped yet cannot be found.
Add important local landmarks here as a fast, reliable fallback. The long-term
fix is still to add the place to OpenStreetMap itself.
"""

import re
import unicodedata

# Keep this list small and accurate. Every entry resolves instantly, without
# calling any external service.
KNOWN_PLACES = (
    {
        "names": (
            "smkn 11 bandung",
            "smk 11 bandung",
            "smkn 11",
            "smk negeri 11 bandung",
            "jalan raya cilember sukaraja cicendo bandung",
            "jalan budhi cilember sukaraja cicendo bandung",
            "jalan budi cilember sukaraja cicendo bandung",
        ),
        "latitude": -6.8902892,
        "longitude": 107.5583826,
        "label": (
            "SMK Negeri 11 Bandung, Jl. Raya Cilember, Sukaraja, "
            "Cicendo, Kota Bandung"
        ),
    },
)


def normalize_query(query: str) -> str:
    """Normalize a place query so aliases match despite punctuation/spacing."""
    text = unicodedata.normalize("NFKC", str(query)).casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bjl\b", "jalan", text)
    text = re.sub(r"\bsekolah menengah kejuruan negeri\b", "smkn", text)
    text = re.sub(r"\bsmk negeri\b", "smkn", text)
    text = re.sub(r"\bsmk n\b", "smkn", text)
    return text


_ADMIN_WORDS = re.compile(r"\b(kota|kabupaten|kab|provinsi|prov)\b")


def _alias_key(query: str) -> str:
    """Normalize for alias matching without changing provider search queries."""
    text = _ADMIN_WORDS.sub(" ", normalize_query(query))
    return re.sub(r"\s+", " ", text).strip()


_ALIAS_INDEX = {
    _alias_key(alias): place
    for place in KNOWN_PLACES
    for alias in place["names"]
}


def find_known_place(query: str) -> dict | None:
    """Return a curated place for an exact normalized alias, if one exists."""
    place = _ALIAS_INDEX.get(_alias_key(query))
    if place is None:
        return None
    return {
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "label": place["label"],
        "source": "curated",
    }
