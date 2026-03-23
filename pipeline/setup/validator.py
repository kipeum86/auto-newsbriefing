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

    creds = kwargs.get("sheets_creds") or os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
    if creds:
        results["sheets"] = validate_google_sheets(creds, kwargs.get("spreadsheet_id", ""))
    else:
        results["sheets"] = {"status": "skip", "message": "GOOGLE_SHEETS_CREDENTIALS not set"}

    smtp_user = kwargs.get("smtp_user") or os.environ.get("SMTP_USER", "")
    smtp_pass = kwargs.get("smtp_pass") or os.environ.get("SMTP_PASS", "")
    if smtp_user and smtp_pass:
        results["smtp"] = validate_smtp(smtp_user, smtp_pass)
    else:
        results["smtp"] = {"status": "skip", "message": "SMTP credentials not set"}

    return results
