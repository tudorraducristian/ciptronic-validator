import base64
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from email_agent.gmail_client import GmailClient, _resize_image


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


# ── _walk_parts ───────────────────────────────────────────────────────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode()


def test_walk_parts_collects_text():
    client = _make_client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64(b"hello email")}, "filename": None},
        ],
    }
    body_ref, images_ref, names_ref, pdf_bytes_ref = [""], [], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, pdf_bytes_ref, "msg-1")
    assert body_ref[0] == "hello email"


def test_walk_parts_collects_image():
    client = _make_client()
    raw_img = _png_bytes(50, 50)
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "image/jpeg",
                "filename": "test.jpg",
                "body": {"data": _b64(raw_img)},
            },
        ],
    }
    body_ref, images_ref, names_ref, pdf_bytes_ref = [""], [], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, pdf_bytes_ref, "msg-1")
    assert len(images_ref) == 1
    img = Image.open(BytesIO(images_ref[0]))
    assert img.format == "JPEG"


def test_walk_parts_collects_pdf_name():
    client = _make_client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "application/pdf", "filename": "logo.pdf", "body": {}},
        ],
    }
    body_ref, images_ref, names_ref, pdf_bytes_ref = [""], [], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, pdf_bytes_ref, "msg-1")
    assert names_ref == ["logo.pdf"]
    assert images_ref == []


def test_walk_parts_ignores_image_without_data():
    client = _make_client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "image/jpeg", "filename": "empty.jpg", "body": {}},
        ],
    }
    body_ref, images_ref, names_ref, pdf_bytes_ref = [""], [], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, pdf_bytes_ref, "msg-1")
    assert images_ref == []


def test_walk_parts_skips_corrupt_image_without_raising():
    client = _make_client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "image/jpeg",
                "filename": "corrupt.jpg",
                "body": {"data": _b64(b"not a real image, just junk bytes")},
            },
        ],
    }
    body_ref, images_ref, names_ref, pdf_bytes_ref = [""], [], [], []
    # nu trebuie să arunce — imaginea coruptă e sărită, nu propagată
    client._walk_parts(payload, body_ref, images_ref, names_ref, pdf_bytes_ref, "msg-1")
    assert images_ref == []


def test_walk_parts_corrupt_image_does_not_block_valid_sibling():
    client = _make_client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "image/jpeg",
                "filename": "corrupt.jpg",
                "body": {"data": _b64(b"junk")},
            },
            {
                "mimeType": "image/png",
                "filename": "good.png",
                "body": {"data": _b64(_png_bytes(40, 40))},
            },
        ],
    }
    body_ref, images_ref, names_ref, pdf_bytes_ref = [""], [], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, pdf_bytes_ref, "msg-1")
    # imaginea validă e colectată chiar dacă fratele ei e corupt
    assert len(images_ref) == 1
    assert Image.open(BytesIO(images_ref[0])).format == "JPEG"


# ── _fetch_and_parse ──────────────────────────────────────────────────────────

def _gmail_message_payload(text: bytes, img_bytes: bytes | None = None) -> dict:
    parts = [{"mimeType": "text/plain", "body": {"data": _b64(text)}}]
    if img_bytes:
        parts.append({
            "mimeType": "image/jpeg",
            "filename": "mock.jpg",
            "body": {"data": _b64(img_bytes)},
        })
    return {
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "Subject", "value": "Test subject"},
                {"name": "Date", "value": "Mon, 10 Jun 2026 09:00:00 +0300"},
            ],
            "parts": parts,
        }
    }


def test_fetch_and_parse_no_images(tmp_path):
    client = _make_client(image_save_dir=str(tmp_path / "email_images"))
    (
        client._service.users.return_value
        .messages.return_value
        .get.return_value
        .execute.return_value
    ) = _gmail_message_payload(b"corpo email")

    msg = client._fetch_and_parse("msg-123")

    assert msg.body_text == "corpo email"
    assert msg.image_paths == []


def test_fetch_and_parse_saves_images(tmp_path):
    client = _make_client(image_save_dir=str(tmp_path / "email_images"))
    (
        client._service.users.return_value
        .messages.return_value
        .get.return_value
        .execute.return_value
    ) = _gmail_message_payload(b"corpo email", _png_bytes(50, 50))

    msg = client._fetch_and_parse("msg-123")

    assert len(msg.image_paths) == 1
    assert Path(msg.image_paths[0]).is_file()
    assert "msg-123" in msg.image_paths[0]


def test_fetch_and_parse_no_save_when_dir_is_none():
    client = _make_client(image_save_dir=None)
    (
        client._service.users.return_value
        .messages.return_value
        .get.return_value
        .execute.return_value
    ) = _gmail_message_payload(b"corpo email", _png_bytes(50, 50))

    msg = client._fetch_and_parse("msg-123")

    assert msg.image_paths == []
