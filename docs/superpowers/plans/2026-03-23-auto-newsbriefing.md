# auto-newsbriefing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize game-policy-briefing into a domain-agnostic RSS newsletter automation tool with multi-LLM, Google Sheets, and setup wizard.

**Architecture:** Incremental refactor of proven 1,740-line monolith into modular pipeline/ structure. Core dedup/classification logic preserved from game-policy-briefing, domain-specific values extracted to config.yaml, Notion replaced with Google Sheets, single Claude replaced with multi-LLM provider abstraction.

**Tech Stack:** Python 3.12, feedparser, requests, beautifulsoup4, gspread, google-auth, anthropic, openai, google-generativeai, pyyaml, python-dotenv

**Spec:** `docs/superpowers/specs/2026-03-23-auto-newsbriefing-design.md`
**Reference impl:** `/Users/kpsfamily/코딩 프로젝트/game-policy-briefing/news_archiver.py`
**Reference pattern:** `/Users/kpsfamily/코딩 프로젝트/parlawatch/pipeline/`

---

## Chunk 1: Foundation — Scaffolding, Config, Data Models

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `pipeline/__init__.py`
- Create: `pipeline/llm/__init__.py`
- Create: `pipeline/setup/__init__.py`
- Create: `pipeline/setup/__main__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
# LLM Providers
anthropic>=0.40.0
openai>=1.0.0
google-generativeai>=0.5.0

# RSS & Scraping
feedparser>=6.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0

# Google Sheets
gspread>=6.0.0
google-auth>=2.0.0
google-api-python-client>=2.0.0

# Config & Environment
pyyaml>=6.0
python-dotenv>=1.0.0

# Testing
pytest>=8.0.0
```

- [ ] **Step 2: Create .env.example**

```
# LLM (선택한 provider에 해당하는 키만 필요)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS=    # 서비스 계정 JSON 경로

# Email (선택)
SMTP_USER=
SMTP_PASS=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

# Logging
LOG_LEVEL=INFO
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.egg-info/
dist/
build/
.pytest_cache/
venv/
```

- [ ] **Step 4: Create package __init__.py files**

Empty `__init__.py` for `pipeline/`, `pipeline/llm/`, `pipeline/setup/`, `tests/`.

`pipeline/setup/__main__.py`:
```python
from pipeline.setup.wizard import run_wizard
import sys
run_wizard(from_example="--from-example" in sys.argv)
```

- [ ] **Step 5: Install dependencies**

Run: `pip install -r requirements.txt`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore pipeline/ tests/
git commit -m "chore: project scaffolding with dependencies and package structure"
```

---

### Task 2: Config module

**Files:**
- Create: `config.yaml`
- Create: `config.example.yaml`
- Create: `pipeline/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import pytest
import tempfile
import os
from pathlib import Path


def test_load_config_valid(tmp_path):
    """Valid YAML loads correctly."""
    from pipeline.config import load_config
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "domain:\n  name: test\n  description: test domain\n  language: ko\n"
    )
    config = load_config(str(cfg_file))
    assert config["domain"]["name"] == "test"
    assert config["domain"]["language"] == "ko"


def test_load_config_missing_file(tmp_path):
    """Missing file returns empty dict."""
    from pipeline.config import load_config
    config = load_config(str(tmp_path / "nope.yaml"))
    assert config == {}


def test_load_config_invalid_yaml(tmp_path):
    """Invalid YAML returns empty dict."""
    from pipeline.config import load_config
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("{{invalid: yaml: [")
    config = load_config(str(cfg_file))
    assert config == {}


def test_validate_config_valid():
    """Config with required fields passes validation."""
    from pipeline.config import validate_config
    config = {
        "domain": {"name": "test", "description": "test domain"},
        "llm": {"provider": "claude"},
    }
    assert validate_config(config) is True


def test_validate_config_missing_domain():
    """Config without domain fails validation."""
    from pipeline.config import validate_config
    assert validate_config({}) is False
    assert validate_config({"domain": {}}) is False
    assert validate_config({"domain": {"name": ""}}) is False


def test_get_config_with_defaults():
    """Defaults are applied for missing optional fields."""
    from pipeline.config import get_config_with_defaults
    config = {
        "domain": {"name": "test", "description": "desc"},
    }
    result = get_config_with_defaults(config)
    assert result["domain"]["language"] == "ko"
    assert result["collection"]["days_back"] == 5
    assert result["collection"]["top_n"] == 10
    assert result["collection"]["dedup"]["source_similarity_threshold"] == 0.75
    assert result["llm"]["provider"] == "claude"
    assert result["llm"]["max_input_chars"] == 8000
    assert result["email"]["enabled"] is True


def test_defaults_do_not_overwrite_user_values():
    """User-provided values are preserved over defaults."""
    from pipeline.config import get_config_with_defaults
    config = {
        "domain": {"name": "test", "description": "desc", "language": "en"},
        "collection": {"days_back": 3, "top_n": 5},
        "llm": {"provider": "openai", "model": "gpt-4o"},
    }
    result = get_config_with_defaults(config)
    assert result["domain"]["language"] == "en"
    assert result["collection"]["days_back"] == 3
    assert result["llm"]["provider"] == "openai"
    assert result["llm"]["model"] == "gpt-4o"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/kpsfamily/코딩 프로젝트/auto-newsbriefing" && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.config'`

- [ ] **Step 3: Implement pipeline/config.py**

```python
# pipeline/config.py
"""Config loading, validation, and defaults."""

import logging
import os
from copy import deepcopy
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = str(_PROJECT_ROOT / "config.yaml")

DEFAULTS = {
    "domain": {"language": "ko"},
    "categories": [],
    "keywords": {"include": [], "exclude": []},
    "sources": {"tier_a": [], "tier_b": []},
    "collection": {
        "days_back": 5,
        "top_n": 10,
        "min_content_length": 200,
        "dedup": {
            "source_similarity_threshold": 0.75,
            "cross_similarity_threshold": 0.60,
            "min_overlap_tokens": 3,
            "event_key_enabled": True,
            "event_time_bucket": "month",
            "hash_len": 16,
        },
    },
    "llm": {
        "provider": "claude",
        "model": "",
        "max_input_chars": 8000,
    },
    "email": {
        "enabled": True,
        "sender_name": "",
        "subject_prefix": "",
        "recipients": [],
    },
    "sheets": {"spreadsheet_id": ""},
    "schedule": {"cron": "7 1 * * 1,3,5", "timezone": "Asia/Seoul"},
}


def load_config(path: str | None = None) -> dict:
    """Load config.yaml. Returns empty dict on error."""
    path = path or DEFAULT_CONFIG_PATH
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config.yaml not found: %s", path)
        return {}
    except yaml.YAMLError as e:
        logger.error("config.yaml parse error: %s", e)
        return {}


def validate_config(config: dict) -> bool:
    """Check required fields exist and are non-empty."""
    domain = config.get("domain", {})
    if not domain.get("name") or not domain.get("description"):
        logger.error(
            "Setup required: set domain.name and domain.description in config.yaml"
        )
        return False
    return True


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values take precedence."""
    result = deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def get_config_with_defaults(config: dict) -> dict:
    """Apply defaults for missing optional fields."""
    return _deep_merge(DEFAULTS, config)


def setup_logging(config: dict) -> None:
    """Configure logging from config/env."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="[%(levelname)s] %(name)s: %(message)s",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/kpsfamily/코딩 프로젝트/auto-newsbriefing" && python -m pytest tests/test_config.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Create config.yaml (empty template)**

```yaml
# auto-newsbriefing configuration
# See config.example.yaml for a complete example.
# Run `python -m pipeline.setup.wizard` for guided setup.

