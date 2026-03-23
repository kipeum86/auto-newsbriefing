# auto-newsbriefing Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Origin:** game-policy-briefing (kipeum86/game-policy-briefing) 범용화
**Approach:** Incremental Refactor — 검증된 파이프라인 보존 + 모듈화 + 범용화

---

## 1. 프로젝트 개요

**auto-newsbriefing** — 어떤 도메인이든 RSS 기반 뉴스를 수집, AI 분류/요약, Google Sheets 아카이브, 이메일 발송까지 자동화하는 범용 뉴스레터 프로그램.

### 핵심 원칙

- game-policy-briefing의 검증된 파이프라인(3단계 중복제거, EventKey, Top-N 선별) 보존
- 도메인 특화 요소(카테고리, 키워드, 프롬프트, 소스)를 전부 config로 분리
- Setup wizard로 첫 사용자도 쉽게 시작
- 멀티 LLM 지원 (Claude, OpenAI, Gemini)
- Notion → Google Sheets 교체

### 원본 대비 변경점

| 항목 | game-policy-briefing | auto-newsbriefing |
|------|---------------------|-------------------|
| 도메인 | 게임 산업 법무 고정 | config로 자유 설정 |
| 데이터 저장 | Notion DB | Google Sheets |
| LLM | Claude 전용 | Claude / OpenAI / Gemini |
| 코드 구조 | 단일 파일 1,740줄 | pipeline/ 모듈 분리 |
| 설정 | 하드코딩 + 부분 config | 전부 config.yaml |
| 초기 설정 | 수동 | Setup wizard |
| 스케줄 | workflow 하드코딩 | config에서 설정 |

---

## 2. 프로젝트 구조

```
auto-newsbriefing/
├── main.py                          # 엔트리포인트
├── config.yaml                      # 빈 템플릿 (사용자가 채움)
├── config.example.yaml              # 게임 법무 예시 (참고용)
├── requirements.txt
├── .env.example
├── .github/workflows/schedule.yml
├── CLAUDE.md
├── pipeline/
│   ├── __init__.py
│   ├── config.py                    # config 로딩 + 검증
│   ├── collector.py                 # RSS 수집 + 본문 추출
│   ├── dedup.py                     # 3단계 중복제거 (URL/토픽토큰/EventKey)
│   ├── classifier.py                # Top-N 선별 + 분류/요약
│   ├── archiver.py                  # Google Sheets 업로드
│   ├── mailer.py                    # Gmail SMTP 발송
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                  # LLM 프로바이더 인터페이스
│   │   ├── claude.py                # Anthropic Claude
│   │   ├── openai.py                # OpenAI GPT
│   │   └── gemini.py                # Google Gemini
│   └── setup/
│       ├── __init__.py
│       ├── wizard.py                # 대화형 초기 설정
│       ├── sheets_creator.py        # Google Sheets 자동 생성
│       └── validator.py             # API 키 검증
├── trends/                          # 로컬 아카이브 (자동 생성)
└── tests/
    ├── test_config.py
    ├── test_dedup.py
    ├── test_classifier.py
    └── test_prompts.py
```

### 모듈 역할

| 모듈 | 역할 |
|------|------|
| `config.py` | config.yaml 로드, 필수값 검증, 기본값 적용 |
| `collector.py` | RSS 피드 파싱, 날짜 필터, 본문 스크래핑 (BeautifulSoup) |
| `dedup.py` | URL 정규화, 토픽 토큰 유사도, EventKey 핑거프린팅 |
| `classifier.py` | 키워드 사전 필터, LLM Top-N 선별, 개별 요약/분류 |
| `archiver.py` | Google Sheets API로 결과 기록 |
| `mailer.py` | HTML 이메일 생성 + Gmail SMTP BCC 발송 |
| `llm/base.py` | LLM 프로바이더 추상 인터페이스 |
| `llm/claude.py` | Anthropic Claude 구현체 |
| `llm/openai.py` | OpenAI GPT 구현체 |
| `llm/gemini.py` | Google Gemini 구현체 |
| `setup/wizard.py` | 대화형 초기 설정 CLI |
| `setup/sheets_creator.py` | Google Sheets 스프레드시트 + 헤더 자동 생성 |
| `setup/validator.py` | API 키 유효성 검증 |

