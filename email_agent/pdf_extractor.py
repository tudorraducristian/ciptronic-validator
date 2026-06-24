import io
import logging

_log = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 2000
_MAX_IMAGES = 10


def extract_pdf(pdf_bytes: bytes) -> tuple[str, list[bytes]]:
    """Extract text and JPEG images from PDF bytes using PyMuPDF.

    Returns (text, jpeg_images). On corrupt or password-protected PDFs
    returns ("", []) without raising.
    """
    try:
        import fitz  # PyMuPDF — imported here so the rest of the app
                     # works even if pymupdf is not installed
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        _log.warning("[pdf] nu pot deschide PDF: %s", exc)
        return "", []

    text_parts: list[str] = []
    images: list[bytes] = []
    total_chars = 0

    for page_num in range(len(doc)):
        page = doc[page_num]

        # --- text ---
        remaining = _MAX_TEXT_CHARS - total_chars
        if remaining > 0:
            page_text = page.get_text().strip()
            if page_text:
                chunk = page_text[:remaining]
                text_parts.append(chunk)
                total_chars += len(chunk)

        # --- images ---
        if len(images) >= _MAX_IMAGES:
            continue
        try:
            image_list = page.get_images(full=True)
        except Exception as exc:
            _log.warning("[pdf] eroare la listarea imaginilor pagina %d: %s", page_num, exc)
            continue

        for img_info in image_list:
            if len(images) >= _MAX_IMAGES:
                _log.warning("[pdf] depășit limita de %d imagini, restul omise", _MAX_IMAGES)
                break
            xref = img_info[0]
            try:
                base_img = doc.extract_image(xref)
                raw = base_img["image"]
                jpeg = _to_jpeg(raw)
                if jpeg:
                    images.append(jpeg)
            except Exception as exc:
                _log.warning("[pdf] imagine xref=%d ilizibilă, omisă: %s", xref, exc)

    return "\n".join(text_parts), images


def _to_jpeg(raw: bytes, max_px: int = 1024) -> bytes | None:
    try:
        from PIL import Image
        buf_in = io.BytesIO(raw)
        img = Image.open(buf_in)
        img.thumbnail((max_px, max_px), Image.LANCZOS)
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        buf_out = io.BytesIO()
        img.save(buf_out, format="JPEG", quality=85)
        return buf_out.getvalue()
    except Exception as exc:
        _log.warning("[pdf] conversie JPEG eșuată: %s", exc)
        return None
