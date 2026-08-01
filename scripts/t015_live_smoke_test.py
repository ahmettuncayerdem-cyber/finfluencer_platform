#!/usr/bin/env python3
"""T-015 live smoke test -- BACKLOG.md T-015's own Verification line: "live collection run
against a small real channel."

Not a pytest test (deliberately -- it spends real YouTube Data API quota and requires a real
`YT_API_KEY`; it must never run automatically in CI). Run manually, once, in an environment with
real network egress to `googleapis.com`:

    python scripts/t015_live_smoke_test.py

Requires `YT_API_KEY` set (via `.env` or the environment) and `ANON_SALT` set (or pass
`--anon-salt`). Targets only `config/analysts.yaml`'s pilot analyst (`satiroglu`, a real,
verified channel) -- not the full four-analyst roster -- to keep quota spend minimal, per
T-015's own Migration Risk Checklist.

This script could NOT be run to completion in the sandbox this task was implemented in: that
sandbox's outbound network proxy returns `403` on `CONNECT` to `googleapis.com` (confirmed via
direct `curl`), independent of API key validity or quota state. This is an environment
constraint, not a code defect -- see `docs/implementation/BACKLOG.md`'s T-015 entry for the full
account. Run this script yourself in an environment with real egress to complete the actual
live-network half of T-015's verification.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from finfluencer.core.config import load_settings  # noqa: E402
from finfluencer.core.contracts import AnalystRoster  # noqa: E402
from finfluencer.infrastructure.collection import build_live_collection_engine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--analyst-key",
        default="satiroglu",
        help="Which config/analysts.yaml entry to collect (default: the pilot analyst).",
    )
    parser.add_argument(
        "--base-root",
        default=None,
        help="Where checkpoints/cache/data_raw land (default: a fresh temp directory).",
    )
    args = parser.parse_args()

    cfg = load_settings(
        _REPO_ROOT / "config" / "settings.yaml",
        _REPO_ROOT / "config" / "analysts.yaml",
        validate_secrets=True,  # a real run: refuse to proceed on a missing YT_API_KEY/ANON_SALT
    )

    trimmed = [a for a in cfg.roster.analysts if a.key == args.analyst_key]
    if not trimmed:
        print(f"No analyst with key={args.analyst_key!r} in config/analysts.yaml", file=sys.stderr)
        return 1
    cfg.roster = AnalystRoster(analysts=trimmed)  # type: ignore[assignment]

    base_root = Path(args.base_root) if args.base_root else Path(tempfile.mkdtemp(prefix="t015-live-"))
    print(f"base_root: {base_root}")
    print(f"Collecting for analyst: {args.analyst_key} ({trimmed[0].handle})")

    adapter, quota = build_live_collection_engine(cfg, base_root)
    outcome = adapter.run(run_id="t015-live-smoke")

    print(f"Outcome: {outcome}")
    print(f"Quota remaining: {quota.remaining if quota is not None else 'n/a'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
