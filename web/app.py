import io
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageChops
from starlette.exceptions import HTTPException as StarletteHTTPException

# Load .env so ANTHROPIC_API_KEY is available even when the app is imported
# directly (uvicorn web.app:app, tests) without going through main.py.
load_dotenv()

from agents import discovery, inspector
from agents.llm_client import LLMClient
from db import repository
from email_agent.gmail_client import GmailClient, authorized_address
from email_agent import email_extractor
from image_matcher.engine import analyze_sim, compare_real
from schemas import loader


BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
import html as _html
from markupsafe import Markup
TEMPLATES.env.filters["json_attr"] = lambda v: Markup(_html.escape(json.dumps(v, ensure_ascii=False)))


DATABASE_PATH = os.environ.get("DATABASE_PATH", "./ciptronic.db")
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(BASE_DIR.parent / "uploads")))
SCHEMA_PATH = BASE_DIR.parent / "db" / "schema.sql"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

MAX_ROUNDS = 5
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
_llm_singleton: Any = None
_gmail_singleton: Any = None


def get_llm_client() -> Any:
    """Lazily build a singleton LLMClient. Tests patch this function."""
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = LLMClient()
    return _llm_singleton


def get_gmail_client() -> Any:
    """Lazily build a singleton GmailClient. Tests patch this function."""
    global _gmail_singleton
    if _gmail_singleton is None:
        _gmail_singleton = GmailClient(
            image_save_dir=str(UPLOADS_DIR / "email_images")
        )
    return _gmail_singleton


def connected_email() -> str | None:
    """Best-effort Gmail address already authorized (None if not yet / on error).
    Never triggers interactive OAuth; patchable in tests."""
    try:
        return authorized_address()
    except Exception:
        return None


