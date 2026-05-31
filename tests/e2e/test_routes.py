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


import base64
import io


def _tiny_jpeg_bytes() -> bytes:
    jpeg_b64 = (
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQ"
        "EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB/8AAEQgAAQABAwEiAA"
        "IRAQMRAf/EABQAAQAAAAAAAAAAAAAAAAAAAAj/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8"
        "QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAh"
        "EDEQA/AL+AB//Z"
    )
    return base64.b64decode(jpeg_b64)


def _complete_session(client, fake_llm) -> str:
    fake_llm.queue_text((FIXTURES / "discovery_round2_done.json").read_text(encoding="utf-8"))
    r = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo"},
    )
    return r.headers["HX-Redirect"].rsplit("/", 1)[-1]


def test_get_validate_page_shows_upload_form(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    r = client.get(f"/sessions/{sid}/validate")
    assert r.status_code == 200
    assert "image1" in r.text


def test_post_validate_runs_inspector_and_redirects_to_report(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    fake_llm.queue_vision((FIXTURES / "inspector_full.json").read_text(encoding="utf-8"))
    files = {"image1": ("front.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/sessions/{sid}/validate", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"].startswith("/reports/")


def test_report_view_shows_three_zones(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    fake_llm.queue_vision((FIXTURES / "inspector_full.json").read_text(encoding="utf-8"))
    files = {"image1": ("front.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/sessions/{sid}/validate", files=files, follow_redirects=False)
    location = r.headers["Location"]

    r = client.get(location)
    assert r.status_code == 200
    assert "Conform" in r.text
    assert "Neconform" in r.text
    assert "Nevizibil" in r.text
    assert "albastru navy" in r.text