---

## 3. Config 설계

### config.yaml 구조

```yaml
domain:
  name: ""                    # e.g., "게임", "핀테크", "의료"
  description: ""             # e.g., "게임 산업 법무/규제 동향"
  language: "ko"              # 브리핑 출력 언어

categories:                   # 사용자 정의 카테고리
  - name: ""
    description: ""           # LLM이 분류할 때 참고하는 설명

keywords:
  include: []                 # 관련 기사 필터 키워드
  exclude: []                 # 제외 키워드

sources:
  tier_a: []                  # 안정적 RSS
  tier_b: []                  # 불안정 RSS (실패 시 무시)

collection:
  days_back: 5
  top_n: 10
  min_content_length: 200
  dedup:
    source_similarity_threshold: 0.75
    cross_similarity_threshold: 0.60
    min_overlap_tokens: 3
    event_key_enabled: true
    event_time_bucket: "month"

llm:
  provider: "claude"          # claude | openai | gemini
  model: ""                   # 비우면 프로바이더 기본값
  max_input_chars: 8000

email:
  enabled: true
  sender_name: ""
  subject_prefix: ""
  recipients: []

sheets:
  spreadsheet_id: ""          # setup wizard가 자동 생성 후 기입

schedule:
  cron: "7 1 * * 1,3,5"      # GitHub Actions용
  timezone: "Asia/Seoul"
```

### 원칙

- `config.yaml`은 빈 템플릿, `config.example.yaml`에 게임 법무 예시 포함
- 모든 도메인 특화 값은 config에서만 관리
- API 키는 `.env`로 분리 (config에 절대 안 넣음)

### .env 구조

```
# LLM (선택한 provider에 해당하는 키만 필요)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS=    # 서비스 계정 JSON 경로 (로컬)
                              # CI: base64 인코딩 후 GOOGLE_SHEETS_CREDENTIALS_B64 secret에 저장

# Email (선택)
SMTP_USER=
SMTP_PASS=
SMTP_HOST=smtp.gmail.com      # 기본값, mailer.py에서 폴백
SMTP_PORT=587                  # 기본값, mailer.py에서 폴백
```

---

## 4. 멀티 LLM 설계

### 프로바이더 인터페이스

```python
# pipeline/llm/base.py
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """텍스트 응답 반환"""

    @abstractmethod
    def complete_json(self, system: str, user: str) -> dict:
        """JSON 파싱된 응답 반환 (3회 재시도)"""
```

### 프로바이더별 기본 모델

| Provider | 기본 모델 | 환경변수 |
|----------|----------|---------|
| claude | claude-haiku-4-5-20251001 | ANTHROPIC_API_KEY |
| openai | gpt-4o-mini | OPENAI_API_KEY |
| gemini | gemini-2.0-flash | GOOGLE_API_KEY |

### 동작 방식

- `config.yaml`의 `llm.provider`로 선택, `llm.model`로 오버라이드
- `complete_json()` 구현은 프로바이더별 최적화:
  - **OpenAI:** `response_format: { type: "json_object" }` 네이티브 JSON 모드 사용
  - **Gemini:** `response_mime_type: "application/json"` 사용
  - **Claude:** 프롬프트 기반 JSON 출력 + 응답 파싱
  - 공통: 파싱 실패 시 3회 재시도, 최종 실패 시 저신뢰 폴백
- 프롬프트는 `classifier.py`에서 config의 domain/categories를 주입해서 생성

### 프롬프트 구조

**LLM 1차 호출 (Top-N 선별):**
- System: `"당신은 {domain.name} 분야의 전문 편집자입니다. {domain.description}에 관한 뉴스 중 가장 중요한 {top_n}건을 선별하세요."`
- User: 후보 기사 목록 (제목 + 설명 + 소스)
- Output: 선별된 URL 목록 (JSON)

**LLM 2차 호출 (개별 요약/분류):**
- System: `"당신은 {domain.name} 분야 브리핑 AI입니다. 기사를 분석하여 요약, 카테고리, 이벤트 정보를 추출하세요. 카테고리: {categories 목록}. 출력 언어: {domain.language}."`
- User: 기사 제목 + 소스 + URL + 본문
- Output: `{ summary: [3줄], category: str, event: { jurisdiction, event_type, actors, object, action, time_hint } }`