domain:
  name: ""
  description: ""
  language: "ko"

categories: []

keywords:
  include: []
  exclude: []

sources:
  tier_a: []
  tier_b: []

llm:
  provider: "claude"
  model: ""

email:
  enabled: true
  sender_name: ""
  subject_prefix: ""
  recipients: []

sheets:
  spreadsheet_id: ""

schedule:
  cron: "7 1 * * 1,3,5"
  timezone: "Asia/Seoul"
```

- [ ] **Step 6: Create config.example.yaml (game law example)**

```yaml
# auto-newsbriefing 설정 예시: 게임 산업 법무/규제 동향
# 이 파일을 config.yaml에 복사하여 사용하세요.

domain:
  name: "게임"
  description: "게임 산업 법무/규제 동향 브리핑"
  language: "ko"

categories:
  - name: "IP"
    description: "지식재산권, 특허, 상표, 저작권 관련 뉴스"
  - name: "CONSUMER_MONETIZATION"
    description: "소비자 보호, 확률형 아이템, 환불 정책"
  - name: "CONTENT_AGE"
    description: "콘텐츠 등급, 연령 제한, 게임물관리위원회"
  - name: "PRIVACY_SECURITY"
    description: "개인정보 보호, 데이터 보안, GDPR"
  - name: "PLATFORM_PUBLISHING"
    description: "플랫폼 규제, 앱스토어 정책, 퍼블리싱 계약"
  - name: "AI_EMERGING"
    description: "AI 규제, 신기술 법규, 메타버스"
  - name: "MA_CORP_ANTITRUST"
    description: "M&A, 기업 법무, 공정거래, 독과점"
  - name: "ESPORTS_MARKETING"
    description: "e스포츠, 마케팅 규제, 광고법"
  - name: "LABOR_EMPLOYMENT"
    description: "노동법, 근로 조건, 조합 활동"
  - name: "ETC"
    description: "기타 법무/규제 동향"

keywords:
  include:
    - "lawsuit"
    - "court"
    - "patent"
    - "privacy"
    - "loot box"
    - "regulation"
    - "FTC"
    - "EU"
    - "DMA"
    - "AI"
    - "antitrust"
    - "소송"
    - "규제"
    - "개인정보"
    - "확률형"
  exclude: []

sources:
  tier_a:
    - url: "https://www.gamesindustry.biz/feed"
      name: "GamesIndustry.biz"
    - url: "https://www.gamedeveloper.com/rss.xml"
      name: "Game Developer"
    - url: "https://techcrunch.com/feed/"
      name: "TechCrunch"
  tier_b:
    - url: "https://www.gamemeca.com/rss.xml"
      name: "게임메카"

llm:
  provider: "claude"
  model: "claude-haiku-4-5-20251001"
  max_input_chars: 8000

email:
  enabled: true
  sender_name: "Game Law & Compliance Briefing"
  subject_prefix: "[게임 산업 법무/규제 동향]"
  recipients:
    - "example@company.com"

sheets:
  spreadsheet_id: ""

schedule:
  cron: "7 1 * * 1,3,5"
  timezone: "Asia/Seoul"
```

- [ ] **Step 7: Commit**

```bash
git add config.yaml config.example.yaml pipeline/config.py tests/test_config.py
git commit -m "feat: add config module with loading, validation, and defaults"
```

---

### Task 3: Data models

**Files:**
- Create: `pipeline/models.py`

- [ ] **Step 1: Create pipeline/models.py**

Port data models from `news_archiver.py`. These are pure data containers with no external dependencies.

```python
# pipeline/models.py
"""Data models for the newsletter pipeline."""

from dataclasses import dataclass, field


@dataclass
class Article:
    """A news article collected from RSS."""
    title: str
    url: str
    source: str
    description: str = ""
    published_date: str = ""
    body: str = ""


@dataclass
class AIResult:
    """LLM analysis result for an article."""
    summary: list[str] = field(default_factory=list)
    category: str = "ETC"
    event: dict = field(default_factory=dict)
    event_key: str = ""
    is_primary: bool = True
    duplicate_of: str = ""
    confidence: str = "high"  # "high" | "low"


@dataclass
class ProcessedArticle:
    """Article with AI analysis attached."""
    article: Article
    ai_result: AIResult


@dataclass
class DedupSnapshot:
    """Deduplication state loaded from history."""
    urls: set[str] = field(default_factory=set)
    canonical_urls: set[str] = field(default_factory=set)
    topic_token_sets: list[set[str]] = field(default_factory=list)
    source_topic_token_sets: dict[str, list[set[str]]] = field(default_factory=dict)
    event_keys: set[str] = field(default_factory=set)
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/models.py
git commit -m "feat: add data models (Article, AIResult, DedupSnapshot)"
```

---

## Chunk 2: LLM Provider Abstraction

### Task 4: LLM base interface

**Files:**
- Create: `pipeline/llm/base.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write tests for prompt generation**

```python
# tests/test_prompts.py
import pytest


def test_build_selection_system_prompt():
    """Selection prompt includes domain name and top_n."""
    from pipeline.llm.base import build_selection_system_prompt
    prompt = build_selection_system_prompt("핀테크", "핀테크 규제 동향", 10)
    assert "핀테크" in prompt
    assert "10" in prompt
    assert "게임" not in prompt


def test_build_summarization_system_prompt():
    """Summarization prompt includes domain, categories, and language."""
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
    """Selection user prompt lists articles."""
    from pipeline.llm.base import build_selection_user_prompt
    from pipeline.models import Article
    articles = [
        Article(title="Test Article", url="https://example.com/1", source="Test"),
    ]
    prompt = build_selection_user_prompt(articles)
    assert "Test Article" in prompt
    assert "https://example.com/1" in prompt


def test_build_summarization_user_prompt():
    """Summarization user prompt includes title and body."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: FAIL

- [ ] **Step 3: Implement pipeline/llm/base.py**

```python
# pipeline/llm/base.py
"""LLM provider interface and prompt builders."""

import json
import logging
import re
from abc import ABC, abstractmethod

from pipeline.models import Article

logger = logging.getLogger(__name__)

# --- Provider interface ---

class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return text completion."""

    def complete_json(self, system: str, user: str, max_retries: int = 3) -> dict:
        """Return parsed JSON, retrying on parse failure."""
        for attempt in range(max_retries):
            try:
                text = self.complete(system, user)
                return extract_json(text)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("JSON parse attempt %d failed: %s", attempt + 1, e)
                if attempt == max_retries - 1:
                    raise
        return {}


def extract_json(text: str) -> dict:
    """Extract JSON from text. Tries full parse first, then regex fallback."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Regex fallback: find first { ... } block
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in response")
    return json.loads(match.group())


# --- Prompt builders ---

