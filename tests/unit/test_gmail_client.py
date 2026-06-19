import base64
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from email_agent.gmail_client import EmailMessage, GmailClient, _resize_image


# ── helpers ──────────────────────────────────────────────────────────────────

def _png_bytes(w: int = 2000, h: int = 1500) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(100, 150, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _make_client(image_save_dir=None) -> GmailClient:
    """GmailClient cu __post_init__ ocolit — fără OAuth."""
    c = object.__new__(GmailClient)
    c.credentials_path = "creds.json"
    c.token_path = "token.json"
    c.image_save_dir = image_save_dir
    c._service = MagicMock()
    return c


# ── _resize_image ─────────────────────────────────────────────────────────────

def test_resize_image_caps_at_1024px():
    result = _resize_image(_png_bytes(2000, 1500))
    img = Image.open(BytesIO(result))
    assert max(img.size) <= 1024


def test_resize_image_output_is_jpeg():
    result = _resize_image(_png_bytes())
    img = Image.open(BytesIO(result))
    assert img.format == "JPEG"


def test_resize_image_small_image_not_upscaled():
    result = _resize_image(_png_bytes(100, 80))
    img = Image.open(BytesIO(result))
    assert img.size == (100, 80)


def test_resize_image_respects_custom_max_px():
    result = _resize_image(_png_bytes(2000, 1500), max_px=512)
    img = Image.open(BytesIO(result))
    assert max(img.size) <= 512


# ── _get_part_bytes ───────────────────────────────────────────────────────────

def test_get_part_bytes_inline_data():
    client = _make_client()
    raw = b"hello image bytes"
    encoded = base64.urlsafe_b64encode(raw).decode()
    result = client._get_part_bytes({"data": encoded}, "msg-1")
    assert result == raw
    client._service.users.return_value.messages.return_value.attachments.assert_not_called()


def test_get_part_bytes_fetches_attachment_id():
    client = _make_client()
    raw = b"large image bytes"
    encoded = base64.urlsafe_b64encode(raw).decode()
    (
        client._service.users.return_value
        .messages.return_value
        .attachments.return_value
        .get.return_value
        .execute.return_value
    ) = {"data": encoded}

    result = client._get_part_bytes({"attachmentId": "att-123"}, "msg-1")

    assert result == raw
    (
        client._service.users.return_value
        .messages.return_value
        .attachments.return_value
        .get.assert_called_once_with(userId="me", messageId="msg-1", id="att-123")
    )


def test_get_part_bytes_returns_none_when_empty():
    client = _make_client()
    assert client._get_part_bytes({}, "msg-1") is None
