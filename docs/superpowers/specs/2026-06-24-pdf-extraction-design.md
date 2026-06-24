# PDF Extraction from Email Attachments

**Date:** 2026-06-24  
**Status:** Approved

## Problem

When a client sends an email with a PDF attachment containing product specifications, the system currently only passes the PDF filename to the LLM — not its content. This means valuable information (text descriptions, branding specs, embedded mockup images) is ignored during extraction.

## Goal

Extract text and images from PDF attachments and feed them to the LLM with the same priority rules already in place: **text always overrides images**. If the PDF text says "round collar" but an embedded image shows a V-neck, the LLM uses "round collar".

## Architecture

### New module: `email_agent/pdf_extractor.py`

Single public function:

```python
def extract_pdf(pdf_bytes: bytes) -> tuple[str, list[bytes]]:
    """Returns (text, jpeg_images) extracted from PDF.
    On corrupt/password-protected PDFs returns ("", []) without raising."""
```

Uses PyMuPDF (`fitz`). Text is limited to 2000 characters per PDF. Images are limited to 10 per PDF; extras are skipped with a warning log.

### Changes to `EmailMessage` (gmail_client.py)

Two new fields:
- `pdf_texts: list[str]` — text extracted from each PDF attachment
- `pdf_image_paths: list[str]` — JPEG images extracted from PDFs, saved to disk

### Changes to `gmail_client._walk_parts()`

When a PDF part is encountered:
1. Download bytes via `_get_part_bytes()`
2. Call `pdf_extractor.extract_pdf(pdf_bytes)`
3. Append text to `pdf_texts`
4. Resize and save images to `uploads/email_images/{msg_id}/pdf_{attachment_idx}_{image_idx}.jpg`
5. Append paths to `pdf_image_paths`

Filename still kept in `other_attachment_names` for reference.

### Changes to `email_extractor.extract()`

- Concatenate `pdf_texts` into `corp_email` with a separator: `"\n\n--- Conținut PDF ---\n" + text`
- Append `pdf_image_paths` to `image_paths` before building vision blocks

LLM sees all text (email body + PDF text) and all images (email images + PDF images), with existing priority rule: text > images.

## Data Flow

```
Email with PDF attachment
        ↓
gmail_client._walk_parts()
        ↓
_get_part_bytes() → pdf_bytes
        ↓
pdf_extractor.extract_pdf(pdf_bytes)
        ├── text → EmailMessage.pdf_texts
        └── JPEG images → uploads/email_images/{msg_id}/pdf_{n}_{i}.jpg
                        → EmailMessage.pdf_image_paths
        ↓
email_extractor.extract()
        ├── corp_email + pdf_texts → LLM text context
        └── image_paths + pdf_image_paths → LLM image blocks
        ↓
LLM: text has priority, images fill only missing fields
```

## Error Handling

- Corrupt / password-protected PDF → `extract_pdf` returns `("", [])`, logs warning, does not block
- Image inside PDF unreadable → skip that image, log warning
- More than 10 images in PDF → skip extras, log warning
- PDF text > 2000 chars → truncate at 2000

## Files Changed

| File | Change |
|------|--------|
| `email_agent/pdf_extractor.py` | New — PyMuPDF extraction |
| `email_agent/gmail_client.py` | `EmailMessage` gets `pdf_texts`, `pdf_image_paths`; `_walk_parts` calls `extract_pdf` |
| `email_agent/email_extractor.py` | Merge pdf_texts into body, pdf_image_paths into image_paths |
| `requirements.txt` | Add `pymupdf>=1.24` |

## Tests

### Unit — `tests/unit/test_pdf_extractor.py`
- `test_extract_text_from_pdf` — text PDF → correct text returned
- `test_extract_images_from_pdf` — PDF with image → non-empty JPEG bytes list
- `test_extract_corrupted_pdf` — invalid bytes → `("", [])`, no exception
- `test_extract_empty_pdf` — empty PDF → `("", [])`

### E2e — `tests/e2e/test_email_agent_routes.py`
- `test_fetch_includes_pdf_text` — email with PDF → PDF text contributes to `prefilled_state`
