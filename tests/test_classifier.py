import pytest


def test_keyword_filter_includes():
    from pipeline.classifier import keyword_filter
    from pipeline.models import Article
    articles = [
        Article(title="FTC files lawsuit", url="u1", source="s"),
        Article(title="Weather forecast", url="u2", source="s"),
        Article(title="New AI regulation", url="u3", source="s"),
    ]
    keywords_config = {"include": ["lawsuit", "regulation", "AI"], "exclude": []}
    result = keyword_filter(articles, keywords_config)
    assert len(result) == 2
    assert result[0].title == "FTC files lawsuit"
    assert result[1].title == "New AI regulation"


def test_keyword_filter_excludes():
    from pipeline.classifier import keyword_filter
    from pipeline.models import Article
    articles = [
        Article(title="FTC files lawsuit on gaming", url="u1", source="s"),
        Article(title="Weather lawsuit", url="u2", source="s"),
    ]
    keywords_config = {"include": ["lawsuit"], "exclude": ["weather"]}
    result = keyword_filter(articles, keywords_config)
    assert len(result) == 1
    assert result[0].title == "FTC files lawsuit on gaming"


def test_keyword_filter_empty_keywords_returns_all():
    from pipeline.classifier import keyword_filter
    from pipeline.models import Article
    articles = [Article(title="Anything", url="u1", source="s")]
    result = keyword_filter(articles, {"include": [], "exclude": []})
    assert len(result) == 1


def test_build_fallback_ai_result():
    from pipeline.classifier import build_fallback_ai_result
    result = build_fallback_ai_result("Test Title", "ETC")
    assert result.confidence == "low"
    assert len(result.summary) > 0
    assert result.category == "ETC"


def test_normalize_category():
    from pipeline.classifier import normalize_category
    cats = [{"name": "IP"}, {"name": "PRIVACY"}, {"name": "ETC"}]
    assert normalize_category("IP", cats) == "IP"
    assert normalize_category("UNKNOWN", cats) == "ETC"
    assert normalize_category("ip", cats) == "IP"
