import pytest


def test_build_selection_system_prompt():
    from pipeline.llm.base import build_selection_system_prompt
    prompt = build_selection_system_prompt("핀테크", "핀테크 규제 동향", 10)
    assert "핀테크" in prompt
    assert "10" in prompt
    assert "게임" not in prompt


def test_build_summarization_system_prompt():
    from pipeline.llm.base import build_summarization_system_prompt
    categories = [
        {"name": "IP", "description": "지식재산권"},
        {"name": "PRIVACY", "description": "개인정보"},
    ]
    prompt = build_summarization_system_prompt("의료", categories, "ko")
    assert "의료" in prompt
    assert "IP" in prompt
    assert "PRIVACY" in prompt
    assert "게임" not in prompt


def test_build_selection_user_prompt():
    from pipeline.llm.base import build_selection_user_prompt
    from pipeline.models import Article
    articles = [
        Article(title="Test Article", url="https://example.com/1", source="Test"),
    ]
    prompt = build_selection_user_prompt(articles)
    assert "Test Article" in prompt
    assert "https://example.com/1" in prompt


def test_build_summarization_user_prompt():
    from pipeline.llm.base import build_summarization_user_prompt
    prompt = build_summarization_user_prompt(
        title="Test Title",
        source="Test Source",
        url="https://example.com",
        description="Short desc",
        body="Full article body text here.",
        max_input_chars=8000,
    )
    assert "Test Title" in prompt
    assert "Full article body text here." in prompt
