import io
import fitz  # PyMuPDF
import pytest
from PIL import Image
from email_agent.pdf_extractor import extract_pdf


def _make_text_pdf(text: str) -> bytes:
    """Creates a minimal PDF with given text on page 1."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    return doc.tobytes()


def _make_image_pdf() -> bytes:
    """Creates a PDF with a small embedded JPEG image."""
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), color=(255, 0, 0)).save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    rect = fitz.Rect(10, 10, 110, 110)
    page.insert_image(rect, stream=jpeg_bytes)
    return doc.tobytes()


def test_extract_text_from_pdf():
    pdf_bytes = _make_text_pdf("culoare negru guler rotund")
    text, images = extract_pdf(pdf_bytes)
    assert "negru" in text
    assert "rotund" in text
    assert isinstance(images, list)


def test_extract_images_from_pdf():
    pdf_bytes = _make_image_pdf()
    text, images = extract_pdf(pdf_bytes)
    assert isinstance(images, list)
    assert len(images) >= 1
    # Each image should be valid JPEG bytes
    img = Image.open(io.BytesIO(images[0]))
    assert img.format == "JPEG"


def test_extract_corrupted_pdf():
    text, images = extract_pdf(b"not a pdf at all %%EOF garbage")
    assert text == ""
    assert images == []


def test_extract_empty_pdf():
    doc = fitz.open()
    doc.new_page()  # blank page, no content
    pdf_bytes = doc.tobytes()
    text, images = extract_pdf(pdf_bytes)
    assert text == ""
    assert images == []


def test_text_truncated_at_2000_chars():
    long_text = "a" * 3000
    pdf_bytes = _make_text_pdf(long_text)
    text, _ = extract_pdf(pdf_bytes)
    assert len(text) <= 2000


def test_max_10_images():
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(0, 0, 255)).save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()
    for i in range(15):
        x = (i % 5) * 50
        y = (i // 5) * 50
        page.insert_image(fitz.Rect(x, y, x + 40, y + 40), stream=jpeg_bytes)
    pdf_bytes = doc.tobytes()
    _, images = extract_pdf(pdf_bytes)
    assert len(images) <= 10
