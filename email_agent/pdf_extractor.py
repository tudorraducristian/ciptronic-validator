import io
import logging

_log = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 2000
_MAX_IMAGES = 10
_MAX_PAGES = 50          # stop walking after this many pages
_MAX_PDF_BYTES = 10 * 1024 * 1024   # 10 MB — reject before opening


def extract_pdf(pdf_bytes: bytes) -> tuple[str, list[bytes]]:
    """Extract text and JPEG images from PDF bytes using PyMuPDF.

    Returns (text, jpeg_images). On corrupt or password-protected PDFs
    returns ("", []) without raising.
    """
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        _log.warning("[pdf] PDF prea mare (%d bytes), omis", len(pdf_bytes))
        return "", []

    try:
        import fitz  # PyMuPDF — imported here so the rest of the app
                     # works even if pymupdf is not installed
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        _log.warning("[pdf] nu pot deschide PDF: %s", exc)
        return "", []

    with doc:
        if doc.needs_pass:
            _log.warning("[pdf] PDF protejat cu parolă, omis")
            return "", []

        text_parts: list[str] = []
        images: list[bytes] = []
        total_chars = 0
        seen_xrefs: set[int] = set()

        for page_num in range(min(len(doc), _MAX_PAGES)):
            # Stop early if both budgets are exhausted
            if total_chars >= _MAX_TEXT_CHARS and len(images) >= _MAX_IMAGES:
                break

            try:
                page = doc[page_num]
            except Exception as exc:
                _log.warning("[pdf] eroare la încărcarea paginii %d: %s", page_num, exc)
                continue

            # --- text ---
            remaining = _MAX_TEXT_CHARS - total_chars
            if remaining > 0:
                try:
                    page_text = page.get_text("text", sort=True).strip()
                    if page_text:
                        chunk = page_text[:remaining]
                        text_parts.append(chunk)
                        total_chars += len(chunk)
                except Exception as exc:
                    _log.warning("[pdf] eroare la extragerea textului pagina %d: %s", page_num, exc)

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
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
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
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 20_000_000  # ~4500×4500px — respinge bombe
    DecompressionBombError = Image.DecompressionBombError
    try:
        buf_in = io.BytesIO(raw)
        img = Image.open(buf_in)
        img.load()  # forțează decodarea completă înainte de thumbnail
        img.thumbnail((max_px, max_px), Image.LANCZOS)
        if img.mode in ("RGBA", "LA", "P"):
            converted = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(converted, mask=converted.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        buf_out = io.BytesIO()
        img.save(buf_out, format="JPEG", quality=85)
        return buf_out.getvalue()
    except DecompressionBombError as exc:
        _log.warning("[pdf] decompression bomb blocată: %s", exc)
        return None
    except Exception as exc:
        _log.warning("[pdf] conversie JPEG eșuată: %s", exc)
        return None
