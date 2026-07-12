"""Enable python -m finfluencer as a shortcut to the language demo."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    demo_path = Path(__file__).resolve().parents[2] / "examples" / "language_demo.py"
    if not demo_path.exists():
        print(
            f"error: demo script not found at {demo_path}. "
            f"Run the demo directly:\n    python examples/language_demo.py",
            file=sys.stderr,
        )
        return 1
    runpy.run_path(str(demo_path), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
