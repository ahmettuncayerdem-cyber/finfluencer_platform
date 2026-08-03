# ADR 0003 — PDF Rendering Library: reportlab

**Date:** 2026-08-03
**Status:** Accepted — 2026-08-03 (BACKLOG.md T-027; Claude drafted, human-approved by proceeding
with T-027 under the operator's own Task Authorization). No prior ADR names a PDF rendering
library — `docs/adr/0001-technology-stack.md` does not mention one, and no such library was
previously declared in `pyproject.toml`.
**Drafted by:** Claude, grounded in direct inspection of `pyproject.toml`'s existing dependency
set, `PRODUCT_ARCHITECTURE.md` §8.4/§10.1, and `IMPLEMENTATION_ROADMAP.md` §3's "export
rendering is genuinely new work" classification.

## Context

`PRODUCT_ARCHITECTURE.md` §8.4 requires the Reporting & Publication Engine to render a `Report`
to "Rendered PDF (v1) / Word (v1.x) documents" (line 299). `Export`/`ExportFormat.PDF` (T-024)
already model this at the Domain layer, unused until this task. No PDF-capable rendering library
was declared anywhere in `pyproject.toml`, and `docs/adr/0001-technology-stack.md` does not name
one — this is a genuine, undecided technology choice, not a previously-settled one this task is
merely implementing.

`pyproject.toml` does already declare `jinja2 = "^3.1"` under a section explicitly commented
"Templating (report / Publication Engine)" — but it produces HTML/text, not PDF bytes, and is
not imported anywhere in the codebase as of this task.

## Decision

Add `reportlab` (`^4.0`, confirmed importable as `4.5.1` in this sandbox) as a new runtime
dependency, used directly via its Platypus API (`SimpleDocTemplate`, `Paragraph`, flowables) to
render `Report` content to PDF — no HTML/Jinja2 intermediate step in this task's scope.

## Reasoning

**Why a rendering library is needed now, not deferred further.** T-027 is BACKLOG.md's own
explicitly-flagged highest-uncertainty task, named because "no existing tested code" backs it —
some new dependency was always the expected outcome of accepting this task; the question was only
which one.

**Why `reportlab` over the alternatives investigated:**
- `weasyprint` — requires system-level Cairo/Pango libraries outside Python's own dependency
  management; a heavier, less portable footprint for a single-developer, sandboxed-environment
  project than this task's minimal scope justifies.
- `pdfkit` — wraps the external `wkhtmltopdf` binary via subprocess; a binary dependency this
  project's `pyproject.toml`-only reproducibility discipline (see its own header comment) cannot
  express or pin the way it pins Python packages.
- `xhtml2pdf` — not importable in this sandbox at all; would require its own separate
  installation verification with no offsetting advantage over `reportlab` for this task's scope.
- `reportlab` — pure-Python-distributable (no external system binary or C-library dependency
  beyond what pip already resolves), already confirmed importable in this sandbox before this
  decision was made, and sufficient for T-027's deliberately minimal "render the citation and
  data content" scope (BACKLOG.md's own Internal Review language for this task).

**Why not adopt `jinja2` in the same task.** `jinja2` renders text/HTML, not PDF bytes; combining
it with `reportlab` would require deciding an HTML-to-PDF path this task does not need yet (no
publication-quality layout is in scope). Introducing it now, with no immediate template-variety
need, would be exactly the "speculative abstraction" pattern this project's operating discipline
has repeatedly instructed against. Left declared-but-unused, as it already was; a fast-follow
layout-polish task is the natural point to introduce it.

**Why `pypdf` is dev-only, not a runtime dependency.** It is used exclusively by this task's own
automated content-match test (reading rendered PDF text back out to assert citation content is
present) — no production code path imports it.

## Consequences

- `pyproject.toml` gains `reportlab` (runtime) and `pypdf` (dev group). `poetry.lock`
  regeneration is environment-blocked in this sandbox, the same root cause already recorded for
  T-002/T-003 — both packages are already importable here directly (verified before this
  decision), so tests run and pass, but a fresh `poetry install --sync` has not been exercised
  this session.
- A future Word (`ExportFormat.WORD`, v1.x) rendering task will need its own library decision —
  `reportlab` does not produce `.docx` output; this ADR does not resolve that choice, only PDF.
- A future layout-polish fast-follow may introduce `jinja2`-based templating alongside
  `reportlab`'s Platypus rendering, or replace part of this rendering path entirely — not
  foreclosed by this decision, since `reportlab`'s flowable content is constructed from plain
  strings this task's orchestrator already assembles, not from a `reportlab`-specific data model
  a future change would need to unwind.