---

## 5. 파이프라인 흐름

```
main.py 실행
    │
    ├─ config.py: config.yaml 로드 + 검증
    │
    ├─ collector.py: RSS 수집
    │   ├─ tier_a/tier_b 피드 파싱
    │   ├─ days_back 기간 필터
    │   └─ 원시 기사 목록 반환
    │
    ├─ dedup.py: 1차 중복제거 (Pre-LLM)
    │   ├─ Google Sheets 과거 기록 로드 (30일)
    │   ├─ 로컬 trends/ 파일 로드
    │   ├─ URL 정규화 + 토픽 토큰 유사도
    │   └─ 유니크 기사 목록 반환
    │
    ├─ classifier.py: 키워드 필터 + Top-N 선별 (LLM 1차)
    │   ├─ config.keywords로 사전 필터
    │   ├─ LLM에 top_n개 선별 요청
    │   └─ 선별된 기사 URL 목록 반환
    │
    ├─ collector.py: 본문 추출
    │   ├─ 선별된 기사 HTTP GET + BeautifulSoup
    │   └─ 본문 텍스트 반환 (min_content_length 미달 시 RSS 설명 폴백)
    │
    ├─ classifier.py: 개별 요약/분류 (LLM 2차)
    │   ├─ 기사별 요약 3줄 + 카테고리 + EventKey 생성
    │   └─ 저신뢰 결과 필터
    │
    ├─ dedup.py: 2차 중복제거 (Post-Summary)
    │   ├─ 요약 기반 토픽 토큰 매칭
    │   └─ EventKey 동일 이벤트 통합
    │
    ├─ archiver.py: Google Sheets 업로드
    │
    ├─ mailer.py: HTML 이메일 생성 + SMTP 발송
    │
    └─ trends/ 로컬 아카이브 저장
```

### 보존하는 핵심 로직

- **3단계 중복제거:** URL 정규화 → 토픽 토큰 유사도 → EventKey 핑거프린팅
- **2단계 LLM 호출:** Top-N 선별 → 개별 요약/분류
- **Graceful degradation:** 피드 실패 무시, LLM 실패 시 폴백, 이메일 실패해도 Sheets 업로드 유지

### 로깅

- Python `logging` 모듈 사용 (print 기반에서 전환)
- 기본 레벨: `INFO` (환경변수 `LOG_LEVEL`로 오버라이드)
- 포맷: `[%(levelname)s] %(name)s: %(message)s`
- GitHub Actions에서는 stdout으로 출력 (별도 파일 저장 불필요)
- 각 파이프라인 단계 시작/종료 로그 + 수집/필터/선별 건수 요약

### EventKey 생성 방식

LLM이 기사별로 반환하는 이벤트 메타데이터를 기반으로 핑거프린트 해시 생성:

```
EventKey = SHA256(
    jurisdiction + event_type + sorted(actors) + object + action + time_bucket
)[:hash_len]
```

- `jurisdiction`: 관할권 (e.g., "FTC", "EU", "KOREA")
- `event_type`: enforcement | legislation | litigation | policy | security_incident | business | other
- `actors`: 관련 주체 (정렬 후 결합)
- `object`: 대상 (e.g., "loot box regulation")
- `action`: 행위 (e.g., "filed complaint")
- `time_bucket`: config의 `event_time_bucket`에 따라 월/주 단위 버킷
- `hash_len`: config의 truncation 길이 (기본 16자)

동일 EventKey = 동일 실세계 이벤트 → 대표 기사 1건만 브리핑, 나머지는 Sheets에 DuplicateOf로 기록

### trends/ 로컬 아카이브 형식

파일명: `trends/trend_YYYY-MM-DD.txt`

```
[CATEGORY] 기사 제목
URL: https://...
Summary: 요약 1줄 | 요약 2줄 | 요약 3줄
EventKey: abc123def456
---
```

- 파이프라인 실행일 기준 1파일, 중복제거 시 과거 30일치 로드
- GitHub Actions에서 자동 커밋되어 git 히스토리에 보존

### CLI 옵션 (원본 보존)