app = FastAPI(title="Ciptronic Product Validator")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Browsers (Accept: text/html) get a friendly error page instead of the raw
    JSON {"detail": ...}; API clients and tests (Accept: */*) keep the JSON. The
    status code is preserved either way."""
    if "text/html" in request.headers.get("accept", ""):
        return TEMPLATES.TemplateResponse(
            request,
            "error.html",
            {"status_code": exc.status_code, "detail": exc.detail},
            status_code=exc.status_code,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def init_database() -> None:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@app.on_event("startup")
def _startup() -> None:
    init_database()


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    today = date.today()
    return TEMPLATES.TemplateResponse(
        request, "index.html",
        {
            "connected_email": connected_email(),
            # Default the e-mail interval to the previous week (today-7 → today).
            "default_date_start": (today - timedelta(days=7)).isoformat(),
            "default_date_end": today.isoformat(),
        },
    )


@app.get("/sessions/new", response_class=HTMLResponse)
def sessions_new(request: Request):
    return TEMPLATES.TemplateResponse(
        request,
        "sessions_new.html",
        {"product_types": loader.available_product_types()},
    )


@app.get("/healthz", response_class=Response)
def healthz():
    return Response(content="ok", media_type="text/plain")


@app.post("/sessions")
def create_session(product_type: str = Form(...), initial_description: str = Form(...)):
    schema = loader.load_schema(product_type)
    initial_state = loader.empty_state(schema)

    llm = get_llm_client()
    system, user = discovery.build_messages(
        schema=schema, initial_description=initial_description,
        state=initial_state, history=[],
    )
    raw = llm.complete_text(system=system, user=user)
    step = discovery.parse_response(raw)

    with get_conn() as conn:
        sid = repository.create_session(conn, product_type, initial_description)
        history = [{"round": 1, "questions": step.intrebari, "answers": None}]
        repository.update_session_state(conn, sid, step.state, history, rounds=1)
        if step.done:
            complete, _ = discovery.is_schema_complete(schema, step.state)
            if complete:
                repository.finalize_session(conn, sid)

    return Response(status_code=200, headers={"HX-Redirect": f"/sessions/{sid}"})


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
def view_session(session_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_session(conn, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")

    schema = loader.load_schema(row["product_type"])
    state = json.loads(row["state_json"])
    history = json.loads(row["history_json"])
    last_questions = history[-1]["questions"] if history else []

    ctx = _build_session_context(
        session_id=session_id,
        product_type=row["product_type"],
        initial_description=row["initial_description"],
        schema=schema, state=state,
        intrebari=last_questions, rounds_used=row["rounds_used"],
        done=(row["status"] == "complete"),
    )
    return TEMPLATES.TemplateResponse(request, "session.html", ctx)


@app.post("/sessions/{session_id}/answer", response_class=HTMLResponse)
async def submit_answers(session_id: str, request: Request):
    form = await request.form()
    answers = {k[len("answer."):]: v for k, v in form.items() if k.startswith("answer.")}

    with get_conn() as conn:
        row = repository.get_session(conn, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        if row["status"] == "complete":
            raise HTTPException(status_code=409, detail="Sesiune deja completă")

        schema = loader.load_schema(row["product_type"])
        state = json.loads(row["state_json"])
        history = json.loads(row["history_json"])
        rounds = row["rounds_used"]

        merged_state = discovery.merge_answers(state, answers)
        if history:
            history[-1]["answers"] = answers

        next_round = rounds + 1
        if next_round > MAX_ROUNDS:
            repository.update_session_state(conn, session_id, merged_state, history, rounds=MAX_ROUNDS)
            repository.finalize_session(conn, session_id)
            ctx = _build_session_context(
                session_id=session_id,
                product_type=row["product_type"],
                initial_description=row["initial_description"],
                schema=schema, state=merged_state,
                intrebari=[], rounds_used=MAX_ROUNDS, done=True,
            )
            return TEMPLATES.TemplateResponse(request, "_session_body.html", ctx)

        llm = get_llm_client()
        system, user = discovery.build_messages(
            schema=schema, initial_description=row["initial_description"],
            state=merged_state, history=history,
        )
        raw = llm.complete_text(system=system, user=user)
        step = discovery.parse_response(raw)

        history.append({"round": next_round, "questions": step.intrebari, "answers": None})
        complete, _ = discovery.is_schema_complete(schema, step.state)
        is_done = step.done and complete

        repository.update_session_state(conn, session_id, step.state, history, rounds=next_round)
        if is_done:
            repository.finalize_session(conn, session_id)

        ctx = _build_session_context(
            session_id=session_id,
            product_type=row["product_type"],
            initial_description=row["initial_description"],
            schema=schema, state=step.state,
            intrebari=step.intrebari, rounds_used=next_round, done=is_done,
        )
        return TEMPLATES.TemplateResponse(request, "_session_body.html", ctx)


def _build_session_context(*, session_id, product_type, initial_description,
                           schema, state, intrebari, rounds_used, done) -> dict:
    applicable = loader.applicable_leaf_keys(schema, state)
    field_state = []
    for f in schema["fields"]:
        if f.get("type") == "object":
            for sub in f["subfields"]:
                dotted = f"{f['key']}.{sub['key']}"
                if dotted not in applicable:
                    continue
                value = (state.get(f["key"]) or {}).get(sub["key"])
                field_state.append(_field_entry(f"{f['label']} → {sub['label']}", value))
        else:
            field_state.append(_field_entry(f["label"], state.get(f["key"])))

    return {
        "session_id": session_id,
        "product_type": product_type, "initial_description": initial_description,
        "field_state": field_state, "intrebari": intrebari,
        "rounds_used": rounds_used, "done": done,
    }


def _spec_field_list(schema, state) -> list[dict]:
    """Flatten the spec into readable {label, value, filled} rows (same logic as
    the session checklist) so the validate page can list them instead of raw
    JSON."""
    applicable = loader.applicable_leaf_keys(schema, state)
    fields = []
    for f in schema["fields"]:
        if f.get("type") == "object":
            for sub in f["subfields"]:
                dotted = f"{f['key']}.{sub['key']}"
                if dotted not in applicable:
                    continue
                value = (state.get(f["key"]) or {}).get(sub["key"])
                fields.append(_field_entry(f"{f['label']} → {sub['label']}", value))
        else:
            fields.append(_field_entry(f["label"], state.get(f["key"])))
    return fields


def _field_entry(label: str, value) -> dict:
    filled = value is not None and value != "" and value != []
    display = ", ".join(str(v) for v in value) if isinstance(value, list) else (str(value) if value is not None else "")
    return {"label": label, "filled": filled, "display_value": display}


@app.get("/sessions/{session_id}/validate", response_class=HTMLResponse)
def validate_page(session_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_session(conn, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        if row["status"] != "complete":
            raise HTTPException(status_code=409, detail="Sesiunea nu e completă încă")

    spec = json.loads(row["state_json"])
    schema = loader.load_schema(row["product_type"])
    return TEMPLATES.TemplateResponse(
        request,
        "validate.html",
        {
            "session_id": session_id,
            "spec_fields": _spec_field_list(schema, spec),
        },
    )


@app.post("/sessions/{session_id}/validate")
async def run_validation(
    session_id: str, request: Request,
    image1: UploadFile = File(...),
    image2: UploadFile | None = File(None),
    image3: UploadFile | None = File(None),
    image4: UploadFile | None = File(None),
):
    with get_conn() as conn:
        row = repository.get_session(conn, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        if row["status"] != "complete":
            raise HTTPException(status_code=409, detail="Sesiunea nu e completă încă")

        spec = json.loads(row["state_json"])
        schema = loader.load_schema(row["product_type"])

        # Browsers send untouched optional file inputs as empty parts
        # (filename=""), which FastAPI binds to an UploadFile rather than None.
        # Skip those so we never send an empty image to the vision API.
        upload_files = [f for f in (image1, image2, image3, image4) if f is not None and f.filename]
        session_uploads = UPLOADS_DIR / session_id
        session_uploads.mkdir(parents=True, exist_ok=True)
        image_paths: list[str] = []
        for i, f in enumerate(upload_files, start=1):
            content = await f.read()
            if len(content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(status_code=413, detail=f"Poza {i} depășește 5MB")
            ext = _ext_for_upload(f)
            path = session_uploads / f"img{i}{ext}"
            path.write_bytes(content)
            image_paths.append(str(path))

        llm = get_llm_client()
        system, content_blocks = inspector.build_messages(spec=spec, image_paths=image_paths)
        raw = llm.complete_vision(system=system, content_blocks=content_blocks)
        try:
            report = inspector.parse_report(raw, schema, spec)
        except ValueError as e:
            raise HTTPException(status_code=502, detail=f"Răspuns Inspector invalid: {e}")

        rid = repository.save_report(
            conn, session_id=session_id, spec=spec, image_paths=image_paths,
            conform=[_item_to_dict(i) for i in report.conform],
            neconform=[_item_to_dict(i) for i in report.neconform],
            nevizibil=[_item_to_dict(i) for i in report.nevizibil],
            raw=raw,
        )

    return Response(status_code=303, headers={"Location": f"/reports/{rid}"})


def _ext_for_upload(upload) -> str:
    """Map an uploaded image to a file extension that matches its real format,
    so the media_type sent to the vision API matches the bytes. Prefer the
    browser content_type; fall back to the filename suffix."""
    ct = (upload.content_type or "").lower()
    if ct == "image/png":
        return ".png"
    if ct == "image/webp":
        return ".webp"
    if ct in ("image/jpeg", "image/jpg"):
        return ".jpg"
    name = (upload.filename or "").lower()
    if name.endswith(".png"):
        return ".png"
    if name.endswith(".webp"):
        return ".webp"
    return ".jpg"


def _item_to_dict(item) -> dict:
    return {
        "camp": item.camp, "valoare_asteptata": item.valoare_asteptata,
        "valoare_observata": item.valoare_observata,
        "incredere": item.incredere, "motiv": item.motiv,
    }


@app.get("/reports/{report_id}/image/{idx}")
def report_image(report_id: str, idx: int):
    """Serve one of the product photos uploaded for this validation report so
    the report can pin them while the user reads the criteria. Scoped to the
    report's own image list."""
    with get_conn() as conn:
        row = repository.get_report(conn, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Raport inexistent")
    paths = json.loads(row["image_paths_json"])
    if idx < 0 or idx >= len(paths) or not Path(paths[idx]).is_file():
        raise HTTPException(status_code=404, detail="Imagine indisponibilă")
    return FileResponse(Path(paths[idx]))


@app.get("/reports/{report_id}", response_class=HTMLResponse)
def view_report(report_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_report(conn, report_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Raport inexistent")

    image_count = len(json.loads(row["image_paths_json"]))
    image_urls = [
        {"url": f"/reports/{report_id}/image/{i}", "label": f"Poza {i + 1}"}
        for i in range(image_count)
    ]
    return TEMPLATES.TemplateResponse(
        request,
        "report.html",
        {
            "report_id": report_id,
            "conform": json.loads(row["conform_json"]),
            "neconform": json.loads(row["neconform_json"]),
            "nevizibil": json.loads(row["nevizibil_json"]),
            "image_urls": image_urls,
        },
    )


@app.get("/matches/new", response_class=HTMLResponse)
def match_new(request: Request):
    return TEMPLATES.TemplateResponse(request, "match_new.html")


def _upload_ext(upload: UploadFile) -> str:
    """Pick a file extension from the upload's declared type/filename."""
    if upload.filename and upload.filename.lower().endswith(".webp"):
        return ".webp"
    return ".png" if upload.content_type == "image/png" else ".jpg"


@app.post("/matches")
async def create_match(sim: UploadFile = File(...)):
    content = await sim.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Mockup-ul depășește 5MB")

    import uuid as _uuid
    match_id_prefix = str(_uuid.uuid4())
    match_uploads = UPLOADS_DIR / "match" / match_id_prefix
    match_uploads.mkdir(parents=True, exist_ok=True)

    sim_path = match_uploads / f"sim{_upload_ext(sim)}"
    sim_path.write_bytes(content)

    try:
        sim_report = analyze_sim(sim_path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"analyze_sim a eșuat: {e}")

    with get_conn() as conn:
        match_id = repository.create_match_session(
            conn, sim_image_path=str(sim_path), sim_report=sim_report,
        )

    return Response(status_code=303, headers={"Location": f"/matches/{match_id}"})


@app.get("/matches/{match_id}", response_class=HTMLResponse)
def view_match(match_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Match inexistent")

    status = row["status"]
    if status == "complete":
        # Already compared — send the user to the report instead of re-rendering
        # the upload form. Re-showing it after a back/refresh/double-submit lets
        # them POST to /real again and hit the 'awaiting_real' guard with a
        # confusing 409 ("Match nu așteaptă poză reală").
        return Response(
            status_code=303, headers={"Location": f"/matches/{match_id}/report"}
        )
    if status == "failed":
        # The match can no longer accept a photo; offer a clean restart rather
        # than a dead upload form that would also 409 on submit.
        return TEMPLATES.TemplateResponse(
            request,
            "match_new.html",
            {"error": "Comparația anterioară a eșuat. Încarcă din nou mockup-ul pentru a relua."},
        )

    sim_report = json.loads(row["sim_report_json"])
    criteria = sim_report.get("criteria", [])

    return TEMPLATES.TemplateResponse(
        request,
        "match_wait.html",
        {"match_id": match_id, "criteria": criteria},
    )


@app.post("/matches/{match_id}/real")
async def upload_match_real(match_id: str, real: UploadFile = File(...)):
    """Upload the real product photo (first time) or replace it on a finished
    match. Either way the mockup criteria are re-compared against the new photo.
    The new image is staged to a temp file so a failed comparison never destroys
    an existing report."""
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Match inexistent")
        if row["status"] not in ("awaiting_real", "complete"):
            raise HTTPException(status_code=409, detail="Match nu așteaptă poză reală")

        content = await real.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Poza reală depășește 5MB")

        sim_path = Path(row["sim_image_path"])
        match_dir = sim_path.parent
        ext = _upload_ext(real)
        staged = match_dir / f"real_new{ext}"
        staged.write_bytes(content)

        sim_report = json.loads(row["sim_report_json"])
        try:
            compare_report = compare_real(sim_report, sim_path, staged, max_tokens=8192)
        except Exception as e:
            staged.unlink(missing_ok=True)
            # First upload failing → mark failed (view_match offers a restart).
            # Replacing on an already-complete match → keep the old report intact.
            if row["status"] == "awaiting_real":
                repository.fail_match_session(conn, match_id)
            raise HTTPException(status_code=502, detail=f"compare_real a eșuat: {e}")

        real_path = match_dir / f"real{ext}"
        staged.replace(real_path)
        old_real = row["real_image_path"]
        if old_real and str(real_path) != old_real:
            Path(old_real).unlink(missing_ok=True)
        repository.update_match_compare_report(
            conn, match_id, real_image_path=str(real_path), compare_report=compare_report,
        )

    return Response(status_code=303, headers={"Location": f"/matches/{match_id}/report"})


@app.post("/matches/{match_id}/sim")
async def replace_match_sim(match_id: str, sim: UploadFile = File(...)):
    """Replace the mockup and re-extract its criteria. If the match already has a
    real photo (status complete), the new criteria are also re-compared against
    it so the report table stays in sync. The new mockup is staged to a temp file
    so a failed re-analysis leaves the existing match untouched."""
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Match inexistent")
        if row["status"] not in ("awaiting_real", "complete"):
            raise HTTPException(status_code=409, detail="Match nu poate fi modificat")

        content = await sim.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Mockup-ul depășește 5MB")

        match_dir = Path(row["sim_image_path"]).parent
        ext = _upload_ext(sim)
        staged = match_dir / f"sim_new{ext}"
        staged.write_bytes(content)

        real_str = row["real_image_path"]
        recompare = row["status"] == "complete" and bool(real_str)
        try:
            new_sim_report = analyze_sim(staged)
            new_compare = (
                compare_real(new_sim_report, staged, Path(real_str), max_tokens=8192)
                if recompare else None
            )
        except Exception as e:
            staged.unlink(missing_ok=True)
            raise HTTPException(status_code=502, detail=f"Re-analiza mockup-ului a eșuat: {e}")

        new_sim_path = match_dir / f"sim{ext}"
        staged.replace(new_sim_path)
        if str(new_sim_path) != row["sim_image_path"]:
            Path(row["sim_image_path"]).unlink(missing_ok=True)
        repository.update_match_sim(conn, match_id, str(new_sim_path), new_sim_report)
        if new_compare is not None:
            repository.update_match_compare_report(
                conn, match_id, real_image_path=real_str, compare_report=new_compare,
            )

    target = f"/matches/{match_id}/report" if recompare else f"/matches/{match_id}"
    return Response(status_code=303, headers={"Location": target})


def _trim_solid_border(data: bytes, *, tolerance: int = 30, max_trim: float = 0.2) -> bytes | None:
    """If the image has a uniform solid-colour frame (e.g. a screenshot exported
    on a dark background), return PNG bytes with that frame cropped off.

    Returns None — meaning "serve the original untouched" — when there is no
    clear frame, when the bytes aren't a readable image, when the image is a
    single flat colour, or when cropping would remove more than `max_trim` of
    either dimension (a guard against eating real product content). Pure and
    display-only: never mutates the stored file."""
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    rgb = im.convert("RGB")
    w, h = rgb.size
    if w < 8 or h < 8:
        return None
    corners = [rgb.getpixel((0, 0)), rgb.getpixel((w - 1, 0)),
               rgb.getpixel((0, h - 1)), rgb.getpixel((w - 1, h - 1))]
    base = corners[0]
    # Only treat it as a frame when all four corners share (near) one colour.
    if any(abs(a - b) > tolerance for c in corners[1:] for a, b in zip(base, c)):
        return None
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, base))
    mask = diff.convert("L").point(lambda p: 255 if p > tolerance else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return None  # image is entirely the frame colour — leave it alone
    left, top, right, bottom = bbox
    if left == 0 and top == 0 and right == w and bottom == h:
        return None  # nothing to trim
    if (left > w * max_trim or (w - right) > w * max_trim or
            top > h * max_trim or (h - bottom) > h * max_trim):
        return None  # would crop too aggressively — likely not a frame
    out = io.BytesIO()
    rgb.crop(bbox).save(out, format="PNG")
    return out.getvalue()


@app.get("/matches/{match_id}/image/{kind}")
def match_image(match_id: str, kind: str):
    """Serve a match's stored mockup or real photo so the report can show them
    side by side. Scoped to the two known image slots — never exposes the
    wider uploads directory. A uniform solid-colour frame (e.g. a navy export
    background) is trimmed for display only; the stored file is untouched."""
    if kind not in ("sim", "real"):
        raise HTTPException(status_code=404, detail="Imagine inexistentă")
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Match inexistent")
    path_str = row["sim_image_path"] if kind == "sim" else row["real_image_path"]
    if not path_str or not Path(path_str).is_file():
        raise HTTPException(status_code=404, detail="Imagine indisponibilă")
    path = Path(path_str)
    trimmed = _trim_solid_border(path.read_bytes())
    if trimmed is not None:
        return Response(content=trimmed, media_type="image/png")
    return FileResponse(path)


@app.get("/matches/{match_id}/report", response_class=HTMLResponse)
def view_match_report(match_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Match inexistent")
        if row["status"] != "complete":
            raise HTTPException(status_code=409, detail="Raport indisponibil — match nu e complet")

    compare_report = json.loads(row["compare_report_json"])

    return TEMPLATES.TemplateResponse(
        request,
        "match_report.html",
        {
            "match_id": match_id,
            "rows": compare_report.get("rows", []),
            "summary": compare_report.get("summary", {"matched": 0, "mismatched": 0}),
            "sim_image_url": f"/matches/{match_id}/image/sim",
            "real_image_url": f"/matches/{match_id}/image/real",
        },
    )


@app.post("/email-agent/fetch", response_class=HTMLResponse)
def email_agent_fetch(
    request: Request,
    date_start: str = Form(...),
    date_end: str = Form(...),
):
    try:
        gmail = get_gmail_client()
    except FileNotFoundError:
        return HTMLResponse(
            '<div class="email-results-empty">'
            '<strong>Gmail neconfigurat.</strong> Adaugă <code>credentials.json</code> '
            'în directorul proiectului și repornește serverul.'
            '</div>'
        )
    messages = gmail.fetch_emails(date_start, date_end)

    try:
        account = gmail.get_address()
    except Exception:
        account = None

    if not messages:
        return TEMPLATES.TemplateResponse(
            request, "email_requests.html",
            {"groups": [], "date_start": date_start, "date_end": date_end, "account": account},
        )

    llm = get_llm_client()
    groups = []
    for msg in messages:
        extracted = email_extractor.extract(msg, llm)
        if extracted:
            groups.append({"email": msg, "requests": extracted})

    return TEMPLATES.TemplateResponse(
        request, "email_requests.html",
        {"groups": groups, "date_start": date_start, "date_end": date_end, "account": account},
    )


@app.post("/email-agent/create-session")
def email_agent_create_session(
    product_type: str = Form(...),
    description: str = Form(...),
    prefilled_state_json: str = Form(...),
):
    prefilled_state = json.loads(prefilled_state_json)
    schema = loader.load_schema(product_type)

    llm = get_llm_client()
    system, user = discovery.build_messages(
        schema=schema,
        initial_description=description,
        state=prefilled_state,
        history=[],
    )
    raw = llm.complete_text(system=system, user=user)
    step = discovery.parse_response(raw)

    merged_state = discovery.merge_answers(prefilled_state, step.state)

    with get_conn() as conn:
        sid = repository.create_session(conn, product_type, description)
        history = [{"round": 1, "questions": step.intrebari, "answers": None}]
        repository.update_session_state(conn, sid, merged_state, history, rounds=1)
        if step.done:
            complete, _ = discovery.is_schema_complete(schema, merged_state)
            if complete:
                repository.finalize_session(conn, sid)

    return Response(status_code=200, headers={"HX-Redirect": f"/sessions/{sid}"})


@app.get("/email-agent/image/{gmail_id}/{idx}")
def email_image(gmail_id: str, idx: int):
    path = UPLOADS_DIR / "email_images" / gmail_id / f"{idx:02d}.jpg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Imagine indisponibilă")
    return FileResponse(path)
