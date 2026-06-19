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
