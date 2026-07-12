Finfluencer Research Platform — Windows Test Fix
=================================================

Generated: 2026-07-11T19:43:36Z

WHAT THIS FIXES
---------------
The 4 tests that were failing on Windows because of two POSIX-only
assumptions in the code:

1. core/budgets.py used `resource.getrusage()` for memory tracking.
   The `resource` module is POSIX-only; on Windows the import fails
   and every MemoryBudget test raises AttributeError.
   Fix: swap to psutil (already installed via prior pip install),
   with graceful fallback to the old POSIX path on Linux/macOS,
   and a "return 0.0 + one-time warning" last-resort branch.

2. tests/unit/test_core/test_checkpoint.py asserted a path substring
   `/ab/abcd1234.npy` which only exists on POSIX. Windows uses \.
   Fix: compare `Path.parts` instead of string substring; now
   platform-independent.

FILES MODIFIED
--------------
    src/finfluencer/core/budgets.py
    tests/unit/test_core/test_checkpoint.py

HOW TO APPLY (Windows PowerShell)
---------------------------------
    cd D:\Projects\finfluencer_platform
    Expand-Archive -Path "$HOME\Downloads\finfluencer_windows_test_fix.zip" `
                   -DestinationPath . -Force

VERIFICATION
------------
    python -m pytest tests\ -q --tb=no --no-cov

    Expected: 236 passed
