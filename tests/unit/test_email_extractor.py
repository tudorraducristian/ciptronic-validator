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
