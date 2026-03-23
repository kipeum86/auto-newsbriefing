import pytest


def test_canonicalize_url_removes_tracking():
    from pipeline.dedup import canonicalize_url
    url = "https://www.example.com/article?id=1&utm_source=twitter&fbclid=abc"
    result = canonicalize_url(url)
    assert "utm_source" not in result
    assert "fbclid" not in result
    assert "id=1" in result


def test_canonicalize_url_strips_www():
    from pipeline.dedup import canonicalize_url
    assert "www." not in canonicalize_url("https://www.example.com/page")


def test_extract_topic_tokens():
    from pipeline.dedup import extract_topic_tokens
    tokens = extract_topic_tokens("FTC files lawsuit against Epic Games")
    assert "ftc" in tokens
    assert "files" in tokens
    assert "lawsuit" in tokens
    assert "epic" in tokens
    assert "games" in tokens


def test_extract_topic_tokens_filters_stopwords():
    from pipeline.dedup import extract_topic_tokens
    tokens = extract_topic_tokens("the new and old way of doing things")
    assert "the" not in tokens
    assert "and" not in tokens
    assert "of" not in tokens


def test_containment_similarity():
    from pipeline.dedup import containment_similarity
    a = {"ftc", "lawsuit", "epic", "games", "loot", "box"}
    b = {"ftc", "lawsuit", "epic", "games"}
    assert containment_similarity(a, b) == 1.0

    c = {"ftc", "apple", "antitrust"}
    assert containment_similarity(a, c) < 0.5


def test_containment_similarity_empty():
    from pipeline.dedup import containment_similarity
    assert containment_similarity(set(), {"a", "b"}) == 0.0
    assert containment_similarity(set(), set()) == 0.0


def test_build_event_key():
    from pipeline.dedup import build_event_key
    event = {
        "jurisdiction": "US",
        "event_type": "litigation",
        "actors": ["Epic Games", "FTC"],
        "object": "loot box",
        "action": "filed complaint",
        "time_hint": "2026-03-15",
    }
    key1 = build_event_key(event, time_bucket="month", hash_len=16)
    assert len(key1) == 16

    event2 = {**event, "actors": ["FTC", "Epic Games"]}
    key2 = build_event_key(event2, time_bucket="month", hash_len=16)
    assert key1 == key2


def test_build_event_key_different_events():
    from pipeline.dedup import build_event_key
    e1 = {"jurisdiction": "US", "event_type": "litigation", "actors": ["FTC"],
          "object": "loot box", "action": "filed", "time_hint": "2026-03-15"}
    e2 = {"jurisdiction": "EU", "event_type": "legislation", "actors": ["EC"],
          "object": "DMA", "action": "passed", "time_hint": "2026-03-15"}
    assert build_event_key(e1) != build_event_key(e2)


def test_deduplicate_articles_removes_url_dupes():
    from pipeline.dedup import deduplicate_articles
    from pipeline.models import Article, DedupSnapshot
    articles = [
        Article(title="A", url="https://example.com/1", source="S1"),
        Article(title="B", url="https://example.com/1", source="S2"),
    ]
    snapshot = DedupSnapshot()
    result = deduplicate_articles(articles, snapshot, {})
    assert len(result) == 1
