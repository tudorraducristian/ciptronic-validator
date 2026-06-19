from io import BytesIO
from pathlib import Path

from PIL import Image

from email_agent.gmail_client import EmailMessage
from email_agent import email_extractor


class FakeLLM:
    def __init__(self, response: str):
        self._response = response
        self.calls: list = []

    def complete_text(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._response


def _make_email(body: str, subject: str = "Cerere produse") -> EmailMessage:
    return EmailMessage(
        gmail_id="gid-1",
        sender="E-CABLAJE S.A. <office@ecablaje.ro>",
        subject=subject,
        body_text=body,
        date="Mon, 10 Jun 2026 09:00:00 +0300",
    )


def test_extract_single_product():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricou polo navy cu broderie ECJ",
        "prefilled_state": {
          "culoare_principala": "navy",
          "guler": "polo",
          "branding": {"tehnica": "broderie", "culori": ["alb"]}
        }
      }
    ]""")
    requests = email_extractor.extract(_make_email("tricou polo navy cu broderie ECJ"), llm)
    assert len(requests) == 1
    assert requests[0].product_type == "tricou"
    assert requests[0].prefilled_state["culoare_principala"] == "navy"
    assert requests[0].email_sender == "E-CABLAJE S.A. <office@ecablaje.ro>"


def test_extract_multiple_products():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricouri polo navy",
        "prefilled_state": {"culoare_principala": "navy", "guler": "polo"}
      },
      {
        "product_type": "tricou",
        "description": "tricouri albe maneci lungi",
        "prefilled_state": {"culoare_principala": "alb", "maneci": "lungi"}
      }
    ]""")
    requests = email_extractor.extract(
        _make_email("vreau tricouri polo navy si tricouri albe maneci lungi"), llm
    )
    assert len(requests) == 2


def test_extract_partial_fields_no_invention():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricou polo cu broderie",
        "prefilled_state": {
          "guler": "polo",
          "branding": {"tehnica": "broderie"}
        }
      }
    ]""")
    requests = email_extractor.extract(_make_email("tricou polo cu broderie"), llm)
    assert len(requests) == 1
    assert "culoare_principala" not in requests[0].prefilled_state


def test_missing_fields_calculated_correctly():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricou polo navy",
        "prefilled_state": {
          "culoare_principala": "navy",
          "guler": "polo"
        }
      }
    ]""")
    requests = email_extractor.extract(_make_email("tricou polo navy"), llm)
    assert len(requests) == 1
    assert "material" in requests[0].missing_fields
    assert "croiala" in requests[0].missing_fields
    assert "branding.tehnica" in requests[0].missing_fields
    assert "culoare_principala" not in requests[0].missing_fields
    assert "guler" not in requests[0].missing_fields


def test_extract_returns_empty_on_no_products():
    llm = FakeLLM("[]")
    requests = email_extractor.extract(_make_email("multumesc pentru colaborare"), llm)
    assert requests == []


def test_extract_handles_json_fenced_response():
    llm = FakeLLM('```json\n[{"product_type": "tricou", "description": "tricou alb", "prefilled_state": {"culoare_principala": "alb"}}]\n```')
    requests = email_extractor.extract(_make_email("tricou alb"), llm)
    assert len(requests) == 1
    assert requests[0].prefilled_state["culoare_principala"] == "alb"


def test_prompt_includes_schema_fields():
    calls = []

    class CaptureLLM:
        def complete_text(self, system, user):
            calls.append(user)
            return "[]"

    email_extractor.extract(_make_email("test"), CaptureLLM())
    assert len(calls) == 1
    assert "culoare_principala" in calls[0]
    assert "branding.tehnica" in calls[0]


# ── ramura vision ─────────────────────────────────────────────────────────────


class _FakeLLMBoth:
    """FakeLLM care înregistrează ambele tipuri de apeluri."""
    def __init__(self, response: str):
        self._response = response
        self.text_calls: list = []
        self.vision_calls: list = []

    def complete_text(self, system: str, user: str) -> str:
        self.text_calls.append((system, user))
        return self._response

    def complete_vision(self, system: str, content_blocks: list) -> str:
        self.vision_calls.append((system, content_blocks))
        return self._response


def _jpeg_file(tmp_path, idx: int = 0) -> str:
    buf = BytesIO()
    Image.new("RGB", (10, 10), color=(255, 0, 0)).save(buf, format="JPEG")
    path = Path(tmp_path) / f"img{idx:02d}.jpg"
    path.write_bytes(buf.getvalue())
    return str(path)


def _make_email_with_images(tmp_path, body: str = "tricou polo navy") -> EmailMessage:
    return EmailMessage(
        gmail_id="gid-img",
        sender="E-CABLAJE S.A. <office@ecablaje.ro>",
        subject="Cerere produse",
        body_text=body,
        date="Mon, 10 Jun 2026 09:00:00 +0300",
        image_paths=[_jpeg_file(tmp_path, 0)],
    )


def test_extract_uses_vision_when_images_present(tmp_path):
    llm = _FakeLLMBoth('[{"product_type":"tricou","description":"polo","prefilled_state":{"culoare_principala":"navy"}}]')
    requests = email_extractor.extract(_make_email_with_images(tmp_path), llm)
    assert len(llm.vision_calls) == 1
    assert len(llm.text_calls) == 0
    assert len(requests) == 1


def test_extract_uses_text_when_no_images():
    llm = _FakeLLMBoth("[]")
    msg = _make_email("test fara imagini")
    email_extractor.extract(msg, llm)
    assert len(llm.text_calls) == 1
    assert len(llm.vision_calls) == 0


def test_extract_vision_content_blocks_include_text_and_image(tmp_path):
    llm = _FakeLLMBoth("[]")
    email_extractor.extract(_make_email_with_images(tmp_path), llm)
    _, content_blocks = llm.vision_calls[0]
    types = [b["type"] for b in content_blocks]
    assert "text" in types
    assert "image" in types


def test_extract_vision_includes_pdf_names_in_text(tmp_path):
    llm = _FakeLLMBoth("[]")
    msg = _make_email_with_images(tmp_path)
    msg.other_attachment_names = ["Logo ECJ.pdf"]
    email_extractor.extract(msg, llm)
    _, content_blocks = llm.vision_calls[0]
    text_block = next(b for b in content_blocks if b["type"] == "text")
    assert "Logo ECJ.pdf" in text_block["text"]


def test_extract_vision_image_block_is_base64_jpeg(tmp_path):
    llm = _FakeLLMBoth("[]")
    email_extractor.extract(_make_email_with_images(tmp_path), llm)
    _, content_blocks = llm.vision_calls[0]
    img_block = next(b for b in content_blocks if b["type"] == "image")
    assert img_block["source"]["type"] == "base64"
    assert img_block["source"]["media_type"] == "image/jpeg"