def build_selection_system_prompt(
    domain_name: str, domain_description: str, top_n: int
) -> str:
    return f"""당신은 {domain_name} 분야의 전문 편집자입니다.
{domain_description}에 관한 뉴스 후보 목록을 받아, 가장 중요하고 시의성 있는 기사 {top_n}건을 선별합니다.

규칙:
- 동일 사건의 중복 기사는 제거하고 가장 상세한 1건만 선택
- 독립적이고 다양한 이벤트를 커버하도록 선별
- 실무적 관점에서 중요도가 높은 기사 우선

출력: 선별된 기사 URL만 JSON 배열로 반환하세요.
{{"selected_urls": ["url1", "url2", ...]}}"""


def build_selection_user_prompt(articles: list[Article]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"[{i}] {a.title}")
        lines.append(f"    URL: {a.url}")
        lines.append(f"    Source: {a.source}")
        if a.description:
            lines.append(f"    Description: {a.description[:200]}")
        lines.append("")
    return "\n".join(lines)


def build_summarization_system_prompt(
    domain_name: str,
    categories: list[dict],
    language: str = "ko",
) -> str:
    cat_lines = "\n".join(
        f"- {c['name']}: {c.get('description', '')}" for c in categories
    )
    return f"""당신은 {domain_name} 분야 전문 브리핑 AI입니다.
기사를 분석하여 요약, 카테고리, 이벤트 정보를 추출합니다.
출력 언어: {language}. 객관적이고 전문적인 어조를 사용하세요.

카테고리 ({len(categories)}개 중 1개 선택):
{cat_lines}

출력 형식 (JSON만 반환):
{{
  "summary": ["핵심 포인트 1", "핵심 포인트 2", "핵심 포인트 3"],
  "category": "CATEGORY_NAME",
  "event": {{
    "jurisdiction": "관할권 (US, EU, KR 등)",
    "event_type": "enforcement|legislation|litigation|policy|security_incident|business|other",
    "actors": ["관련 주체"],
    "object": "대상",
    "action": "행위",
    "time_hint": "YYYY-MM-DD"
  }}
}}"""


def build_summarization_user_prompt(
    title: str,
    source: str,
    url: str,
    description: str,
    body: str,
    max_input_chars: int = 8000,
) -> str:
    truncated_body = body[:max_input_chars] if body else ""
    content = truncated_body or description
    return f"""제목: {title}
출처: {source}
URL: {url}

본문:
{content}"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/llm/base.py tests/test_prompts.py
git commit -m "feat: add LLM provider interface and prompt builders"
```

---

### Task 5: LLM provider implementations

**Files:**
- Create: `pipeline/llm/claude.py`
- Create: `pipeline/llm/openai.py`
- Create: `pipeline/llm/gemini.py`
- Modify: `pipeline/llm/__init__.py`

- [ ] **Step 1: Implement Claude provider**

```python
# pipeline/llm/claude.py
"""Anthropic Claude LLM provider."""

import json
import logging
import os

import anthropic

from pipeline.llm.base import LLMProvider, extract_json

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str = ""):
        self.model = model or DEFAULT_MODEL
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = anthropic.Anthropic(api_key=api_key)

    def complete(self, system: str, user: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
```

- [ ] **Step 2: Implement OpenAI provider**

```python
# pipeline/llm/openai.py
"""OpenAI GPT LLM provider."""

import json
import logging
import os

from openai import OpenAI

from pipeline.llm.base import LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = ""):
        self.model = model or DEFAULT_MODEL
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key)

    def complete(self, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    def complete_json(self, system: str, user: str, max_retries: int = 3) -> dict:
        """Use native JSON mode for OpenAI."""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                text = response.choices[0].message.content or "{}"
                return json.loads(text)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("OpenAI JSON attempt %d failed: %s", attempt + 1, e)
                if attempt == max_retries - 1:
                    raise
        return {}
```

- [ ] **Step 3: Implement Gemini provider**

```python
# pipeline/llm/gemini.py
"""Google Gemini LLM provider."""

import json
import logging
import os

import google.generativeai as genai

from pipeline.llm.base import LLMProvider, extract_json

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = ""):
        self.model_name = model or DEFAULT_MODEL
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.model_name, system_instruction=None)
        self._system_cache = ""

    def complete(self, system: str, user: str) -> str:
        # Recreate model if system instruction changed
        if system != self._system_cache:
            self.model = genai.GenerativeModel(self.model_name, system_instruction=system)
            self._system_cache = system
        response = self.model.generate_content(
            user,
            generation_config=genai.GenerationConfig(temperature=0),
        )
        return response.text or ""

    def complete_json(self, system: str, user: str, max_retries: int = 3) -> dict:
        """Use Gemini's JSON response mime type with system_instruction."""
        if system != self._system_cache:
            self.model = genai.GenerativeModel(self.model_name, system_instruction=system)
            self._system_cache = system
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    user,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0,
                    ),
                )
                text = response.text or "{}"
                return json.loads(text)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("Gemini JSON attempt %d failed: %s", attempt + 1, e)
                if attempt == max_retries - 1:
                    raise
        return {}
```

- [ ] **Step 4: Create provider factory in __init__.py**

```python
# pipeline/llm/__init__.py
"""LLM provider factory."""

from pipeline.llm.base import LLMProvider


def create_provider(provider_name: str, model: str = "") -> LLMProvider:
    """Create LLM provider by name."""
    if provider_name == "claude":
        from pipeline.llm.claude import ClaudeProvider
        return ClaudeProvider(model)
    elif provider_name == "openai":
        from pipeline.llm.openai import OpenAIProvider
        return OpenAIProvider(model)
    elif provider_name == "gemini":
        from pipeline.llm.gemini import GeminiProvider
        return GeminiProvider(model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/llm/
git commit -m "feat: add multi-LLM providers (Claude, OpenAI, Gemini)"
```

---

## Chunk 3: Core Pipeline — Collector & Dedup

### Task 6: Collector module (RSS + body extraction)

**Files:**
- Create: `pipeline/collector.py`

- [ ] **Step 1: Implement pipeline/collector.py**

Port RSS collection and body extraction from `news_archiver.py` lines 92-270, 1225-1310. Replace hardcoded values with config parameters.

```python
# pipeline/collector.py
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
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/collector.py
git commit -m "feat: add collector module (RSS parsing + body extraction)"
```

---

### Task 7: Dedup module

**Files:**
- Create: `pipeline/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dedup.py
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
    assert containment_similarity(a, b) == 1.0  # 4/min(6,4) = 4/4

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

    # Same event, different actor order → same key
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
        Article(title="B", url="https://example.com/1", source="S2"),  # same URL
    ]
    snapshot = DedupSnapshot()
    result = deduplicate_articles(articles, snapshot, {})
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dedup.py -v`
Expected: FAIL

- [ ] **Step 3: Implement pipeline/dedup.py**

Port dedup logic from `news_archiver.py` (lines 280-600, 1448-1490). All thresholds come from config.

```python
# pipeline/dedup.py
"""3-stage deduplication: URL → topic tokens → EventKey."""

import hashlib
import logging
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pipeline.models import Article, DedupSnapshot, ProcessedArticle

