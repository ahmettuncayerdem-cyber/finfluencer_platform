# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-08-07 — Research Ready

The literal MVP/v1.0 milestone (Roadmap §6): T-029's own acceptance criterion --
"a researcher creates a Project, collects real YouTube data, runs topic *and*
sentiment analysis, views and exports a Report citing raw snapshots -- no AI call
anywhere in the path" -- was met by a real, live, operator-performed run
(`t029_live_verification.py`, 16/16 checks passed; see
`docs/implementation/BACKLOG.md` T-029 and `docs/implementation/PROGRAM_DIRECTOR_REPORT.md`).
All 7 Release blockers (`docs/implementation/RELEASE_BLOCKING_ASSESSMENT.md`) resolved.
Followed by a Version 1.0 Research Readiness freeze pass
(`docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md`): repo-root hygiene, per-row
provenance (`analysis_run_id`/model name+revision) on the exported master table,
`replication.stage` raised to `submission`, and this citation metadata corrected.

This supersedes the entry previously dated 2026-07-26 below, which asserted "Initial
public release" before this criterion had actually been met by a live run --
correctly re-labeled here as implementation-side-only, not a retraction of that
work (nothing in that work was wrong; the "1.0.0"/"Initial public release" framing
was premature).

## [1.0.0-rc] - 2026-07-26 (implementation-side only; human sign-off was still pending)

Entity-centric migration v2 (scope-based analysis layer), the Run Manifest System,
and the Market subsystem (BIST100/TCMB EVDS integration) complete and verified
against fixture/demo data. Real live-data collection and the human, live,
once-performed T-029 sign-off (see above) had not yet occurred as of this date --
`docs/implementation/BACKLOG.md`'s own T-029 entry as of 2026-08-03 explicitly
tracked this as "IMPLEMENTATION-SIDE VERIFICATION COMPLETE; LIVE-DATA / HUMAN
SIGN-OFF HALF OUTSTANDING." See the release history in git log for the full
commit-by-commit record.
