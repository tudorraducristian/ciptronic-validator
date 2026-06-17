import base64
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


@dataclass
class EmailMessage:
    gmail_id: str
    sender: str
    subject: str
    body_text: str
    date: str  # RFC 2822 date string din header


@dataclass
class GmailClient:
    credentials_path: str = field(
        default_factory=lambda: os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
    )
    token_path: str = "gmail_token.json"

    def __post_init__(self):
        self._service = self._build_service()

    def _build_service(self):
        creds = None
        if Path(self.token_path).exists():
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            Path(self.token_path).write_text(creds.to_json())
        return build("gmail", "v1", credentials=creds)

    def fetch_emails(self, date_start: str, date_end: str) -> list[EmailMessage]:
        """Returnează emailurile primite între date_start și date_end (format YYYY-MM-DD)."""
        end_exclusive = (date.fromisoformat(date_end) + timedelta(days=1)).strftime("%Y/%m/%d")
        query = f"after:{date_start.replace('-', '/')} before:{end_exclusive}"
        import logging; logging.warning(f"[GmailClient] query={query!r}")
        result = self._service.users().messages().list(
            userId="me", q=query
        ).execute()
        messages = result.get("messages", [])
        import logging; logging.warning(f"[GmailClient] messages={messages}")
        return [self._fetch_and_parse(m["id"]) for m in messages]

    def _fetch_and_parse(self, msg_id: str) -> EmailMessage:
        msg = self._service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body_ref = [""]
        self._walk_parts(msg["payload"], body_ref)
        return EmailMessage(
            gmail_id=msg_id,
            sender=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            body_text=body_ref[0],
            date=headers.get("Date", ""),
        )

    def _walk_parts(self, payload: dict, body_ref: list) -> None:
        mime = payload.get("mimeType", "")
        if mime == "text/plain" and not payload.get("filename"):
            data = payload.get("body", {}).get("data", "")
            if data:
                body_ref[0] += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            self._walk_parts(part, body_ref)
