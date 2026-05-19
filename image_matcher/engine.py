"""Image match engine: pure functions + a single I/O wrapper.

Pure functions (find_pairs, encode_image, build_*_messages, parse_*_response,
render_table) are unit-tested in `tests/test_engine.py`. The single I/O
function (`call_llm`) and the orchestrators (analyze_sim, compare_real,
process_pair) are verified manually with the checklist in README.md.
"""
