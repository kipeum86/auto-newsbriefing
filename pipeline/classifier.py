"""Keyword filtering, Top-N LLM selection, and article summarization/classification."""

import logging
import re

from pipeline.dedup import build_event_key
from pipeline.llm.base import (
    LLMProvider,
    build_selection_system_prompt,
    build_selection_user_prompt,
    build_summarization_system_prompt,
    build_summarization_user_prompt,
)
from pipeline.models import AIResult, Article, ProcessedArticle

logger = logging.getLogger(__name__)


def keyword_filter(
    articles: list[Article],
    keywords_config: dict,
) -> list[Article]:
    """Filter articles by include/exclude keyword regex matching."""
    include = keywords_config.get("include", [])
    exclude = keywords_config.get("exclude", [])

    if not include:
        result = list(articles)
    else:
        pattern = re.compile("|".join(re.escape(k) for k in include), re.IGNORECASE)
        result = [
            a for a in articles
            if pattern.search(f"{a.title} {a.description}")
        ]

    if exclude:
        ex_pattern = re.compile("|".join(re.escape(k) for k in exclude), re.IGNORECASE)
        result = [
            a for a in result
            if not ex_pattern.search(f"{a.title} {a.description}")
        ]

    logger.info("Keyword filter: %d → %d articles", len(articles), len(result))
    return result


def select_top_articles(
    articles: list[Article],
    llm: LLMProvider,
    config: dict,
) -> list[Article]:
    """Use LLM to select top-N most important articles."""
    domain = config.get("domain", {})
    top_n = config.get("collection", {}).get("top_n", 10)

    system = build_selection_system_prompt(
        domain.get("name", ""), domain.get("description", ""), top_n
    )
    user = build_selection_user_prompt(articles)

    try:
        result = llm.complete_json(system, user)
        selected_urls = set(result.get("selected_urls", []))
        if not selected_urls:
            logger.warning("LLM returned no URLs, using first %d", top_n)
            return articles[:top_n]
        selected = [a for a in articles if a.url in selected_urls]
        logger.info("Top-N selection: %d → %d articles", len(articles), len(selected))
        return selected or articles[:top_n]
    except Exception as e:
        logger.warning("Top-N selection failed: %s — using first %d", e, top_n)
        return articles[:top_n]


def summarize_article(
    article: Article,
    llm: LLMProvider,
    config: dict,
) -> ProcessedArticle:
    """Summarize and classify a single article via LLM."""
    domain = config.get("domain", {})
    categories = config.get("categories", [])
    language = domain.get("language", "ko")
    max_chars = config.get("llm", {}).get("max_input_chars", 8000)
    dedup_config = config.get("collection", {}).get("dedup", {})

    system = build_summarization_system_prompt(domain.get("name", ""), categories, language)
    user = build_summarization_user_prompt(
        title=article.title,
        source=article.source,
        url=article.url,
        description=article.description,
        body=article.body,
        max_input_chars=max_chars,
    )

    try:
        data = llm.complete_json(system, user)
        summary = data.get("summary", [])
        if not isinstance(summary, list) or len(summary) < 1:
            raise ValueError("Invalid summary format")

        category = normalize_category(data.get("category", "ETC"), categories)
        event = data.get("event", {})
        event_key = build_event_key(
            event,
            time_bucket=dedup_config.get("event_time_bucket", "month"),
            hash_len=dedup_config.get("hash_len", 16),
        )

        ai_result = AIResult(
            summary=summary[:3],
            category=category,
            event=event,
            event_key=event_key,
        )
    except Exception as e:
        logger.warning("Summarization failed for '%s': %s", article.title[:60], e)
        default_cat = categories[-1]["name"] if categories else "ETC"
        ai_result = build_fallback_ai_result(article.title, default_cat)

    return ProcessedArticle(article=article, ai_result=ai_result)


def build_fallback_ai_result(title: str, default_category: str) -> AIResult:
    """Build a low-confidence fallback result when LLM fails."""
    return AIResult(
        summary=[title],
        category=default_category,
        confidence="low",
    )


def normalize_category(category: str, categories: list[dict]) -> str:
    """Normalize category name to match config. Falls back to last category or ETC."""
    valid_names = [c["name"] for c in categories]
    upper = category.upper().strip()
    for name in valid_names:
        if name.upper() == upper:
            return name
    return valid_names[-1] if valid_names else "ETC"


def is_usable_result(ai_result: AIResult) -> bool:
    """Check if AI result is usable (not a fallback)."""
    return ai_result.confidence == "high" and len(ai_result.summary) >= 1