logger = logging.getLogger(__name__)

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "mkt_tok", "ref", "source")

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "must", "need",
    "it", "its", "this", "that", "these", "those", "he", "she", "they",
    "we", "you", "his", "her", "their", "our", "my", "your",
    "not", "no", "nor", "so", "if", "then", "than", "too", "very",
    "just", "about", "also", "more", "some", "any", "all", "each",
    "how", "what", "when", "where", "which", "who", "why",
    "new", "says", "said", "one", "two", "get", "got", "into",
    "up", "out", "over", "after", "before", "between",
    # Korean stopwords
    "은", "는", "이", "가", "을", "를", "의", "에", "에서", "로", "으로",
    "와", "과", "도",
})

_TOKEN_RE = re.compile(r"[a-z0-9\uac00-\ud7af]{2,}", re.IGNORECASE)


def canonicalize_url(url: str) -> str:
    """Normalize URL for dedup: strip tracking params, www, trailing slash."""
    parts = urlsplit(url.strip())
    host = parts.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+", "/", parts.path).rstrip("/") or "/"
    params = [
        (k, v) for k, v in parse_qsl(parts.query)
        if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)
    ]
    params.sort()
    query = urlencode(params)
    return urlunsplit(("https", host, path, query, ""))


def extract_topic_tokens(text: str) -> set[str]:
    """Extract normalized topic tokens, filtering stopwords."""
    tokens = set(_TOKEN_RE.findall(text.lower()))
    return tokens - _STOPWORDS


def containment_similarity(a: set[str], b: set[str]) -> float:
    """Containment similarity: overlap / min(len(a), len(b))."""
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return overlap / min(len(a), len(b))


def build_event_key(
    event: dict,
    time_bucket: str = "month",
    hash_len: int = 16,
) -> str:
    """Build EventKey hash from event metadata."""
    jurisdiction = _normalize_text(event.get("jurisdiction", ""))
    event_type = _normalize_text(event.get("event_type", ""))
    actors = sorted(_normalize_text(a) for a in event.get("actors", []))
    obj = _normalize_text(event.get("object", ""))
    action = _normalize_text(event.get("action", ""))
    time_hint = event.get("time_hint", "")

    bucket = _time_to_bucket(time_hint, time_bucket)

    raw = "|".join([jurisdiction, event_type, ",".join(actors), obj, action, bucket])
    return hashlib.sha256(raw.encode()).hexdigest()[:hash_len]


def deduplicate_articles(
    articles: list[Article],
    snapshot: DedupSnapshot,
    dedup_config: dict,
) -> list[Article]:
    """Pre-LLM dedup: URL canonicalization + topic token similarity."""
    source_thresh = dedup_config.get("source_similarity_threshold", 0.75)
    cross_thresh = dedup_config.get("cross_similarity_threshold", 0.60)
    min_overlap = dedup_config.get("min_overlap_tokens", 3)

    seen_urls: set[str] = set(snapshot.canonical_urls)
    seen_tokens: list[set[str]] = list(snapshot.topic_token_sets)
    source_tokens: dict[str, list[set[str]]] = dict(snapshot.source_topic_token_sets)
    result: list[Article] = []

    for article in articles:
        canon = canonicalize_url(article.url)

        # URL dedup
        if canon in seen_urls:
            logger.debug("URL dedup: %s", article.title[:60])
            continue

        tokens = extract_topic_tokens(f"{article.title} {article.description}")
        if not tokens:
            result.append(article)
            seen_urls.add(canon)
            continue

        # Same-source topic dedup
        src_tokens = source_tokens.get(article.source, [])
        if _is_similar(tokens, src_tokens, source_thresh, min_overlap):
            logger.debug("Source-topic dedup: %s", article.title[:60])
            continue

        # Cross-source topic dedup
        if _is_similar(tokens, seen_tokens, cross_thresh, min_overlap):
            logger.debug("Cross-topic dedup: %s", article.title[:60])
            continue

        seen_urls.add(canon)
        seen_tokens.append(tokens)
        source_tokens.setdefault(article.source, []).append(tokens)
        result.append(article)

    logger.info("Dedup: %d → %d articles", len(articles), len(result))
    return result


def deduplicate_by_event_key(
    processed: list[ProcessedArticle],
) -> list[ProcessedArticle]:
    """Post-LLM dedup: unify same-event articles via EventKey."""
    seen_keys: dict[str, int] = {}
    for i, pa in enumerate(processed):
        key = pa.ai_result.event_key
        if not key:
            continue
        if key in seen_keys:
            pa.ai_result.is_primary = False
            pa.ai_result.duplicate_of = key
        else:
            seen_keys[key] = i
            pa.ai_result.is_primary = True
    return processed


def load_trend_snapshot(trends_dir: str, days: int = 30) -> DedupSnapshot:
    """Load dedup snapshot from local trends/*.txt files."""
    import os
    from datetime import timedelta, timezone

    snapshot = DedupSnapshot()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if not os.path.isdir(trends_dir):
        return snapshot

    for fname in sorted(os.listdir(trends_dir)):
        if not fname.startswith("trend_") or not fname.endswith(".txt"):
            continue
        date_str = fname.replace("trend_", "").replace(".txt", "")
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if file_date < cutoff:
            continue

        filepath = os.path.join(trends_dir, fname)
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            for block in content.split("---"):
                block = block.strip()
                if not block:
                    continue
                for line in block.split("\n"):
                    if line.startswith("URL: "):
                        url = line[5:].strip()
                        snapshot.urls.add(url)
                        snapshot.canonical_urls.add(canonicalize_url(url))
                    elif line.startswith("EventKey: "):
                        snapshot.event_keys.add(line[10:].strip())
                # Extract topic tokens from first line (title)
                first_line = block.split("\n")[0]
                if first_line.startswith("["):
                    title_part = first_line.split("]", 1)[-1].strip()
                    tokens = extract_topic_tokens(title_part)
                    if tokens:
                        snapshot.topic_token_sets.append(tokens)
        except Exception as e:
            logger.debug("Failed to parse trend file %s: %s", fname, e)

    return snapshot


def save_trend_file(
    trends_dir: str,
    processed: list[ProcessedArticle],
    run_date: str,
) -> str:
    """Save trend archive file. Returns filepath."""
    import os
    os.makedirs(trends_dir, exist_ok=True)
    filepath = os.path.join(trends_dir, f"trend_{run_date}.txt")
    lines = []
    for pa in processed:
        if not pa.ai_result.is_primary:
            continue
        lines.append(f"[{pa.ai_result.category}] {pa.article.title}")
        lines.append(f"URL: {pa.article.url}")
        summary_str = " | ".join(pa.ai_result.summary)
        lines.append(f"Summary: {summary_str}")
        if pa.ai_result.event_key:
            lines.append(f"EventKey: {pa.ai_result.event_key}")
        lines.append("---")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return filepath


# --- Internal helpers ---

