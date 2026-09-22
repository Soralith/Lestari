"""
Health-article aggregation for the Artikel Kesehatan page.

Articles come from the public Google News RSS search feed
(https://news.google.com/rss/search), filtered to Indonesian-language health
topics. Results are cached in the database for 10 minutes.
"""

import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime

from django.utils import timezone

from .models import ArtikelCache

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
ARTIKEL_TTL = timedelta(minutes=10)
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"


def fetch_articles(query: str = "kesehatan", limit: int = 24) -> list:
    """
    Return a list of health article dicts for a search query, cached 10 min.

    Each item: {"title", "link", "source", "published", "snippet"}.
    Returns [] on upstream failure so the page degrades gracefully.
    """
    q = query.strip() or "kesehatan"
    cache_key = q.lower()

    try:
        cached = ArtikelCache.objects.get(query=cache_key)
        if timezone.now() - cached.fetched_at < ARTIKEL_TTL:
            return cached.payload
    except ArtikelCache.DoesNotExist:
        pass

    params = urllib.parse.urlencode({"q": q, "hl": "id", "gl": "ID", "ceid": "ID:id"})
    url = f"{GOOGLE_NEWS_RSS}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            xml_bytes = resp.read()
    except Exception as exc:  # noqa: BLE001 - surface any upstream failure
        logger.warning("Google News fetch failed: %s", exc)
        return []

    items = _parse_rss(xml_bytes)[:limit]
    if items:
        ArtikelCache.objects.update_or_create(
            query=cache_key,
            defaults={"payload": items},
        )
    return items


def _parse_rss(xml_bytes: bytes) -> list:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        logger.warning("Google News returned unparseable XML.")
        return []

    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()

        if not title or not link:
            continue

        # Google appends " - SourceName" to the title; drop the duplicate.
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)]

        published = ""
        if pub:
            try:
                published = parsedate_to_datetime(pub).astimezone(
                    timezone.get_current_timezone()
                ).isoformat()
            except (TypeError, ValueError):
                published = ""

        items.append({
            "title": title,
            "link": link,
            "source": source,
            "published": published,
            "snippet": _clean_snippet(desc, source),
        })
    return items


def _clean_snippet(desc_html: str, source: str) -> str:
    text = re.sub(r"<[^>]+>", " ", desc_html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    if source and text.endswith(source):
        text = text[: -len(source)].strip()
    return text[:220]