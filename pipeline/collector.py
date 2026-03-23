"""RSS feed collection and article body extraction."""

import logging
import re
from datetime import datetime, timedelta, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

from pipeline.models import Article

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (auto-newsbriefing bot; +https://github.com/kipeum86/auto-newsbriefing)"
}


def collect_articles(config: dict) -> tuple[list[Article], list[str]]:
    """Collect articles from RSS sources. Returns (articles, failed_sources)."""
    sources = config.get("sources", {})
    days_back = config.get("collection", {}).get("days_back", 5)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    articles: list[Article] = []
    failed: list[str] = []

    for tier, tier_sources in [("a", sources.get("tier_a", [])), ("b", sources.get("tier_b", []))]:
        for src in tier_sources:
            url = src if isinstance(src, str) else src.get("url", "")
            name = src.get("name", url) if isinstance(src, dict) else url
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    pub_date = _parse_date(entry)
                    if pub_date and pub_date < cutoff:
                        continue
                    articles.append(Article(
                        title=entry.get("title", "").strip(),
                        url=entry.get("link", "").strip(),
                        source=name,
                        description=_clean_html(entry.get("summary", "")),
                        published_date=pub_date.strftime("%Y-%m-%d") if pub_date else "",
                    ))
            except Exception as e:
                if tier == "a":
                    logger.warning("tier_a feed failed: %s — %s", name, e)
                    failed.append(name)
                else:
                    logger.debug("tier_b feed skipped: %s — %s", name, e)

    logger.info("Collected %d articles from %d sources (%d failed)",
                len(articles), len(sources.get("tier_a", [])) + len(sources.get("tier_b", [])), len(failed))
    return articles, failed


def extract_body(url: str, min_content_length: int = 200) -> str:
    """Extract article body text via HTTP + BeautifulSoup."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) < min_content_length:
            return ""
        return text
    except Exception as e:
        logger.debug("Body extraction failed for %s: %s", url, e)
        return ""


def _parse_date(entry) -> datetime | None:
    """Parse feedparser date to timezone-aware datetime."""
    from time import mktime
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def _clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(strip=True)
