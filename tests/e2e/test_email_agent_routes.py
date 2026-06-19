import json
from email_agent.gmail_client import EmailMessage


class FakeGmail:
    def __init__(self, messages, address="owner@corai.ai"):
        self._messages = messages
        self._address = address

    def fetch_emails(self, date_start, date_end):
        return self._messages

    def get_address(self):
        return self._address


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


def test_fetch_shows_connected_account(client, fake_llm, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client",
                        lambda: FakeGmail([_make_email()], address="atelier@corai.ai"))
    fake_llm.queue_text(json.dumps([{
        "product_type": "tricou", "description": "polo navy",
        "prefilled_state": {"culoare_principala": "navy"},
    }]))
    r = client.post("/email-agent/fetch", data={"date_start": "2026-06-01", "date_end": "2026-06-12"})
    assert r.status_code == 200
    assert "atelier@corai.ai" in r.text


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


# ── ruta /email-agent/image/ ──────────────────────────────────────────────────

def test_email_image_route_returns_file(client):
    from web import app as web_app
    from PIL import Image
    from io import BytesIO

    gmail_id = "test-gmail-id-img"
    img_dir = web_app.UPLOADS_DIR / "email_images" / gmail_id
    img_dir.mkdir(parents=True, exist_ok=True)
    buf = BytesIO()
    Image.new("RGB", (10, 10), color=(0, 128, 255)).save(buf, format="JPEG")
    (img_dir / "00.jpg").write_bytes(buf.getvalue())

    r = client.get(f"/email-agent/image/{gmail_id}/0")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_email_image_route_404_when_file_missing(client):
    r = client.get("/email-agent/image/nonexistent-id/0")
    assert r.status_code == 404


def test_email_image_route_404_for_invalid_index(client):
    from web import app as web_app
    from PIL import Image
    from io import BytesIO

    gmail_id = "test-gmail-id-idx"
    img_dir = web_app.UPLOADS_DIR / "email_images" / gmail_id
    img_dir.mkdir(parents=True, exist_ok=True)
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="JPEG")
    (img_dir / "00.jpg").write_bytes(buf.getvalue())

    r = client.get(f"/email-agent/image/{gmail_id}/99")
    assert r.status_code == 404
