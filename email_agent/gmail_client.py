import base64
import io
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from PIL import Image


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


@dataclass
class EmailMessage:
    gmail_id: str
    sender: str
    subject: str
    body_text: str
    date: str  # RFC 2822 date string din header
    image_paths: list[str] = field(default_factory=list)
    other_attachment_names: list[str] = field(default_factory=list)


def _resize_image(data: bytes, max_px: int = 1024) -> bytes:
    img = Image.open(io.BytesIO(data))
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


@dataclass
class GmailClient:
    credentials_path: str = field(
        default_factory=lambda: os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
    )
    token_path: str = "gmail_token.json"
    image_save_dir: str | None = None

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

    def _get_part_bytes(self, body: dict, msg_id: str) -> bytes | None:
        data = body.get("data", "")
        if data:
            return base64.urlsafe_b64decode(data)
        att_id = body.get("attachmentId")
        if att_id:
            att = self._service.users().messages().attachments().get(
                userId="me", messageId=msg_id, id=att_id
            ).execute()
            return base64.urlsafe_b64decode(att.get("data", ""))
        return None

    def get_address(self) -> str:
        """Email address of the authorized account (userId='me')."""
        profile = self._service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress", "")

    def fetch_emails(self, date_start: str, date_end: str) -> list[EmailMessage]:
        """Returnează emailurile primite între date_start și date_end (format YYYY-MM-DD)."""
        end_exclusive = (date.fromisoformat(date_end) + timedelta(days=1)).strftime("%Y/%m/%d")
        query = f"after:{date_start.replace('-', '/')} before:{end_exclusive}"
        result = self._service.users().messages().list(
            userId="me", q=query
        ).execute()
        messages = result.get("messages", [])
        return [self._fetch_and_parse(m["id"]) for m in messages]

    def _fetch_and_parse(self, msg_id: str) -> EmailMessage:
        msg = self._service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

        body_ref: list[str] = [""]
        images_ref: list[bytes] = []
        names_ref: list[str] = []
        self._walk_parts(msg["payload"], body_ref, images_ref, names_ref, msg_id)

        image_paths: list[str] = []
        if images_ref and self.image_save_dir:
            save_dir = Path(self.image_save_dir) / Path(msg_id).name
            save_dir.mkdir(parents=True, exist_ok=True)
            for idx, img_bytes in enumerate(images_ref):
                path = save_dir / f"{idx:02d}.jpg"
                path.write_bytes(img_bytes)
                image_paths.append(str(path))

        return EmailMessage(
            gmail_id=msg_id,
            sender=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            body_text=body_ref[0],
            date=headers.get("Date", ""),
            image_paths=image_paths,
            other_attachment_names=names_ref,
        )

    def _walk_parts(
        self,
        payload: dict,
        body_ref: list[str],
        images_ref: list[bytes],
        names_ref: list[str],
        msg_id: str,
    ) -> None:
        mime = payload.get("mimeType", "")
        body = payload.get("body", {})

        if mime == "text/plain" and not payload.get("filename"):
            data = body.get("data", "")
            if data:
                body_ref[0] += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        elif mime.startswith("image/"):
            raw = self._get_part_bytes(body, msg_id)
            if raw:
                images_ref.append(_resize_image(raw))

        elif mime == "application/pdf" or (payload.get("filename") or "").lower().endswith(".pdf"):
            fn = payload.get("filename") or "document.pdf"
            names_ref.append(fn)

        for part in payload.get("parts", []):
            self._walk_parts(part, body_ref, images_ref, names_ref, msg_id)


def authorized_address(token_path: str = "gmail_token.json") -> str | None:
    """Email of the already-authorized Gmail account, or None when not yet
    authorized / unavailable. Never starts the interactive OAuth flow, so it is
    safe to call on a normal page load."""
    try:
        if not Path(token_path).exists():
            return None
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return None
        service = build("gmail", "v1", credentials=creds)
        return service.users().getProfile(userId="me").execute().get("emailAddress")
    except Exception:
        return None
