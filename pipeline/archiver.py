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
