# Known Issues

**Last verified:** 2026-07-27

## Windows Runtime Compatibility

### Investigation summary

[Confirmed] `torch 2.13.0` fails to import on Windows with
`OSError: [WinError 1114]` when `pandas`/`pyarrow` is imported first in
the same process; `torch 2.8.0` does not exhibit this failure under
otherwise identical conditions (same `pandas`, `pyarrow`, `numpy`
versions). This was reproduced in an isolated virtual environment
containing only the four implicated packages, with no repository code
present, and toggled off by changing a single variable — the `torch`
version. [Verified upstream] An independently filed, still-open PyTorch
issue ([pytorch/pytorch#166628](https://github.com/pytorch/pytorch/issues/166628))
describes the same error signature and the same import-order
dependency, triggered by a different package, in an unrelated
codebase. On this evidence, the defect is attributed to `torch`'s own
Windows DLL-loading code, not to this repository.

### Diagnostic environment

| Component | Version |
| --- | --- |
| OS | Windows |
| Python | 3.12.10 |
| `torch` (fails) | 2.13.0 |
| `torch` (works) | 2.8.0 |
| `pandas` | 2.3.3 |
| `pyarrow` | 15.0.2 |
| `numpy` | 1.26.4 |

### Observed symptom

[Confirmed] On Windows, importing `torch` after `pandas` (or after any
module that transitively imports `pandas`/`pyarrow`) within the same
Python process fails with:

```
OSError: [WinError 1114] A dynamic link library (DLL) initialization
routine failed. Error loading "...\torch\lib\c10.dll" or one of its
dependencies.
```

The same process succeeds if `torch` is imported before `pandas`. This
was confirmed with a minimal, repeatable test:

```python
import pandas
import torch   # fails: WinError 1114
```

```python
import torch
import pandas  # succeeds
```

In this repository, the failure surfaces during `pytest` collection:
any test module that imports `pandas` (directly or transitively) before
a module that imports `torch` (e.g. `finfluencer.collect.main`) is
collected causes the entire collection run to abort with the error
above.

### Affected environments

- [Confirmed] **`torch 2.13.0` fails; `torch 2.8.0` does not**, under a
  single-variable bisection: with `pandas==2.3.3`, `pyarrow==15.0.2`,
  and `numpy==1.26.4` held constant, only the `torch` version was
  changed. The exact version at which the regression begins, between
  2.8.0 and 2.13.0, was not individually bisected — see "Root cause"
  below for what is and is not established about the boundary.
- [Confirmed] Reproduces identically in the project's Poetry-managed
  virtual environment **and** in a freshly created, isolated virtual
  environment outside the repository, installing only the four
  packages above at the same pinned versions.
- [Inference] The failing code path
  (`torch/__init__.py::_load_dll_libraries`) is Windows-specific by
  construction — it registers DLL search directories via
  `os.add_dll_directory`, a Windows-only API. The failure is therefore
  not expected on Linux/macOS, but this was **not independently
  tested**; reproduction was not attempted on either platform.
- CUDA involvement was **not independently checked** in this
  repository's environment — the installed `torch` build variant
  (CPU-only vs. CUDA-enabled) was not verified via `torch.version.cuda`
  or an equivalent check. The upstream issue reporter's environment
  (pytorch/pytorch#166628) was confirmed CPU-only, but that is evidence
  about their environment, not this one.

### Root cause

[Confirmed] The failure is attributable to `torch` itself: an isolated,
single-variable experiment (only the `torch` version changed; `pandas`,
`pyarrow`, and `numpy` held fixed) shows `torch 2.13.0` failing and
`torch 2.8.0` succeeding under otherwise identical conditions. This
isolates the regression to somewhere between these two `torch`
releases; it does not by itself pinpoint the exact introducing version.

[Verified upstream] The independently filed, still-open issue
**[pytorch/pytorch#166628](https://github.com/pytorch/pytorch/issues/166628)**
— "[WinError 1114] A dynamic link library (DLL) initialization routine
failed" — reports the identical error signature and the same
import-order dependency (a different package, PyQt6, imported before
`torch`, in an unrelated codebase) and attributes the onset of this
regression specifically to `torch 2.9.0`. This repository's own
bisection did not individually test `2.9.0`–`2.12.x`, so the exact
boundary version is taken from this upstream report rather than
directly proven here.

[Inference] The most likely mechanism, consistent with general Windows
DLL-loading behaviour and the pattern described in the upstream issue,
is that `torch` and other native-extension packages (potentially
including `pyarrow`, which `pandas` imports internally on this
platform) each register their own bundled runtime DLL directories with
the OS at import time, and that a conflict between these registrations
causes `torch`'s own DLL initialization to fail when a different
package's directory is registered first. **The specific conflicting
DLL was not independently verified** — no DLL-level tracing (e.g.
Process Monitor, `dumpbin /dependents`) was performed on this system.
This paragraph describes the most plausible explanation given the
available evidence, not a confirmed mechanism.

### Why this repository is not responsible

- [Confirmed] The failure was reproduced in a virtual environment
  created entirely outside this repository, with none of the
  repository's code, dependency graph, or test infrastructure present
  — only the four implicated packages at their exact pinned versions.
- [Confirmed] Changing exactly one variable (the `torch` version, with
  `pandas`, `pyarrow`, and `numpy` held fixed) toggled the failure on
  and off, isolating the defect to `torch` itself rather than to any
  application-level import order, module structure, or test design.
- [Verified upstream] The identical failure signature and the same
  import-order dependency are independently reported against an
  unrelated codebase in the upstream PyTorch issue tracker.

### Temporary mitigation (applied)

`torch` is pinned in `pyproject.toml` to the last release line not
known to exhibit this failure:

```toml
torch = ">=2.8.0,<2.9.0"
```

This is a dependency version constraint only — no application code,
test code, or import ordering in this repository was changed as part
of this mitigation. `poetry.lock` was regenerated accordingly; only
`torch` and its own transitive dependencies changed (see the release
report for this change for the full before/after comparison).

### Upstream issue reference

- [pytorch/pytorch#166628](https://github.com/pytorch/pytorch/issues/166628) — "[WinError 1114] A dynamic link library (DLL) initialization routine failed"

### Reproduction steps

To reproduce the failure independently of this repository, in an
isolated virtual environment:

```powershell
$testDir = "$env:TEMP\torch_isolation_test"
New-Item -ItemType Directory -Path $testDir -Force | Out-Null
cd $testDir
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install pandas==2.3.3 pyarrow==15.0.2 numpy==1.26.4 torch==2.13.0
python -c "import pandas; import torch"   # expected: OSError [WinError 1114]
python -c "import torch; import pandas"   # expected: succeeds
deactivate
```

Substituting `torch==2.8.0` in the `pip install` line reproduces the
non-failing case used to bisect the regression.

### Criteria for removing the temporary pin

All of the following must hold before widening the `torch` constraint
back to a caret range (e.g. `^2.2`) and regenerating `poetry.lock`:

1. Upstream issue **pytorch/pytorch#166628** (or the issue/PR that
   supersedes it) is closed as fixed in a released, non-nightly
   `torch` version.
2. That release is verified in an isolated virtual environment,
   outside this repository, with the same pinned `pandas`/`pyarrow`/
   `numpy` versions used above: both `import pandas; import torch` and
   `import torch; import pandas` succeed without `WinError 1114`.
3. `poetry run pytest` (full suite, no path restriction) collects and
   runs without the `WinError 1114` collection error.

Once all three are confirmed, update the `torch` constraint, run
`poetry lock`, and update or remove this section.
