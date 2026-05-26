"""Streamlit UI for image_matcher.

Run from project root with: `streamlit run image_matcher/app.py`.
The engine logic (process_pair) is reused untouched.
"""
import re
from pathlib import Path

import streamlit as st

from image_matcher.engine import process_pair

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"
_THEME_CSS_PATH = Path(__file__).parent / "theme.css"

_SUPPORTED_EXTS = ("png", "jpg", "jpeg", "webp")
_BASE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")

st.set_page_config(page_title="Image Match", layout="centered")

# Inject custom theme. Kept in a sibling file so app.py stays focused on logic.
st.markdown(
    f"<style>{_THEME_CSS_PATH.read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)


def _match_icon(is_match: bool) -> str:
    # Geometric Unicode symbols, not emoji. ui-ux-pro-max + CLAUDE.md both
    # forbid emoji-as-icons; ✓ / ✗ render as flat text glyphs.
    return "✓" if is_match else "✗"


@st.cache_data(show_spinner=False)
def _run_pair(base: str, sim_str: str, real_str: str) -> dict:
    """Cached wrapper around process_pair. Streamlit hashes by argument values,
    so the LLM is re-called only when the inputs change."""
    return process_pair(base, Path(sim_str), Path(real_str), OUTPUT_DIR)


st.title("Image Match — Sim vs Real")
st.caption("Compară un mockup 2D cu fotografia produsului real.")

base_raw = st.text_input(
    "Nume pereche:",
    placeholder="ex: Tricou_05 (litere, cifre și _)",
)
base = base_raw.strip()
base_valid = bool(base) and bool(_BASE_NAME_RE.match(base))
if base and not base_valid:
    st.warning("Numele poate conține doar litere, cifre și `_` (fără spații).")

col_sim, col_real = st.columns(2)
with col_sim:
    sim_file = st.file_uploader(
        "Imagine sim (mockup)", type=list(_SUPPORTED_EXTS), key="sim_upload",
    )
with col_real:
    real_file = st.file_uploader(
        "Imagine real", type=list(_SUPPORTED_EXTS), key="real_upload",
    )

if sim_file and real_file:
    prev_sim, prev_real = st.columns(2)
    with prev_sim:
        st.image(sim_file, caption=sim_file.name, use_container_width=True)
    with prev_real:
        st.image(real_file, caption=real_file.name, use_container_width=True)

st.divider()

ready = base_valid and (sim_file is not None) and (real_file is not None)
if st.button(
    "Analizează",
    type="primary",
    use_container_width=True,
    disabled=not ready,
):
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    sim_ext = Path(sim_file.name).suffix.lower()
    real_ext = Path(real_file.name).suffix.lower()
    sim_path = INPUT_DIR / f"{base}_sim{sim_ext}"
    real_path = INPUT_DIR / f"{base}_real{real_ext}"
    sim_path.write_bytes(sim_file.getvalue())
    real_path.write_bytes(real_file.getvalue())

    try:
        with st.spinner("Analizez perechea cu Claude... (poate dura 30-60s)"):
            report = _run_pair(base, str(sim_path), str(real_path))
    except KeyError:
        st.error(
            "Lipsește variabila de mediu ANTHROPIC_API_KEY. "
            "Setează-o înainte să pornești UI-ul."
        )
        st.stop()
    except Exception as e:
        st.error(f"Eroare la analiză: {e}")
        st.stop()

    summary = report["summary"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", summary["total"])
    c2.metric("Matched", summary["matched"])
    c3.metric("Mismatched", summary["mismatched"])

    table_rows = [
        {
            "Criterion": r["criterion"],
            "Sim": r.get("sim_value") or "—",
            "Real": r.get("real_value") or "—",
            "Match": _match_icon(r["match"]),
        }
        for r in report["rows"]
    ]
    st.table(table_rows)
    st.caption(
        f"Rezultatul complet a fost salvat în "
        f"{OUTPUT_DIR / base}/compare.json"
    )
