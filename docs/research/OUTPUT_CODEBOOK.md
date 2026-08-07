# Output Codebook

**Audience:** a researcher interpreting this platform's exported data — not a developer working
on its code. Companion to `docs/research/QUICKSTART.md`.

**Status:** written 2026-08-07, Version 1.0 Research Readiness freeze
(`docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md`), from the actual, real construction code
(`src/finfluencer/reporting/master_table.py`, `src/finfluencer/domain/reporting_engine.py`) — not
from memory or assumption.

---

## 1. The master table (CSV/table export)

One row per collected comment. Built by `build_master_table()`
(`src/finfluencer/reporting/master_table.py`), left-joining sentiment and topic results onto
every raw comment — a comment with no sentiment or topic match yet (e.g. an AnalysisRun still in
progress) keeps its row with those fields empty, rather than being dropped.

| Column | Meaning |
|---|---|
| `comment_id` | Stable identifier for one YouTube comment. Join key for everything else in this table. |
| `video_id` | The YouTube video the comment was posted under. |
| `analyst_key` | Which roster entry (`config/analysts.yaml`) the comment's channel belongs to. |
| `posted_date` | Date the comment was posted. **Date only, no time-of-day** — the collection provider truncates to day granularity; do not expect intra-day timing precision for event-study-style questions. |
| `text_clean` | The comment's cleaned raw text. Real text, not a placeholder or an ID — you can read and re-analyze it directly. |
| `n_tokens` | Token count of `text_clean` after cleaning/tokenization. |
| `likes` | Like count on the comment at collection time. |
| `sentiment_class` | The sentiment classifier's predicted class (e.g. positive/neutral/negative — see `config/settings.yaml`'s `sentiment` section for the exact label set currently configured). |
| `sentiment_prob` | The classifier's confidence for `sentiment_class`, as a single scalar (**not** a full probability distribution over all classes — if your analysis needs per-class probabilities or calibration diagnostics, that is not currently exported and would need a code change). |
| `topic_id_pooled`, `topic_label_pooled`, `topic_prob_pooled` | BERTopic result from the **pooled** configuration — one topic model fit across all analysts/channels together, so topic IDs are comparable across your whole roster. |
| `topic_id_within`, `topic_label_within` | BERTopic result from the **within-analyst** configuration — a separate topic model fit per analyst/channel, so topic IDs are only comparable *within* the same `analyst_key`, not across different ones. No `topic_prob_within` column exists (this configuration does not produce one). |
| `sentiment_analysis_run_id`, `sentiment_model_name`, `sentiment_model_revision` | **Provenance, added 2026-08-07.** Which `AnalysisRun` and exactly which model (name + pinned HuggingFace commit revision) produced this row's sentiment fields. Present only if the export was built with `settings` wired in (`MasterTableExportAdapter`'s `settings` argument) — the platform's own live workflow (§4 of the Quickstart) always does this. Reflects the model **currently configured**, not a historical per-run catalog — if you change `config/settings.yaml`'s model after this export, this column still describes what actually produced *this* file. |
| `topics_analysis_run_id`, `topics_model_name`, `topics_model_revision` | Same, for the topic-modeling embedding model. |

**Citing this table in a Methods section:** report the `_model_name`/`_model_revision` values
directly — they are the exact pinned model identity, not just a human-readable name — and the
`_analysis_run_id` values if you need to cross-reference a specific run's own `provenance.json`
(git commit, full config hash, environment package versions, random seed; written once per run
under that run's own output directory).

## 2. Reports, citations, and snapshots

A **Report** (`domain/entities/report.py`) is a container you build up by **citing** one or more
completed `AnalysisRun`s (§4 of the Quickstart does this with one topics run and one sentiment
run). Each citation becomes an `InterpretationRecord` of kind `raw_result_snapshot` — a **frozen
copy** of that AnalysisRun's own output, taken at cite-time. This matters for reproducibility:
if you re-run collection/analysis later and results change, an already-cited Report's snapshots
do **not** silently change with them — a Report always reflects what its data looked like when
you cited it, not the current state of anything.

A Report must be **finalized** (`POST .../reports/{id}/finalize`) before it can be exported.

## 3. The PDF export

The PDF is a **bounded preview**, not a second full copy of your data. Each cited
AnalysisRun's snapshot is embedded up to 20 records; beyond that, the PDF states the total record
count and an explicit note that the remainder is omitted, pointing you to the CSV/table export
(§1 above) for the complete dataset. **Do not use the PDF as your data source for analysis or as
a manuscript table** — it exists for human-readable review of what a Report cites, not as a data
export. The CSV/table export is always the complete dataset; the PDF never is, by design (see
`src/finfluencer/infrastructure/reporting/pdf_renderer_adapter.py`'s own module docstring for the
full rationale — this was a real defect found and fixed during this platform's own MVP sign-off,
documented in `docs/implementation/PROGRAM_DIRECTOR_REPORT.md`).

## 4. `replication.stage`

`config/settings.yaml`'s `replication.stage` (currently `"submission"`, raised from
`"exploratory"` as part of this freeze) controls how strictly the platform enforces
reproducibility discipline as your study progresses:

| Stage | What it enforces |
|---|---|
| `exploratory` | Permissive — for early development/exploration only. |
| `internal` | Pre-registration checks pass; suitable for internal review. |
| `submission` | `ANON_SALT` must meet a minimum length and not be a known placeholder; any replication-package build requires a clean git working tree (so the exact code that produced your outputs is exactly what's committed). **Current default.** |
| `publication` | Everything `submission` requires, plus: every model revision must be a real pinned commit hash, not a placeholder (`core/config.py`'s `is_placeholder_revision` check); a clean git tree is required for *every* CLI report generation, not just replication-package builds. |

Raise this to `publication` before your actual submission-bound manuscript export — this freeze
deliberately stopped at `submission` (see `config/settings.yaml`'s own inline comment for why),
leaving that as your decision for the specific study you're running, not a platform default.
