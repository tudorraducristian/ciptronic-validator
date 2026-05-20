"""Thin CLI wrapper around `image_matcher.engine`.

Invoke from project root with: `python -m image_matcher.run`.
See `image_matcher/README.md` for usage.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .engine import find_pairs, process_pair, render_table

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_INPUT = _PACKAGE_DIR / "input"
_DEFAULT_OUTPUT = _PACKAGE_DIR / "output"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare sim vs real product images.",
        prog="python -m image_matcher.run",
    )
    parser.add_argument("--folder", type=Path, default=_DEFAULT_INPUT,
                        help="Folder containing *_sim.* and *_real.* pairs.")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT,
                        help="Folder where per-pair output is written.")
    parser.add_argument("--model", default="claude-sonnet-4-6",
                        help="Anthropic model id.")
    parser.add_argument("--max-tokens", type=int, default=8192,
                        help="Max output tokens for the compare call. "
                             "Default 8192 covers ~17-20 criteria; raise for "
                             "products with 30+ criteria.")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable INFO logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if not args.folder.exists():
        print(f"input folder not found: {args.folder}", file=sys.stderr)
        return 2

    pairs = find_pairs(args.folder)
    if not pairs:
        print(f"no pairs found in {args.folder}/")
        return 0

    failures = 0
    for i, (base, sim, real) in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] {base}:")
        print(f"  → analyzing {sim.name} ... (via LLM)")
        try:
            report = process_pair(
                base, sim, real, args.output,
                model=args.model, max_tokens=args.max_tokens,
            )
        except Exception as e:  # batch must continue
            print(f"  ✗ failed: {e}", file=sys.stderr)
            failures += 1
            continue
        print(render_table(report))
        print(f"  → {args.output / base / 'compare.json'} saved")

    if failures:
        print(f"\n{failures} pair(s) failed; see logs above.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
