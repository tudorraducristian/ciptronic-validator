import json
from email_agent.gmail_client import EmailMessage


class FakeGmail:
    def __init__(self, messages):
        self._messages = messages

    def fetch_emails(self, date_start, date_end):
        return self._messages


def _make_email(body="tricou polo navy cu broderie ECJ"):
    return EmailMessage(
        gmail_id="gid-1",
        sender="E-CABLAJE S.A. <office@ecablaje.ro>",
        subject="Cerere produse iunie",
        body_text=body,
        date="Mon, 10 Jun 2026 09:00:00 +0300",
    )


def test_fetch_returns_list_with_results(client, fake_llm, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([_make_email()]))
    fake_llm.queue_text(json.dumps([{
        "product_type": "tricou",
        "description": "tricou polo navy cu broderie ECJ",
        "prefilled_state": {"culoare_principala": "navy", "guler": "polo"},
    }]))
    r = client.post("/email-agent/fetch", data={"date_start": "2026-06-01", "date_end": "2026-06-12"})
    assert r.status_code == 200
    assert "tricou" in r.text
    assert "E-CABLAJE" in r.text
    assert "navy" in r.text


def test_fetch_shows_missing_fields(client, fake_llm, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([_make_email()]))
    fake_llm.queue_text(json.dumps([{
        "product_type": "tricou",
        "description": "tricou polo navy",
        "prefilled_state": {"culoare_principala": "navy"},
    }]))
    r = client.post("/email-agent/fetch", data={"date_start": "2026-06-01", "date_end": "2026-06-12"})
    assert r.status_code == 200
    assert "material" in r.text


def test_fetch_groups_by_email(client, fake_llm, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([_make_email()]))
    fake_llm.queue_text(json.dumps([
        {"product_type": "tricou", "description": "polo navy", "prefilled_state": {"culoare_principala": "navy"}},
        {"product_type": "tricou", "description": "tricou alb", "prefilled_state": {"culoare_principala": "alb"}},
    ]))
    r = client.post("/email-agent/fetch", data={"date_start": "2026-06-01", "date_end": "2026-06-12"})
    assert r.status_code == 200
    assert r.text.count("E-CABLAJE") == 1


def test_fetch_empty_interval(client, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([]))
    r = client.post("/email-agent/fetch", data={"date_start": "2026-06-01", "date_end": "2026-06-12"})
    assert r.status_code == 200
    assert "Niciun email" in r.text


def test_create_session_from_request(client, fake_llm):
    prefilled = {"culoare_principala": "navy", "branding": {"tehnica": "broderie"}}
    fake_llm.queue_text(json.dumps({
        "state": prefilled,
        "intrebari": [{"camp": "material", "intrebare": "Ce material?"}],
        "done": False,
    }))
    r = client.post("/email-agent/create-session", data={
        "product_type": "tricou",
        "description": "tricou polo navy cu broderie ECJ",
        "prefilled_state_json": json.dumps(prefilled),
    })
    assert r.status_code == 200
    assert "HX-Redirect" in r.headers
    assert r.headers["HX-Redirect"].startswith("/sessions/")


def test_create_session_has_prefilled_state(client, fake_llm):
    prefilled = {"culoare_principala": "navy"}
    fake_llm.queue_text(json.dumps({
        "state": {"culoare_principala": "navy"},
        "intrebari": [{"camp": "material", "intrebare": "Ce material?"}],
        "done": False,
    }))
    r = client.post("/email-agent/create-session", data={
        "product_type": "tricou",
        "description": "tricou polo navy",
        "prefilled_state_json": json.dumps(prefilled),
    })
    session_url = r.headers["HX-Redirect"]
    r2 = client.get(session_url)
    assert r2.status_code == 200
    assert "navy" in r2.text
