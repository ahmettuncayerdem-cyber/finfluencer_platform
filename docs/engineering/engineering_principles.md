# Engineering Principles

## Purpose and Scope

This document collects repository-wide engineering principles distilled from
completed Product Engineering and Release Engineering work. It is
intentionally technology-agnostic: entries here should remain applicable to
future work unrelated to the sprint that produced them.

This document does **not** contain:

- Implementation details of any specific sprint or migration.
- Technology-specific instructions (e.g., "call `matplotlib.use("Agg")`
  in `pytest_configure`"). Those belong in the relevant module's docstring,
  code comments, or the sprint's own record.
- Decisions that apply to a single subsystem only. If a lesson cannot be
  restated without naming a specific library, file, or tool, it is not yet
  general enough for this document.

Each principle is classified as one of:

- **Verified within this repository** — directly demonstrated by evidence
  from completed work in this codebase (a fix, a test result, a diff).
- **General engineering principle** — a widely applicable principle that
  this repository's experience is consistent with, but which was not
  independently proven here; it is stated as accepted practice, not as a
  repository-specific finding.

New entries should be added as future sprints conclude, following the same
format: state the principle in technology-agnostic terms, then classify it.

---

## Lessons Learned from PE-03 (Test Isolation / Order-Dependent Failures)

**1. Library modules must not unilaterally configure shared, process-wide
runtime state as a side effect of being imported.**

Rendering backends, locales, global logging configuration, random seeds, and
similar cross-cutting settings affect every consumer of a process, not just
the module that happens to need them. A library module that changes such
state on import imposes that choice on every other part of the system that
imports it, silently and irreversibly for the life of the process.

*Classification: General engineering principle.* (Consistent with this
repository's existing convention of leaving such configuration to the
importer; not independently proven as a universal law, but well supported by
this and prior experience.)

**2. Responsibility for environment-specific configuration belongs to the
execution context that owns the process, not to the code it invokes.**

When a codebase is entered through multiple paths (a CLI, a test suite, a
notebook, a GUI), each entry point is best positioned to decide the
environment-specific concerns relevant to it. Shared library code that
remains agnostic to which entry point invoked it stays reusable across all of
them; library code that assumes a particular entry point's environment
becomes coupled to it.

*Classification: Verified within this repository.* Demonstrated by two
independent modules in this codebase deliberately avoiding this
configuration at import time, and by a test-only fix at the harness level
resolving the resulting failure without any change to those modules.

**3. The test harness's initialization sequence is the correct architectural
boundary for environment-specific test configuration — and the earliest
applicable hook should be preferred over per-test fixtures when a concern
must be fixed before test subjects are even imported.**

Per-test fixtures, including autouse ones, run after test collection. If the
concern in question must be settled before any test module is imported (as
opposed to before each test runs), it belongs in a collection-time or
session-initialization hook, not in a fixture.

*Classification: Verified within this repository.* Demonstrated directly:
an autouse fixture would have run too late to affect the failure in
question; a collection-time hook, placed in the test harness rather than in
any module under test, resolved it completely.

**4. Failures that appear only under certain execution orders should first
be investigated as lifecycle or initialization-sequencing problems, not as
defects in the code being exercised.**

Order-dependent failures are a symptom of *when* something is initialized
relative to *when* it is first used, not necessarily of *what* that
something does. Diagnosing the lifecycle stage at which a shared resource is
configured — and comparing it to the lifecycle stage at which the failure is
observed — should precede any change to the code under test.

*Classification: General engineering principle*, illustrated by this
repository's own experience: the root cause was fully resolved by correcting
an initialization boundary, with zero changes to the modules where the
failure was observed.

**5. The scope of a fix should match the diagnosed architectural boundary,
not the visible surface area of the symptom.**

A failure that manifests across many test cases does not imply that many
files need to change. When the root cause is correctly localized to a single
boundary, the fix should be confined to that boundary even if the symptom
was widespread.

*Classification: Verified within this repository.* A failure spanning
multiple test cases and, in earlier runs, multiple unrelated test files, was
resolved with a single-file, single-function change.
