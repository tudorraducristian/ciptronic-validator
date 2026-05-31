def test_landing_page_is_chooser(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Am o descriere" in r.text
    assert "Am un mockup" in r.text
    assert "/sessions/new" in r.text
    assert "/matches/new" in r.text


def test_sessions_new_page_renders_form(client):
    r = client.get("/sessions/new")
    assert r.status_code == 200
    assert "Începe o specificare" in r.text
    assert "tricou" in r.text.lower()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.text.strip('"') == "ok"


from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "llm_responses"


def _create_session(client, fake_llm):
    fake_llm.queue_text((FIXTURES / "discovery_round1.json").read_text(encoding="utf-8"))
    r = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo pe piept"},
    )
    return r.headers["HX-Redirect"]


def test_create_session_returns_hx_redirect(client, fake_llm):
    fake_llm.queue_text((FIXTURES / "discovery_round1.json").read_text(encoding="utf-8"))
    r = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo"},
    )
    assert r.status_code == 200
    assert "HX-Redirect" in r.headers
    assert r.headers["HX-Redirect"].startswith("/sessions/")


def test_get_session_after_creation_shows_partial_state(client, fake_llm):
    url = _create_session(client, fake_llm)
    r = client.get(url)
    assert r.status_code == 200
    assert "albastru navy" in r.text


def test_submit_answers_returns_partial_with_done_when_llm_finishes(client, fake_llm):
    url = _create_session(client, fake_llm)
    fake_llm.queue_text((FIXTURES / "discovery_round2_done.json").read_text(encoding="utf-8"))
    r = client.post(
        url + "/answer",
        data={
            "answer.material": "bumbac 100%",
            "answer.croiala": "slim",
            "answer.branding.tehnica": "serigrafie",
        },
    )
    assert r.status_code == 200
    assert "Specificare completă" in r.text or "done" in r.text
    assert "Validează cu poze" in r.text
