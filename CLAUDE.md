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
