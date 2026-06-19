def test_landing_page_is_chooser(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Am o descriere" in r.text
    assert "Am un mockup" in r.text
    assert "/sessions/new" in r.text
    assert "/matches/new" in r.text


def test_email_dates_default_to_previous_week(client):
    import re
    from datetime import date, timedelta
    r = client.get("/")
    start = re.search(r'name="date_start" value="(\d{4}-\d{2}-\d{2})"', r.text)
    end = re.search(r'name="date_end" value="(\d{4}-\d{2}-\d{2})"', r.text)
    assert start and end, "both date inputs should carry a default value"
    d_start = date.fromisoformat(start.group(1))
    d_end = date.fromisoformat(end.group(1))
    assert d_end == date.today()
    assert (d_end - d_start).days == 7


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


def test_post_validate_ignores_empty_optional_file_slots(client, fake_llm):
    """Browsers submit untouched optional <input type=file> as empty parts
    (filename="", no content), not as absent fields. These must be skipped so
    no empty image block is sent to the vision API. Built as a raw multipart
    body because TestClient/httpx drops empty-filename parts, unlike a browser."""
    sid = _complete_session(client, fake_llm)
    fake_llm.queue_vision((FIXTURES / "inspector_full.json").read_text(encoding="utf-8"))

    boundary = "----testboundary123"
    jpeg = _tiny_jpeg_bytes()
    parts = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="image1"; filename="front.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + jpeg + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="image2"; filename=""\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
        "\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    r = client.post(
        f"/sessions/{sid}/validate",
        content=parts,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # exactly one image block reached the LLM; the empty slot was dropped
    _system, content_blocks = fake_llm.vision_calls[0]
    image_blocks = [b for b in content_blocks if b.get("type") == "image"]
    assert len(image_blocks) == 1


def test_post_validate_preserves_webp_media_type(client, fake_llm):
    """A WEBP upload must be sent to the vision API with media_type image/webp.
    Saving it as .jpg made _media_type_for report image/jpeg, which the API
    rejects because the bytes are webp."""
    sid = _complete_session(client, fake_llm)
    fake_llm.queue_vision((FIXTURES / "inspector_full.json").read_text(encoding="utf-8"))
    files = {"image1": ("photo.webp", io.BytesIO(_tiny_jpeg_bytes()), "image/webp")}
    r = client.post(f"/sessions/{sid}/validate", files=files, follow_redirects=False)
    assert r.status_code == 303
    _system, content_blocks = fake_llm.vision_calls[0]
    image_block = next(b for b in content_blocks if b.get("type") == "image")
    assert image_block["source"]["media_type"] == "image/webp"


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


def test_get_matches_new_shows_upload_form(client):
    r = client.get("/matches/new")
    assert r.status_code == 200
    assert "Încarcă mockup-ul" in r.text
    assert 'name="sim"' in r.text


def test_post_matches_runs_analyze_sim_and_redirects(client, fake_image_engine):
    fake_image_engine.sim_response = {
        "criteria": [
            {"id": "color", "label": "Color principal", "description": "navy uniform"},
            {"id": "logo_pos", "label": "Logo poziție", "description": "piept stâng"},
        ]
    }
    files = {"sim": ("mockup.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post("/matches", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"].startswith("/matches/")
    assert len(fake_image_engine.analyze_calls) == 1


def test_get_match_session_shows_criteria_and_real_upload(client, fake_image_engine):
    fake_image_engine.sim_response = {
        "criteria": [{"id": "color", "label": "Color", "description": "navy"}]
    }
    files = {"sim": ("mockup.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post("/matches", files=files, follow_redirects=False)
    match_url = r.headers["Location"]

    r = client.get(match_url)
    assert r.status_code == 200
    assert "Criterii detectate" in r.text
    assert "Color" in r.text
    assert 'name="real"' in r.text


def test_post_match_real_runs_compare_and_redirects_to_report(client, fake_image_engine):
    fake_image_engine.sim_response = {"criteria": [{"id": "color", "label": "Color", "description": "x"}]}
    fake_image_engine.compare_response = {
        "rows": [{"criterion": "Color", "sim_value": "navy", "real_value": "navy",
                  "match": True, "match_type": "exact", "confidence": "high", "note": ""}],
        "summary": {"matched": 1, "mismatched": 0, "total": 1},
    }
    files = {"sim": ("mockup.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post("/matches", files=files, follow_redirects=False)
    match_id = r.headers["Location"].rsplit("/", 1)[-1]

    files = {"real": ("real.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/matches/{match_id}/real", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"] == f"/matches/{match_id}/report"
    assert len(fake_image_engine.compare_calls) == 1
    # compare_real(sim_report, sim_path, real_path) — guard the argument order;
    # both image paths must be passed so the model compares them visually.
    recorded_sim_report, recorded_sim_path, recorded_real_path = (
        fake_image_engine.compare_calls[0]
    )
    assert isinstance(recorded_sim_report, dict) and "criteria" in recorded_sim_report
    assert recorded_sim_path.endswith((".jpg", ".jpeg", ".png", ".webp"))
    assert recorded_real_path.endswith((".jpg", ".jpeg", ".png", ".webp"))


def test_match_report_shows_rows_table(client, fake_image_engine):
    fake_image_engine.sim_response = {"criteria": [{"id": "c1", "label": "Color", "description": "x"}]}
    fake_image_engine.compare_response = {
        "rows": [{"criterion": "Color", "sim_value": "navy", "real_value": "navy",
                  "match": True, "match_type": "exact", "confidence": "high", "note": ""}],
        "summary": {"matched": 1, "mismatched": 0, "total": 1},
    }
    files = {"sim": ("m.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post("/matches", files=files, follow_redirects=False)
    match_id = r.headers["Location"].rsplit("/", 1)[-1]
    files = {"real": ("r.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    client.post(f"/matches/{match_id}/real", files=files, follow_redirects=False)

    r = client.get(f"/matches/{match_id}/report")
    assert r.status_code == 200
    assert "Color" in r.text
    assert "navy" in r.text
    assert "exact" in r.text


def test_get_completed_match_redirects_to_report(client, fake_image_engine):
    """Revisiting a finished match (back button, refresh, double-submit) must NOT
    re-show the real-photo upload form. Doing so lets the user POST to an
    already-complete match, which the status guard rejects with a confusing 409.
    A completed match should redirect to its report instead."""
    fake_image_engine.sim_response = {"criteria": [{"id": "c1", "label": "Color", "description": "x"}]}
    fake_image_engine.compare_response = {
        "rows": [{"criterion": "Color", "sim_value": "navy", "real_value": "navy",
                  "match": True, "match_type": "exact", "confidence": "high", "note": ""}],
        "summary": {"matched": 1, "mismatched": 0, "total": 1},
    }
    files = {"sim": ("m.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    match_id = client.post("/matches", files=files, follow_redirects=False).headers["Location"].rsplit("/", 1)[-1]
    files = {"real": ("r.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    client.post(f"/matches/{match_id}/real", files=files, follow_redirects=False)

    # Match is now 'complete' — revisiting it must redirect to the report,
    # never re-render the upload form (which would invite a 409 on re-submit).
    r = client.get(f"/matches/{match_id}", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"] == f"/matches/{match_id}/report"


def test_errors_render_html_for_browsers_json_for_api(client):
    """A browser (Accept: text/html) gets a friendly HTML error page instead of
    the raw JSON {"detail": ...}; API clients keep JSON. Status is preserved."""
    r = client.get("/matches/does-not-exist", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]
    assert "A apărut o problemă" in r.text
    assert "Match inexistent" in r.text

    r = client.get("/matches/does-not-exist")  # TestClient default Accept: */*
    assert r.status_code == 404
    assert r.json()["detail"] == "Match inexistent"


def test_failed_match_offers_restart_not_dead_form(client, fake_image_engine, monkeypatch):
    """A match whose comparison failed can never accept a photo again; revisiting
    it must offer a clean restart (match_new + message), not the dead upload form
    that would also 409 on submit."""
    fake_image_engine.sim_response = {"criteria": [{"id": "c1", "label": "Color", "description": "x"}]}
    files = {"sim": ("m.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    match_id = client.post("/matches", files=files, follow_redirects=False).headers["Location"].rsplit("/", 1)[-1]

    from web import app as web_app
    monkeypatch.setattr(web_app, "compare_real", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("vision down")))
    files = {"real": ("r.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/matches/{match_id}/real", files=files, follow_redirects=False)
    assert r.status_code == 502  # match flipped to 'failed'

    r = client.get(f"/matches/{match_id}", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 200
    assert "Încarcă mockup" in r.text   # match_new page, not the upload form
    assert "a eșuat" in r.text          # friendly restart message
    assert 'name="real"' not in r.text  # no dead real-photo form


def test_match_image_trims_solid_navy_border(client, fake_image_engine):
    """The report's image route strips a uniform solid-colour frame (e.g. a
    screenshot exported on a navy background) for display, without altering the
    stored upload."""
    from PIL import Image as _Image
    im = _Image.new("RGB", (120, 120), (255, 255, 255))
    for x in list(range(12)) + list(range(108, 120)):
        for y in range(120):
            im.putpixel((x, y), (30, 41, 59))  # 12px navy bars left/right
    for x in range(40, 80):
        for y in range(50, 70):
            im.putpixel((x, y), (200, 50, 20))  # interior content
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)

    fake_image_engine.sim_response = {"criteria": [{"id": "c1", "label": "X", "description": "y"}]}
    files = {"sim": ("m.png", buf, "image/png")}
    match_id = client.post("/matches", files=files, follow_redirects=False).headers["Location"].rsplit("/", 1)[-1]

    r = client.get(f"/matches/{match_id}/image/sim")
    assert r.status_code == 200
    served = _Image.open(io.BytesIO(r.content))
    assert served.width == 96  # 12px navy trimmed from each side (120 - 24)


def _complete_match(client, fake_image_engine):
    """Create a match and run it through to a complete comparison; return its id."""
    fake_image_engine.sim_response = {"criteria": [{"id": "c1", "label": "Color", "description": "x"}]}
    fake_image_engine.compare_response = {
        "rows": [{"criterion": "Color", "sim_value": "navy", "real_value": "navy",
                  "match": True, "match_type": "exact", "confidence": "high", "note": ""}],
        "summary": {"matched": 1, "mismatched": 0, "total": 1},
    }
    files = {"sim": ("m.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    mid = client.post("/matches", files=files, follow_redirects=False).headers["Location"].rsplit("/", 1)[-1]
    files = {"real": ("r.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    client.post(f"/matches/{mid}/real", files=files, follow_redirects=False)
    return mid


def test_replace_real_on_complete_recompares_and_updates_table(client, fake_image_engine):
    mid = _complete_match(client, fake_image_engine)
    assert len(fake_image_engine.compare_calls) == 1

    fake_image_engine.compare_response = {
        "rows": [{"criterion": "Color", "sim_value": "navy", "real_value": "RED",
                  "match": False, "match_type": "partial", "confidence": "high", "note": "diff"}],
        "summary": {"matched": 0, "mismatched": 1, "total": 1},
    }
    files = {"real": ("r2.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/matches/{mid}/real", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"] == f"/matches/{mid}/report"
    assert len(fake_image_engine.compare_calls) == 2  # re-compared
    assert len(fake_image_engine.analyze_calls) == 1  # mockup NOT re-analyzed
    rep = client.get(f"/matches/{mid}/report")
    assert "RED" in rep.text


def test_replace_sim_on_complete_reanalyzes_and_recompares(client, fake_image_engine):
    mid = _complete_match(client, fake_image_engine)
    assert len(fake_image_engine.analyze_calls) == 1 and len(fake_image_engine.compare_calls) == 1

    fake_image_engine.sim_response = {"criteria": [
        {"id": "c1", "label": "Logo", "description": "z"},
        {"id": "c2", "label": "Size", "description": "L"},
    ]}
    files = {"sim": ("m2.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post(f"/matches/{mid}/sim", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"] == f"/matches/{mid}/report"
    assert len(fake_image_engine.analyze_calls) == 2  # re-analyzed
    assert len(fake_image_engine.compare_calls) == 2  # re-compared with existing real


def test_replace_sim_on_awaiting_real_reanalyzes_only(client, fake_image_engine):
    fake_image_engine.sim_response = {"criteria": [{"id": "c1", "label": "Color", "description": "x"}]}
    files = {"sim": ("m.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    mid = client.post("/matches", files=files, follow_redirects=False).headers["Location"].rsplit("/", 1)[-1]
    assert len(fake_image_engine.analyze_calls) == 1

    fake_image_engine.sim_response = {"criteria": [
        {"id": "c1", "label": "Logo", "description": "z"},
        {"id": "c2", "label": "Size", "description": "L"},
    ]}
    files = {"sim": ("m2.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post(f"/matches/{mid}/sim", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"] == f"/matches/{mid}"  # stays on match_wait
    assert len(fake_image_engine.analyze_calls) == 2
    assert len(fake_image_engine.compare_calls) == 0  # no real photo yet
    page = client.get(f"/matches/{mid}")
    assert "Logo" in page.text and "Size" in page.text


def test_replace_failure_preserves_existing_report(client, fake_image_engine, monkeypatch):
    mid = _complete_match(client, fake_image_engine)

    from web import app as web_app
    monkeypatch.setattr(web_app, "compare_real",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("vision down")))
    files = {"real": ("r2.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/matches/{mid}/real", files=files, follow_redirects=False)
    assert r.status_code == 502
    # Old report must survive: still complete, still reachable, original data intact.
    rep = client.get(f"/matches/{mid}/report")
    assert rep.status_code == 200
    assert "navy" in rep.text