def _normalize_text(text: str) -> str:
    """Lowercase, remove punctuation, normalize whitespace."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def _time_to_bucket(time_hint: str, bucket_type: str) -> str:
    """Convert date string to time bucket."""
    if not time_hint:
        return ""
    try:
        dt = datetime.strptime(time_hint[:10], "%Y-%m-%d")
        if bucket_type == "week":
            return f"{dt.year}-W{dt.isocalendar()[1]:02d}"
        return f"{dt.year}-{dt.month:02d}"
    except (ValueError, IndexError):
        return ""


def _is_similar(
    tokens: set[str],
    existing: list[set[str]],
    threshold: float,
    min_overlap: int,
) -> bool:
    """Check if tokens are similar to any existing token set."""
    for existing_tokens in existing:
        overlap = len(tokens & existing_tokens)
        if overlap >= min_overlap and containment_similarity(tokens, existing_tokens) >= threshold:
            return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dedup.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/dedup.py tests/test_dedup.py
git commit -m "feat: add 3-stage dedup module (URL, topic tokens, EventKey)"
```

---

## Chunk 4: Classifier & Keyword Filter

### Task 8: Classifier module

**Files:**
- Create: `pipeline/classifier.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_classifier.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_classifier.py -v`
Expected: FAIL

- [ ] **Step 3: Implement pipeline/classifier.py**

```python
# pipeline/classifier.py
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
        # No include keywords = pass all, then apply exclude
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_classifier.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/classifier.py tests/test_classifier.py
git commit -m "feat: add classifier module (keyword filter, Top-N, summarization)"
```

---

## Chunk 5: Output Modules — Archiver & Mailer

### Task 9: Google Sheets archiver

**Files:**
- Create: `pipeline/archiver.py`

- [ ] **Step 1: Implement pipeline/archiver.py**

```python
# pipeline/archiver.py
"""Google Sheets archiver — upload processed articles."""

import logging
import os
import time

import gspread
from google.oauth2 import service_account

from pipeline.models import DedupSnapshot, ProcessedArticle

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADERS = [
    "Date", "Title", "URL", "CanonicalURL", "Source",
    "Category", "Summary", "EventKey", "IsPrimary", "DuplicateOf", "RunDate",
]


def get_sheets_client() -> gspread.Client:
    """Create authenticated gspread client from service account."""
    creds_path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
    if not creds_path or not os.path.isfile(creds_path):
        raise FileNotFoundError(
            f"Google Sheets credentials not found: {creds_path}. "
            "Set GOOGLE_SHEETS_CREDENTIALS env var to service account JSON path."
        )
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)


def upload_to_sheets(
    processed: list[ProcessedArticle],
    spreadsheet_id: str,
    run_date: str,
) -> int:
    """Upload processed articles to Google Sheets. Returns count uploaded."""
    if not spreadsheet_id:
        logger.warning("No spreadsheet_id configured, skipping Sheets upload")
        return 0

    try:
        client = get_sheets_client()
        sheet = client.open_by_key(spreadsheet_id).sheet1
    except Exception as e:
        logger.error("Failed to open spreadsheet: %s", e)
        return 0

    from pipeline.dedup import canonicalize_url

    rows = []
    for pa in processed:
        summary_str = " | ".join(pa.ai_result.summary)
        rows.append([
            pa.article.published_date,
            pa.article.title,
            pa.article.url,
            canonicalize_url(pa.article.url),
            pa.article.source,
            pa.ai_result.category,
            summary_str,
            pa.ai_result.event_key,
            str(pa.ai_result.is_primary),
            pa.ai_result.duplicate_of,
            run_date,
        ])

    for attempt in range(5):
        try:
            sheet.append_rows(rows, value_input_option="RAW")
            logger.info("Uploaded %d articles to Sheets", len(rows))
            return len(rows)
        except gspread.exceptions.APIError as e:
            if "429" in str(e) and attempt < 4:
                wait = 2 ** attempt
                logger.warning("Sheets rate limit, retrying in %ds", wait)
                time.sleep(wait)
            else:
                logger.error("Sheets batch upload failed: %s", e)
                return 0
    return 0


def load_sheets_snapshot(
    spreadsheet_id: str,
    days: int = 30,
) -> DedupSnapshot:
    """Load dedup snapshot from Google Sheets history."""
    from datetime import datetime, timedelta, timezone
    from pipeline.dedup import canonicalize_url, extract_topic_tokens

    snapshot = DedupSnapshot()
    if not spreadsheet_id:
        return snapshot

    try:
        client = get_sheets_client()
        sheet = client.open_by_key(spreadsheet_id).sheet1
        records = sheet.get_all_records()
    except Exception as e:
        logger.warning("Failed to load Sheets snapshot: %s", e)
        return snapshot

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    for row in records:
        run_date_str = str(row.get("RunDate", ""))
        if run_date_str:
            try:
                run_date = datetime.strptime(run_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if run_date < cutoff:
                    continue
            except ValueError:
                pass

        url = str(row.get("URL", ""))
        if url:
            snapshot.urls.add(url)
            snapshot.canonical_urls.add(canonicalize_url(url))

        event_key = str(row.get("EventKey", ""))
        if event_key:
            snapshot.event_keys.add(event_key)

        title = str(row.get("Title", ""))
        if title:
            tokens = extract_topic_tokens(title)
            if tokens:
                snapshot.topic_token_sets.append(tokens)

    return snapshot
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/archiver.py
git commit -m "feat: add Google Sheets archiver with retry and snapshot loading"
```

---

### Task 10: Email mailer

**Files:**
- Create: `pipeline/mailer.py`

- [ ] **Step 1: Implement pipeline/mailer.py**

Port from `news_archiver.py` lines 1310-1462. Parameterize domain-specific text.

```python
# pipeline/mailer.py
"""HTML email generation and SMTP dispatch."""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pipeline.models import ProcessedArticle

logger = logging.getLogger(__name__)


def build_html_email(
    processed: list[ProcessedArticle],
    config: dict,
    run_date: str,
) -> str:
    """Build HTML email body grouped by category."""
    domain = config.get("domain", {})
    categories = config.get("categories", [])
    cat_names = [c["name"] for c in categories] if categories else []

    # Group by category
    by_category: dict[str, list[ProcessedArticle]] = {}
    for pa in processed:
        if not pa.ai_result.is_primary:
            continue
        cat = pa.ai_result.category
        by_category.setdefault(cat, []).append(pa)

    # Sort categories by config order
    ordered_cats = [c for c in cat_names if c in by_category]
    for c in by_category:
        if c not in ordered_cats:
            ordered_cats.append(c)

    article_count = sum(len(v) for v in by_category.values())

    sections = []
    for cat in ordered_cats:
        items = by_category[cat]
        item_html = []
        for pa in items:
            summary_bullets = "".join(
                f"<li>{s}</li>" for s in pa.ai_result.summary
            )
            item_html.append(f"""
            <div style="margin-bottom:16px;padding:12px;background:#f8f9fa;border-radius:6px;">
                <a href="{pa.article.url}" style="color:#1a73e8;font-weight:bold;text-decoration:none;">
                    {pa.article.title}
                </a>
                <div style="color:#666;font-size:12px;margin:4px 0;">
                    {pa.article.source} · {pa.article.published_date}
                </div>
                <ul style="margin:8px 0 0;padding-left:20px;color:#333;">
                    {summary_bullets}
                </ul>
            </div>""")

        sections.append(f"""
        <div style="margin-bottom:24px;">
            <h2 style="color:#1a1a2e;border-bottom:2px solid #1a73e8;padding-bottom:4px;font-size:16px;">
                {cat} ({len(items)})
            </h2>
            {"".join(item_html)}
        </div>""")

    domain_name = domain.get("name", "")
    description = domain.get("description", "")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:700px;margin:0 auto;padding:20px;">
    <div style="background:#1a1a2e;color:white;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
        <h1 style="margin:0;font-size:20px;">{description}</h1>
        <p style="margin:4px 0 0;opacity:0.8;">{run_date} · {article_count}건</p>
    </div>
    <div style="padding:20px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">
        {"".join(sections)}
    </div>
    <p style="text-align:center;color:#999;font-size:11px;margin-top:16px;">
        Powered by auto-newsbriefing
    </p>
</body>
</html>"""


