import json
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Load .env so ANTHROPIC_API_KEY is available even when the app is imported
# directly (uvicorn web.app:app, tests) without going through main.py.
load_dotenv()

from agents import discovery, inspector
from agents.llm_client import LLMClient
from db import repository
from image_matcher.engine import analyze_sim, compare_real
from schemas import loader


BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./ciptronic.db")
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(BASE_DIR.parent / "uploads")))
SCHEMA_PATH = BASE_DIR.parent / "db" / "schema.sql"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

MAX_ROUNDS = 5
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
_llm_singleton: Any = None


def get_llm_client() -> Any:
    """Lazily build a singleton LLMClient. Tests patch this function."""
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = LLMClient()
    return _llm_singleton


app = FastAPI(title="Ciptronic Product Validator")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


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
    return TEMPLATES.TemplateResponse(request, "index.html")


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


@app.get("/reports/{report_id}", response_class=HTMLResponse)
def view_report(report_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_report(conn, report_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Raport inexistent")

    return TEMPLATES.TemplateResponse(
        request,
        "report.html",
        {
            "report_id": report_id,
            "conform": json.loads(row["conform_json"]),
            "neconform": json.loads(row["neconform_json"]),
            "nevizibil": json.loads(row["nevizibil_json"]),
        },
    )


@app.get("/matches/new", response_class=HTMLResponse)
def match_new(request: Request):
    return TEMPLATES.TemplateResponse(request, "match_new.html")


@app.post("/matches")
async def create_match(sim: UploadFile = File(...)):
    content = await sim.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Mockup-ul depășește 5MB")

    import uuid as _uuid
    match_id_prefix = str(_uuid.uuid4())
    match_uploads = UPLOADS_DIR / "match" / match_id_prefix
    match_uploads.mkdir(parents=True, exist_ok=True)

    ext = ".png" if sim.content_type == "image/png" else ".jpg"
    if sim.filename and sim.filename.lower().endswith(".webp"):
        ext = ".webp"
    sim_path = match_uploads / f"sim{ext}"
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

    sim_report = json.loads(row["sim_report_json"])
    criteria = sim_report.get("criteria", [])

    return TEMPLATES.TemplateResponse(
        request,
        "match_wait.html",
        {"match_id": match_id, "criteria": criteria},
    )


@app.post("/matches/{match_id}/real")
async def upload_match_real(match_id: str, real: UploadFile = File(...)):
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Match inexistent")
        if row["status"] != "awaiting_real":
            raise HTTPException(status_code=409, detail="Match nu așteaptă poză reală")

        content = await real.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Poza reală depășește 5MB")

        sim_path = Path(row["sim_image_path"])
        match_dir = sim_path.parent
        ext = ".png" if real.content_type == "image/png" else ".jpg"
        if real.filename and real.filename.lower().endswith(".webp"):
            ext = ".webp"
        real_path = match_dir / f"real{ext}"
        real_path.write_bytes(content)

        sim_report = json.loads(row["sim_report_json"])
        try:
            compare_report = compare_real(
                sim_report, sim_path, real_path, max_tokens=8192
            )
        except Exception as e:
            repository.fail_match_session(conn, match_id)
            raise HTTPException(status_code=502, detail=f"compare_real a eșuat: {e}")

        repository.update_match_compare_report(
            conn, match_id, real_image_path=str(real_path), compare_report=compare_report,
        )

    return Response(status_code=303, headers={"Location": f"/matches/{match_id}/report"})


@app.get("/matches/{match_id}/image/{kind}")
def match_image(match_id: str, kind: str):
    """Serve a match's stored mockup or real photo so the report can show them
    side by side. Scoped to the two known image slots — never exposes the
    wider uploads directory."""
    if kind not in ("sim", "real"):
        raise HTTPException(status_code=404, detail="Imagine inexistentă")
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Match inexistent")
    path_str = row["sim_image_path"] if kind == "sim" else row["real_image_path"]
    if not path_str or not Path(path_str).is_file():
        raise HTTPException(status_code=404, detail="Imagine indisponibilă")
    return FileResponse(Path(path_str))


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
