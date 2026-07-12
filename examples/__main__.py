"""
Enable ``python -m finfluencer`` as an entry point to the first runnable
feature demo (the TurkishLanguageProvider preprocessing pipeline).

For the CLI over the data-collection pipeline (requires YouTube API key),
use:
    python -m finfluencer.collect.main run
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    # The demo lives outside the installed package so we import it by path.
    # This keeps __main__.py free of demo-specific imports and lets the
    # demo evolve without touching the package.
    _repo_root = Path(__file__).resolve().parents[2]
    demo_path = _repo_root / "examples" / "language_demo.py"

    if not demo_path.exists():
        print(
            f"error: demo script not found at {demo_path}. "
            f"Run the demo directly:\n    python examples/language_demo.py",
            file=sys.stderr,
        )
        return 1

    # Execute the demo script in a way that lets its `if __name__ == '__main__'`
    # block run, without spawning a subprocess.
    import runpy
    runpy.run_path(str(demo_path), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