def send_email(
    html_body: str,
    config: dict,
    run_date: str,
) -> bool:
    """Send HTML email via SMTP. Returns True on success."""
    email_config = config.get("email", {})
    if not email_config.get("enabled", True):
        logger.info("Email disabled in config")
        return False

    recipients = email_config.get("recipients", [])
    if not recipients:
        logger.warning("No email recipients configured")
        return False

    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP credentials not set, skipping email")
        return False

    sender_name = email_config.get("sender_name", "Auto News Briefing")
    prefix = email_config.get("subject_prefix", "[News Briefing]")
    article_count = html_body.count("background:#f8f9fa")  # rough count
    subject = f"{prefix} {run_date} ({article_count}건)"

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{sender_name} <{smtp_user}>"
    msg["To"] = smtp_user
    msg["Bcc"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            all_recipients = [smtp_user] + recipients
            server.sendmail(smtp_user, all_recipients, msg.as_string())
        logger.info("Email sent to %d recipients", len(recipients))
        return True
    except (TimeoutError, ConnectionRefusedError, smtplib.SMTPException) as e:
        logger.error("Email send failed: %s", e)
        return False
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/mailer.py
git commit -m "feat: add email mailer with HTML template and SMTP dispatch"
```

---

## Chunk 6: Setup Wizard

### Task 11: API validator

**Files:**
- Create: `pipeline/setup/validator.py`

- [ ] **Step 1: Implement pipeline/setup/validator.py**

```python
# pipeline/setup/validator.py
"""Validate API keys for external services."""

import logging
import os

logger = logging.getLogger(__name__)


def validate_anthropic(api_key: str) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=10,
            messages=[{"role": "user", "content": "test"}],
        )
        return {"status": "ok", "message": "Anthropic API 연결 성공"}
    except Exception as e:
        return {"status": "error", "message": f"Anthropic API 오류: {e}"}


def validate_openai(api_key: str) -> dict:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        client.chat.completions.create(
            model="gpt-4o-mini", max_tokens=10,
            messages=[{"role": "user", "content": "test"}],
        )
        return {"status": "ok", "message": "OpenAI API 연결 성공"}
    except Exception as e:
        return {"status": "error", "message": f"OpenAI API 오류: {e}"}


def validate_gemini(api_key: str) -> dict:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        model.generate_content("test")
        return {"status": "ok", "message": "Gemini API 연결 성공"}
    except Exception as e:
        return {"status": "error", "message": f"Gemini API 오류: {e}"}


def validate_google_sheets(creds_path: str, spreadsheet_id: str = "") -> dict:
    try:
        import gspread
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        if spreadsheet_id:
            client.open_by_key(spreadsheet_id)
        return {"status": "ok", "message": "Google Sheets API 연결 성공"}
    except Exception as e:
        return {"status": "error", "message": f"Google Sheets 오류: {e}"}


def validate_smtp(user: str, password: str, host: str = "smtp.gmail.com", port: int = 587) -> dict:
    try:
        import smtplib
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
        return {"status": "ok", "message": "SMTP 연결 성공"}
    except Exception as e:
        return {"status": "error", "message": f"SMTP 오류: {e}"}


def validate_all(provider: str = "claude", **kwargs) -> dict:
    """Validate all configured services. Returns {service: {status, message}}."""
    results = {}

    # LLM provider
    llm_validators = {
        "claude": ("ANTHROPIC_API_KEY", validate_anthropic),
        "openai": ("OPENAI_API_KEY", validate_openai),
        "gemini": ("GOOGLE_API_KEY", validate_gemini),
    }
    if provider in llm_validators:
        env_key, validator = llm_validators[provider]
        api_key = kwargs.get("llm_key") or os.environ.get(env_key, "")
        if api_key:
            results["llm"] = validator(api_key)
        else:
            results["llm"] = {"status": "skip", "message": f"{env_key} not set"}

    # Google Sheets
    creds = kwargs.get("sheets_creds") or os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
    if creds:
        results["sheets"] = validate_google_sheets(creds, kwargs.get("spreadsheet_id", ""))
    else:
        results["sheets"] = {"status": "skip", "message": "GOOGLE_SHEETS_CREDENTIALS not set"}

    # SMTP
    smtp_user = kwargs.get("smtp_user") or os.environ.get("SMTP_USER", "")
    smtp_pass = kwargs.get("smtp_pass") or os.environ.get("SMTP_PASS", "")
    if smtp_user and smtp_pass:
        results["smtp"] = validate_smtp(smtp_user, smtp_pass)
    else:
        results["smtp"] = {"status": "skip", "message": "SMTP credentials not set"}

    return results
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/setup/validator.py
git commit -m "feat: add API key validator for LLM, Sheets, and SMTP"
```

---

### Task 12: Sheets creator

**Files:**
- Create: `pipeline/setup/sheets_creator.py`

- [ ] **Step 1: Implement pipeline/setup/sheets_creator.py**

```python
# pipeline/setup/sheets_creator.py
"""Auto-create Google Sheets spreadsheet with proper headers."""

import logging
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

HEADERS = [
    "Date", "Title", "URL", "CanonicalURL", "Source",
    "Category", "Summary", "EventKey", "IsPrimary", "DuplicateOf", "RunDate",
]


def create_spreadsheet(
    title: str = "auto-newsbriefing",
    share_email: str = "",
) -> str:
    """Create a new spreadsheet with headers. Returns spreadsheet_id."""
    creds_path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
    if not creds_path:
        raise FileNotFoundError("GOOGLE_SHEETS_CREDENTIALS env var not set")

    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # Create spreadsheet
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "Briefings"}}],
    }
    result = sheets_service.spreadsheets().create(body=body).execute()
    spreadsheet_id = result["spreadsheetId"]
    logger.info("Created spreadsheet: %s", spreadsheet_id)

    # Write headers
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Briefings!A1",
        valueInputOption="RAW",
        body={"values": [HEADERS]},
    ).execute()

    # Share if email provided
    if share_email:
        try:
            drive_service.permissions().create(
                fileId=spreadsheet_id,
                body={"type": "user", "role": "writer", "emailAddress": share_email},
                sendNotificationEmail=False,
            ).execute()
            logger.info("Shared spreadsheet with %s", share_email)
        except Exception as e:
            logger.warning("Failed to share spreadsheet: %s", e)

    return spreadsheet_id
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/setup/sheets_creator.py
git commit -m "feat: add Sheets creator with auto headers and sharing"
```

---

### Task 13: Setup wizard

**Files:**
- Create: `pipeline/setup/wizard.py`

- [ ] **Step 1: Implement pipeline/setup/wizard.py**

```python
# pipeline/setup/wizard.py
"""Interactive setup wizard for auto-newsbriefing."""

