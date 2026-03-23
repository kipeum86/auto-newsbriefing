"""Auto-create Google Sheets spreadsheet with proper headers."""

import logging
import os

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

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "Briefings"}}],
    }
    result = sheets_service.spreadsheets().create(body=body).execute()
    spreadsheet_id = result["spreadsheetId"]
    logger.info("Created spreadsheet: %s", spreadsheet_id)

    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Briefings!A1",
        valueInputOption="RAW",
        body={"values": [HEADERS]},
    ).execute()

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
