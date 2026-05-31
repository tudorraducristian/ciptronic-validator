import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from schemas import loader


BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./ciptronic.db")
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(BASE_DIR.parent / "uploads")))
SCHEMA_PATH = BASE_DIR.parent / "db" / "schema.sql"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


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