import os
import sys

import yaml


def run_wizard(config_path: str = "config.yaml", from_example: bool = False):
    """Interactive CLI wizard to generate config.yaml."""
    print("\n=== auto-newsbriefing Setup Wizard ===\n")

    config: dict = {}

    if from_example and os.path.isfile("config.example.yaml"):
        with open("config.example.yaml", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        print("Loaded config.example.yaml as starting point.\n")

    # Step 1: Validate API keys
    print("--- Step 1: API Key Validation ---")
    provider = _ask("LLM provider (claude/openai/gemini)", default="claude")
    config.setdefault("llm", {})["provider"] = provider
    _validate_keys(provider)

    # Step 2: Domain
    print("\n--- Step 2: Domain Settings ---")
    name = _ask("Domain name (e.g., 핀테크, 의료, 게임)")
    desc = _ask("Domain description (e.g., 핀테크 규제 동향 브리핑)")
    lang = _ask("Output language", default="ko")
    config["domain"] = {"name": name, "description": desc, "language": lang}

    # Step 3: Categories
    print("\n--- Step 3: Categories ---")
    print("Enter categories (empty name to stop):")
    categories = []
    while True:
        cat_name = _ask(f"  Category {len(categories)+1} name", allow_empty=True)
        if not cat_name:
            break
        cat_desc = _ask(f"  Category {len(categories)+1} description", allow_empty=True)
        categories.append({"name": cat_name, "description": cat_desc})
    config["categories"] = categories

    # Step 4: Keywords
    print("\n--- Step 4: Keywords ---")
    include = _ask("Include keywords (comma-separated)", allow_empty=True)
    exclude = _ask("Exclude keywords (comma-separated)", allow_empty=True)
    config["keywords"] = {
        "include": [k.strip() for k in include.split(",") if k.strip()] if include else [],
        "exclude": [k.strip() for k in exclude.split(",") if k.strip()] if exclude else [],
    }

    # Step 5: RSS Sources
    print("\n--- Step 5: RSS Sources ---")
    print("Enter tier_a sources (reliable, empty URL to stop):")
    tier_a = _collect_sources()
    print("Enter tier_b sources (unreliable, empty URL to stop):")
    tier_b = _collect_sources()
    config["sources"] = {"tier_a": tier_a, "tier_b": tier_b}

    # Step 6: Google Sheets
    print("\n--- Step 6: Google Sheets ---")
    create_sheet = _ask("Auto-create spreadsheet? (y/n)", default="y")
    if create_sheet.lower() == "y":
        try:
            from pipeline.setup.sheets_creator import create_spreadsheet
            share = _ask("Share with email (optional)", allow_empty=True)
            sheet_title = f"auto-newsbriefing: {name}"
            sid = create_spreadsheet(title=sheet_title, share_email=share)
            config.setdefault("sheets", {})["spreadsheet_id"] = sid
            print(f"  Spreadsheet created: {sid}")
        except Exception as e:
            print(f"  Failed to create spreadsheet: {e}")
            sid = _ask("Enter spreadsheet_id manually", allow_empty=True)
            config.setdefault("sheets", {})["spreadsheet_id"] = sid
    else:
        sid = _ask("Enter spreadsheet_id", allow_empty=True)
        config.setdefault("sheets", {})["spreadsheet_id"] = sid

    # Step 7: Email recipients
    print("\n--- Step 7: Email Recipients ---")
    recipients_str = _ask("Recipient emails (comma-separated)", allow_empty=True)
    recipients = [r.strip() for r in recipients_str.split(",") if r.strip()] if recipients_str else []
    sender = _ask("Sender name", default="Auto News Briefing")
    prefix = _ask("Subject prefix", default=f"[{name} Briefing]")
    config["email"] = {
        "enabled": bool(recipients),
        "sender_name": sender,
        "subject_prefix": prefix,
        "recipients": recipients,
    }

    # Step 8: Save
    print("\n--- Step 8: Save ---")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\nConfig saved to {config_path}")
    print("Run `python main.py --dry-run` to test your setup.\n")


def _ask(prompt: str, default: str = "", allow_empty: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default:
            return default
        if value or allow_empty:
            return value
        print("  This field is required.")


def _collect_sources() -> list[dict]:
    sources = []
    while True:
        url = _ask(f"  Source {len(sources)+1} URL", allow_empty=True)
        if not url:
            break
        name = _ask(f"  Source {len(sources)+1} name", allow_empty=True) or url
        sources.append({"url": url, "name": name})
    return sources


def _validate_keys(provider: str):
    try:
        from pipeline.setup.validator import validate_all
        results = validate_all(provider=provider)
        for service, result in results.items():
            status = result["status"]
            icon = "✓" if status == "ok" else ("⚠" if status == "skip" else "✗")
            print(f"  {icon} {service}: {result['message']}")
    except Exception as e:
        print(f"  Validation skipped: {e}")


if __name__ == "__main__":
    from_example = "--from-example" in sys.argv
    run_wizard(from_example=from_example)
```

- [ ] **Step 2: Create pipeline/setup/__init__.py**

Empty file (already created in Task 1, verify it exists).

- [ ] **Step 3: Commit**

```bash
git add pipeline/setup/wizard.py
git commit -m "feat: add interactive setup wizard"
```

---

## Chunk 7: Main Entrypoint, CI/CD, Docs

### Task 14: Main entrypoint

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement main.py**

Orchestrate the full pipeline, referencing all modules.

```python
# main.py
"""auto-newsbriefing — domain-agnostic RSS newsletter automation."""

import argparse
import logging
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from pipeline.config import (
    DEFAULT_CONFIG_PATH,
    get_config_with_defaults,
    load_config,
    setup_logging,
    validate_config,
)

load_dotenv()

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="auto-newsbriefing")
    parser.add_argument("--dry-run", action="store_true", help="Skip Sheets upload and email")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM calls")
    parser.add_argument("--max-items", type=int, default=0, help="Limit articles processed")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config file path")
    return parser.parse_args()


def main():
    args = parse_args()

    # Load & validate config
    raw_config = load_config(args.config)
    if not validate_config(raw_config):
        print("Run `python -m pipeline.setup.wizard` to configure.")
        sys.exit(1)
    config = get_config_with_defaults(raw_config)
    setup_logging(config)

    domain = config["domain"]
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    llm = None  # initialized lazily when needed
    logger.info("=== auto-newsbriefing: %s (%s) ===", domain["description"], run_date)

    # [1/6] Collect RSS
    from pipeline.collector import collect_articles, extract_body
    articles, failed = collect_articles(config)
    if not articles:
        logger.warning("No articles collected. Exiting.")
        return
    logger.info("[1/6] Collected %d articles (%d sources failed)", len(articles), len(failed))

    # [2/6] Pre-LLM dedup
    from pipeline.dedup import (
        deduplicate_articles,
        deduplicate_by_event_key,
        load_trend_snapshot,
        save_trend_file,
    )
    from pipeline.models import DedupSnapshot

    trends_dir = str(__import__("pathlib").Path(__file__).parent / "trends")
    trend_snapshot = load_trend_snapshot(trends_dir)

    if not args.dry_run:
        from pipeline.archiver import load_sheets_snapshot
        sheets_snapshot = load_sheets_snapshot(config.get("sheets", {}).get("spreadsheet_id", ""))
        # Merge snapshots
        trend_snapshot.urls |= sheets_snapshot.urls
        trend_snapshot.canonical_urls |= sheets_snapshot.canonical_urls
        trend_snapshot.topic_token_sets.extend(sheets_snapshot.topic_token_sets)
        trend_snapshot.event_keys |= sheets_snapshot.event_keys

    dedup_config = config.get("collection", {}).get("dedup", {})
    articles = deduplicate_articles(articles, trend_snapshot, dedup_config)
    logger.info("[2/6] After dedup: %d articles", len(articles))

    # [3/6] Keyword filter + Top-N selection
    from pipeline.classifier import (
        is_usable_result,
        keyword_filter,
        select_top_articles,
        summarize_article,
    )

    articles = keyword_filter(articles, config.get("keywords", {}))

    if not args.no_llm and not args.max_items:
        from pipeline.llm import create_provider  # noqa: E402
        llm = create_provider(
            config["llm"]["provider"],
            config["llm"].get("model", ""),
        )
        articles = select_top_articles(articles, llm, config)
    elif args.max_items:
        articles = articles[: args.max_items]
    else:
        top_n = config.get("collection", {}).get("top_n", 10)
        articles = articles[:top_n]

    logger.info("[3/6] After selection: %d articles", len(articles))

    # [4/6] Body extraction + Summarization
    min_len = config.get("collection", {}).get("min_content_length", 200)
    for article in articles:
        body = extract_body(article.url, min_len)
        article.body = body or article.description

    processed = []
    if not args.no_llm:
        if llm is None:
            from pipeline.llm import create_provider
            llm = create_provider(config["llm"]["provider"], config["llm"].get("model", ""))
        for article in articles:
            pa = summarize_article(article, llm, config)
            processed.append(pa)
        # Filter low-confidence
        processed = [pa for pa in processed if is_usable_result(pa.ai_result)]
    else:
        from pipeline.models import AIResult, ProcessedArticle
        default_cat = config.get("categories", [{}])[-1].get("name", "ETC") if config.get("categories") else "ETC"
        for article in articles:
            pa = ProcessedArticle(
                article=article,
                ai_result=AIResult(summary=[article.title], category=default_cat, confidence="low"),
            )
            processed.append(pa)

    logger.info("[4/6] Summarized %d articles", len(processed))

    # [5/6] Post-summary dedup (EventKey)
    if dedup_config.get("event_key_enabled", True) and not args.no_llm:
        processed = deduplicate_by_event_key(processed)
    primary = [pa for pa in processed if pa.ai_result.is_primary]
    logger.info("[5/6] After EventKey dedup: %d primary articles", len(primary))

    if not primary:
        logger.info("No primary articles to report. Done.")
        return

    # [6/6] Output
    if not args.dry_run:
        # Google Sheets
        from pipeline.archiver import upload_to_sheets
        upload_to_sheets(processed, config.get("sheets", {}).get("spreadsheet_id", ""), run_date)

        # Email
        from pipeline.mailer import build_html_email, send_email
        if config.get("email", {}).get("enabled", True):
            html = build_html_email(processed, config, run_date)
            send_email(html, config, run_date)

    # Trend archive
    save_trend_file(trends_dir, processed, run_date)
    logger.info("[6/6] Done. %d primary articles briefed.", len(primary))

    # Dry-run summary
    if args.dry_run:
        print(f"\n--- DRY RUN SUMMARY ({run_date}) ---")
        for pa in primary:
            print(f"\n[{pa.ai_result.category}] {pa.article.title}")
            print(f"  Source: {pa.article.source}")
            for s in pa.ai_result.summary:
                print(f"  - {s}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add main.py entrypoint with full pipeline orchestration"
```

---

### Task 15: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/schedule.yml`

- [ ] **Step 1: Create workflow**

```yaml
# .github/workflows/schedule.yml
name: Auto News Briefing

on:
  schedule:
    - cron: '7 1 * * 1,3,5'
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: briefing
  cancel-in-progress: false

jobs:
  briefing:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: pip install -r requirements.txt

      - name: Decode Google Sheets credentials
        run: echo "$GOOGLE_SHEETS_CREDENTIALS_B64" | base64 -d > /tmp/gsheets-creds.json
        env:
          GOOGLE_SHEETS_CREDENTIALS_B64: ${{ secrets.GOOGLE_SHEETS_CREDENTIALS_B64 }}

      - run: python main.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          GOOGLE_SHEETS_CREDENTIALS: /tmp/gsheets-creds.json
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          TZ: ${{ vars.BRIEFING_TZ || 'Asia/Seoul' }}

      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "auto: briefing ${{ github.run_id }}"
          file_pattern: "trends/*.txt"
```

- [ ] **Step 2: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/schedule.yml
git commit -m "ci: add GitHub Actions workflow for scheduled briefings"
```

---

### Task 16: CLAUDE.md + README

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Create CLAUDE.md**

```markdown
# auto-newsbriefing

Domain-agnostic RSS newsletter automation tool.

## Quick Start

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in API keys
3. `python -m pipeline.setup.wizard` to configure
4. `python main.py --dry-run` to test
5. `python main.py` to run

## Development

- Tests: `python -m pytest tests/ -v`
- Config: `config.yaml` (user settings), `config.example.yaml` (reference)
- Logs: Set `LOG_LEVEL=DEBUG` for verbose output

## Architecture

```
main.py → pipeline/config.py → collector.py → dedup.py → classifier.py → archiver.py → mailer.py
                                                              ↓
                                                         pipeline/llm/ (claude|openai|gemini)
```

## CLI

- `python main.py` — full run
- `python main.py --dry-run` — no Sheets/email
- `python main.py --no-llm` — no LLM calls
- `python main.py --max-items 3` — limit batch
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with quick start and architecture"
```

---

### Task 17: Final integration test

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (config: 6, dedup: 9, prompts: 4, classifier: 5 = 24 total)

- [ ] **Step 2: Run dry-run smoke test**

Create a minimal test config and verify the pipeline runs end-to-end without external services.

Run: `python main.py --dry-run --no-llm --config config.example.yaml`
Expected: Runs without errors (may show 0 articles if no RSS accessible)

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: integration test fixes"
```

---

## Summary

| Chunk | Tasks | Files | Tests |
|-------|-------|-------|-------|
| 1: Foundation | 1-3 | scaffolding, config.py, models.py, config.yaml, config.example.yaml | test_config.py (6) |
| 2: LLM | 4-5 | llm/base.py, claude.py, openai.py, gemini.py | test_prompts.py (4) |
| 3: Pipeline Core | 6-7 | collector.py, dedup.py | test_dedup.py (9) |
| 4: Classifier | 8 | classifier.py | test_classifier.py (5) |
| 5: Output | 9-10 | archiver.py, mailer.py | — |
| 6: Setup | 11-13 | validator.py, sheets_creator.py, wizard.py | — |
| 7: Integration | 14-17 | main.py, schedule.yml, CLAUDE.md | smoke test |

**Total: 17 tasks, ~20 files, 24 unit tests, 17 commits**
