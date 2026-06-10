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
