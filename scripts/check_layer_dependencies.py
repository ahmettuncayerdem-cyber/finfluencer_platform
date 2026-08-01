#!/usr/bin/env python3
"""Enforce IG-001 (IMPLEMENTATION_PLAYBOOK.md, section 0): layer-dependency direction.

IG-001, verbatim: no package in `presentation` or `api` may import from `infrastructure` or
`persistence`; no package in `domain` may import from `infrastructure`, `persistence`, `api`, or
`presentation`.

This script is deliberately stdlib-only (ast + pathlib), not a third-party import-linter
dependency: this repository's poetry.lock cannot currently be regenerated in every environment
this might run in (BACKLOG.md T-003 -- blocked on a Python >=3.11 interpreter), and a two-sentence,
frozen rule does not need a general-purpose contract DSL to express correctly.

Usage:
    python scripts/check_layer_dependencies.py [--root PATH] [--package NAME]

Exits 0 with a summary line if clean, or exits 1 and lists every violation found.

A layer directory that does not exist yet (e.g. before BACKLOG.md T-006 scaffolds the six-layer
skeleton) is treated as clean, not an error -- this check is safe to wire into CI before the
skeleton exists and starts enforcing automatically the moment real files land in it.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

# IG-001's rule set, exactly as written in IMPLEMENTATION_PLAYBOOK.md section 0. Layers with no
# entry here (application, infrastructure, persistence) are not constrained by IG-001 and are
# deliberately not checked -- adding a rule for them would be inventing governance this script
# has no authority to add.
FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    "presentation": frozenset({"infrastructure", "persistence"}),
    "api": frozenset({"infrastructure", "persistence"}),
    "domain": frozenset({"infrastructure", "persistence", "api", "presentation"}),
}


@dataclass(frozen=True)
class Violation:
    file: Path
    line: int
    layer: str
    imported: str

    def __str__(self) -> str:
        return (
            f"{self.file}:{self.line}: layer '{self.layer}' imports forbidden "
            f"'{self.imported}' (IG-001)"
        )


def _imported_module_names(node: ast.AST) -> list[str]:
    """Return every module name a single import statement node references."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module]
    return []


def _violated_layer(imported: str, package: str, forbidden_layers: frozenset[str]) -> str | None:
    """Return the specific forbidden layer name if `imported` reaches into one, else None."""
    prefix = f"{package}."
    if not imported.startswith(prefix):
        return None
    remainder = imported[len(prefix) :]
    layer = remainder.split(".", 1)[0]
    return layer if layer in forbidden_layers else None


def check_layers(
    root: Path,
    package: str = "finfluencer",
    rules: dict[str, frozenset[str]] | None = None,
) -> list[Violation]:
    """Walk `root/<layer>` for every layer named in `rules` and report IG-001 violations."""
    rules = FORBIDDEN_IMPORTS if rules is None else rules
    violations: list[Violation] = []

    for layer, forbidden in rules.items():
        layer_dir = root / layer
        if not layer_dir.is_dir():
            continue
        for py_file in sorted(layer_dir.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                for imported in _imported_module_names(node):
                    hit = _violated_layer(imported, package, forbidden)
                    if hit is not None:
                        violations.append(
                            Violation(
                                file=py_file, line=node.lineno, layer=layer, imported=imported
                            )
                        )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "src" / "finfluencer",
        help="Directory containing the layer packages (default: src/finfluencer).",
    )
    parser.add_argument(
        "--package",
        default="finfluencer",
        help="The import-path prefix the layer packages live under (default: finfluencer).",
    )
    args = parser.parse_args(argv)

    violations = check_layers(args.root, package=args.package)
    if not violations:
        print("IG-001: clean -- no forbidden cross-layer imports found.")
        return 0

    print(f"IG-001: {len(violations)} violation(s) found:", file=sys.stderr)
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
