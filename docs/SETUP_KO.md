# auto-newsbriefing 한국어 셋업 가이드

> 영문 README 및 아키텍처 설명: [README.md](../README.md)

RSS 기반 뉴스를 수집하고, AI로 분류/요약한 뒤, Google Sheets에 아카이브하고 이메일 브리핑을 발송하는 자동화 도구입니다.

---

## 사전 준비

| 필요 항목 | 비고 |
|-----------|------|
| Python 3.12 이상 | 3.12~3.14 테스트 완료 |
| LLM API 키 | Anthropic, OpenAI, Google AI 중 하나 |
| Google Cloud 서비스 계정 | Google Sheets API용 (무료 티어 충분) |
| Gmail + 앱 비밀번호 | 선택 사항 — 이메일 발송 시에만 필요 |
| GitHub 저장소 | 선택 사항 — 자동 스케줄 실행 시에만 필요 |

---

## 셋업 가이드

### 1단계: 클론 및 설치

```bash
git clone https://github.com/kipeum86/auto-newsbriefing.git
cd auto-newsbriefing
pip install -r requirements.txt
```

### 2단계: API 키 발급

#### LLM 프로바이더 (하나만 선택)

| 프로바이더 | 발급 페이지 | 환경변수 |
|-----------|------------|---------|
| Claude | [console.anthropic.com](https://console.anthropic.com/) | `ANTHROPIC_API_KEY` |
| OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` |
| Gemini | [aistudio.google.com](https://aistudio.google.com/apikey) | `GOOGLE_API_KEY` |

#### Google Sheets 서비스 계정

1. [Google Cloud Console](https://console.cloud.google.com/)에 접속
2. 새 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **Google Sheets API**와 **Google Drive API** 활성화:
   - *API 및 서비스 → 라이브러리*로 이동
   - 각 API를 검색하여 *사용* 클릭
4. 서비스 계정 생성:
   - *IAM 및 관리자 → 서비스 계정*으로 이동
   - *서비스 계정 만들기* 클릭
   - 이름 입력 (예: `newsbriefing-bot`) → *완료*
5. JSON 키 생성:
   - 서비스 계정 클릭 → *키* 탭 → *키 추가 → 새 키 만들기 → JSON*
   - 다운로드된 `.json` 파일을 안전한 위치에 저장
6. 파일 경로를 기록 — `.env`의 `GOOGLE_SHEETS_CREDENTIALS`에 사용

#### Gmail 앱 비밀번호 (선택, 이메일 발송용)

1. Google 계정에서 [2단계 인증](https://myaccount.google.com/security) 활성화
2. [앱 비밀번호](https://myaccount.google.com/apppasswords) 페이지로 이동
3. *메일*을 선택하고 비밀번호 생성
4. 16자리 비밀번호를 복사 — `.env`의 `SMTP_PASS`에 사용

### 3단계: 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 편집합니다:

```env
# LLM — 선택한 프로바이더의 키만 입력하면 됩니다
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=AI...

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS=/path/to/service-account-key.json

# 이메일 (선택)
SMTP_USER=you@gmail.com
SMTP_PASS=abcd efgh ijkl mnop

# 로깅
LOG_LEVEL=INFO
```

### 4단계: 브리핑 설정

**방법 A: 대화형 위저드 (권장)**

```bash
python -m pipeline.setup.wizard
```

위저드가 8단계를 안내합니다: API 검증 → 도메인 → 카테고리 → 키워드 → RSS 소스 → Google Sheets → 이메일 → 저장.

**방법 B: 예시 설정 복사**

```bash
cp config.example.yaml config.yaml
# config.yaml을 원하는 도메인에 맞게 편집
```

#### config.yaml 주요 섹션

| 섹션 | 설명 |
|------|------|
| `domain` | 도메인 이름, 설명, 출력 언어 |
| `categories` | 뉴스 분류 카테고리 (이름 + LLM용 설명) |
| `keywords` | LLM 호출 전 적용되는 포함/제외 키워드 |
| `sources` | RSS 피드 URL — `tier_a` (안정적) / `tier_b` (불안정) |
| `llm` | 프로바이더 (`claude`/`openai`/`gemini`), 모델, 최대 입력 글자수 |
| `email` | 발신자 이름, 제목 접두사, 수신자 목록 |
| `sheets` | `spreadsheet_id` (위저드 또는 자동 생성으로 채워짐) |
| `schedule` | cron 표현식과 타임존 (GitHub Actions 참조용) |

### 5단계: 테스트 실행

```bash
# 전체 dry run (RSS 수집 + LLM 요약, Sheets/이메일은 건너뜀)
python main.py --dry-run

# LLM 호출 없이 빠르게 테스트
python main.py --dry-run --no-llm

# 기사 3개로 제한
python main.py --dry-run --max-items 3
```

성공하면 카테고리별로 분류·요약된 `DRY RUN SUMMARY`가 출력됩니다.

### 6단계: GitHub Actions 배포

#### 6.1 Google Sheets 인증 정보 인코딩

```bash
# macOS
cat /path/to/service-account-key.json | base64 | pbcopy

# Linux
cat /path/to/service-account-key.json | base64 -w 0
```

#### 6.2 GitHub Secrets 등록

저장소 → *Settings → Secrets and variables → Actions → New repository secret*:

| Secret 이름 | 값 |
|-------------|-----|
| `ANTHROPIC_API_KEY` | Anthropic API 키 (또는 `OPENAI_API_KEY` / `GOOGLE_API_KEY`) |
| `GOOGLE_SHEETS_CREDENTIALS_B64` | Base64 인코딩된 서비스 계정 JSON |
| `SMTP_USER` | Gmail 주소 (선택) |
| `SMTP_PASS` | Gmail 앱 비밀번호 (선택) |

#### 6.3 (선택) 타임존 변수 설정

*Settings → Secrets and variables → Actions → Variables*:

| Variable 이름 | 값 |
|--------------|-----|
| `BRIEFING_TZ` | 예: `Asia/Seoul`, `America/New_York` |

#### 6.4 스케줄 변경

`.github/workflows/schedule.yml`에서 cron 라인을 수정합니다:

```yaml
schedule:
  - cron: '7 1 * * 1,3,5'   # UTC 기준 월/수/금 01:07 (KST 10:07)
```

*Actions → Run workflow*에서 수동 실행도 가능합니다.

---

## CLI 참조

```
python main.py [옵션]

옵션:
  --dry-run          수집·처리만 하고 Sheets 업로드/이메일 발송 건너뜀
  --no-llm           LLM 호출 전부 건너뜀 (RSS/중복제거만 테스트)
  --max-items N      처리할 기사 수 제한
  --config PATH      커스텀 설정 파일 사용 (기본: config.yaml)
```

```
python -m pipeline.setup.wizard [옵션]

옵션:
  --from-example     빈 설정 대신 config.example.yaml 기반으로 시작
```

---

## 문제 해결

| 문제 | 해결 방법 |
|------|----------|
| `ModuleNotFoundError: No module named 'yaml'` | `pip install -r requirements.txt` 실행 |
| `config.yaml not found` | `python -m pipeline.setup.wizard` 실행 또는 `cp config.example.yaml config.yaml` |
| `ANTHROPIC_API_KEY not set` | `.env`에 키 추가 후 터미널 재시작 |
| `Google Sheets credentials not found` | `.env`의 `GOOGLE_SHEETS_CREDENTIALS` 경로 확인 (절대 경로 사용) |
| `SMTP connection failed` | Google 계정에서 2단계 인증 활성화 후 앱 비밀번호 재생성 |
| `No articles collected` | RSS 피드 URL 접근 가능 여부 확인; `--no-llm`으로 분리 테스트 |
| GitHub Actions 인증 에러 | `cat file.json \| base64` 로 재인코딩 (줄바꿈 없이) |
| `키워드 필터 후 0건` | `keywords.include`를 넓히거나 `[]`로 설정하여 필터 건너뜀 |

---

> 아키텍처, 모듈 구조 등 상세 내용은 [README.md](../README.md)를 참조하세요.