```bash
python main.py                  # 전체 실행
python main.py --dry-run        # 수집+요약만, Sheets/이메일 안 함
python main.py --no-llm         # 수집+중복제거만, LLM 호출 안 함
python main.py --max-items 3    # 테스트용 제한 배치
```

---

## 6. Setup Wizard

```
python -m pipeline.setup.wizard
    │
    ├─ Step 1: API 키 검증 (validator.py)
    │   ├─ LLM 프로바이더 키 확인 (선택한 provider만)
    │   ├─ Google Sheets API 키 확인
    │   └─ SMTP 자격증명 확인 (email 활성화 시)
    │
    ├─ Step 2: 도메인 설정
    │   ├─ 도메인 이름 입력 (e.g., "핀테크")
    │   ├─ 도메인 설명 입력
    │   └─ 출력 언어 선택
    │
    ├─ Step 3: 카테고리 설정
    │   └─ 카테고리 이름 + 설명 입력 (반복)
    │
    ├─ Step 4: 키워드 설정
    │   ├─ 포함 키워드 입력
    │   └─ 제외 키워드 입력
    │
    ├─ Step 5: RSS 소스 등록
    │   └─ tier_a / tier_b URL 입력
    │
    ├─ Step 6: Google Sheets 자동 생성 (sheets_creator.py)
    │   ├─ 스프레드시트 생성
    │   ├─ 헤더 행 세팅 (Section 7 스키마 참조: Date~RunDate 11열)
    │   └─ spreadsheet_id를 config.yaml에 자동 기입
    │
    ├─ Step 7: 이메일 수신자 등록
    │
    └─ Step 8: config.yaml 저장 + 완료 메시지
```

### 특징

- 각 단계 스킵 가능 (나중에 config.yaml 직접 편집)
- `config.example.yaml` 기반으로 시작할 수도 있음 (`--from-example` 플래그)
- 검증 실패 시 어떤 키가 문제인지 명확히 안내

---

## 7. Google Sheets 스키마

### 자동 생성되는 시트 구조

| 열 | 타입 | 설명 |
|----|------|------|
| Date | 날짜 | 기사 발행일 |
| Title | 텍스트 | 기사 제목 |
| URL | URL | 기사 링크 |
| CanonicalURL | URL | 정규화된 URL (중복제거용) |
| Source | 텍스트 | 뉴스 소스명 |
| Category | 텍스트 | AI 분류 카테고리 |
| Summary | 텍스트 | AI 요약 (3줄) |
| EventKey | 텍스트 | 이벤트 핑거프린트 해시 |
| IsPrimary | 불리언 | 동일 이벤트 대표 기사 여부 |
| DuplicateOf | 텍스트 | 중복 대상 EventKey (비대표 기사) |
| RunDate | 날짜 | 파이프라인 실행일 |

---

## 8. 기술 스택 & 의존성

### requirements.txt

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

# Config & Environment
pyyaml>=6.0
python-dotenv>=1.0.0
```

### 외부 서비스

| 서비스 | 용도 | 인증 |
|--------|------|------|
| LLM API (선택) | 기사 선별 + 요약/분류 | API 키 (.env) |
| Google Sheets API | 데이터 아카이브 | 서비스 계정 JSON |
| Gmail SMTP | 이메일 발송 | 앱 비밀번호 (.env) |
| RSS 피드 | 뉴스 소스 | 없음 (공개) |

---

## 9. GitHub Actions

```yaml
name: Auto News Briefing
on:
  schedule:
    - cron: '7 1 * * 1,3,5'       # 사용자가 직접 편집 (config.yaml의 schedule.cron 참조)
  workflow_dispatch:

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

### config → workflow 연동

- `schedule.cron`은 workflow 파일에 직접 편집 (GitHub Actions는 cron을 리터럴로만 파싱)
- config.yaml의 `schedule.cron`은 문서/참조용으로 유지, setup wizard가 README에 설정 방법 안내
- `schedule.timezone`은 `BRIEFING_TZ` Repository Variable로 전달
- **Google Sheets 인증:** 서비스 계정 JSON을 base64 인코딩하여 `GOOGLE_SHEETS_CREDENTIALS_B64` secret에 저장, workflow에서 디코딩하여 임시 파일로 사용
