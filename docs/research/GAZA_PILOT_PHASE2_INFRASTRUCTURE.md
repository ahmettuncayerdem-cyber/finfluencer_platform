# Phase 2 Research Infrastructure Report
## Gaza War Audience Narrative Reception Study — Production Environment Preparation

**Date:** 2026-08-07
**Prepared by:** Program Director / Principal Research Infrastructure Engineer / Computational
Communication Scientist
**Platform state:** `phase2-development` @ `v1.0.0` (tag pushed), architecture frozen, Persistence
and Authentication out of scope and not discussed below.
**Builds on:** `docs/research/GAZA_PILOT_PHASE1_PLAN.md` (Phase 1) and
`docs/research/GAZA_PILOT_MINIMAL_DESIGN.md` (approved research design — audience narrative
reception, 3 channels, not redesigned here).
**Scope discipline:** planning only. No repository, configuration, or code change is made by
this report. Every "identify what changes" item below is named and explained, not edited.

---

## Executive Summary

Phase 2's job is to make Phase 3 (pilot collection) executable without further planning
mid-stream. This report gets there on every axis except one: the English sentiment model
decision (D-1) is analyzed in full here — two credible, real candidates compared on the actual
criteria the mission specifies — but is presented as a recommendation for the project owner's
sign-off, not a unilateral pick, consistent with this engagement's standing discipline for
research-design-adjacent decisions. Everything else (Google Cloud structure, API strategy, quota
budgets for both pilot and full study, exact repository configuration touch-points, and a
module-by-module validation checklist) is specified concretely enough to execute immediately
once approved.

**Bottom line:** Conditional Go. Infrastructure planning is complete. Execution is blocked on a
short, named list of Mandatory decisions (§7) — most of them require the project owner's own
action (Google account access, real channel-ID lookup, a specific event-anchored date), not
further analysis from this seat.

---

## 1. Current Status

Unchanged from the prior two reports, restated only where it bears directly on Phase 2:

- Software: v1.0.0, frozen, live-verified (T-029, 16/16), CI/lint/type/test all green.
- Research design: approved — audience narrative reception, not channel-narrative claims;
  3 channels (BBC News, Al Jazeera English, TRT World); per-video comment cap; descriptive/
  comparative RQs only.
- **Not yet done, and this report's actual subject:** no Google Cloud project exists for this
  study, no API key has been created, no repository configuration values have been changed
  (correctly — Phase 2 is preparation, not execution), and D-1 (sentiment model) is unresolved.

---

## 2. Google Cloud Plan

### Project structure
**One dedicated Google Cloud project for this study**, separate from any project used for the
existing Turkish finfluencer work. This is the single highest-leverage decision in this section
— every other recommendation below (quota, billing alerts, IAM, key restriction) is easier,
safer, and more legible with one project per study than with a shared project, because quota
exhaustion, cost, and security incidents on one study cannot silently affect the other, and the
Google Cloud Console's own usage/billing dashboards become directly readable as "this study's
footprint" without manual filtering.

**Recommended project name:** `finfluencer-gaza-narrative-2026` (or the project's own internal
study identifier if one is later formalized) — descriptive, dated, and distinguishable from the
existing study's project at a glance in the Console's project switcher. Avoid generic names like
`research-project-1`; a future audit (this platform's own engagement has now produced three of
these) benefits enormously from names that are self-describing without opening the project.

### Billing configuration
YouTube Data API v3 itself carries no per-request monetary cost — confirmed current as of this
report (Google does not charge for standard quota usage). A billing account must still be
attached to the project regardless: Google requires one to enable most APIs at all, and it is a
prerequisite if a quota-extension request (§4) becomes necessary later. **Attach a billing
account with a $0-expected-spend budget alert set at a low threshold (e.g. $1)** — this is a
tripwire, not an expected cost, and exists specifically to catch an accidental enablement of a
different, paid Google Cloud API in this project before it becomes a real bill.

### API restrictions
The API key (§3) should be restricted at creation, not left open:
- **API restriction:** YouTube Data API v3 only — no other API this key could accidentally be
  used against.
- **Application restriction:** IP address restriction to the machine(s) that will actually run
  collection, if collection runs from a small, known set of locations (the operator's own
  machine, per this engagement's established pattern) — tighter than no restriction, and
  simpler to maintain correctly than an HTTP-referrer restriction, which is designed for
  browser-side use this platform's server-side collection script does not have.

### IAM roles
For a single-researcher study with no team members needing Console access, the project owner's
own Google account as **Owner** (or **Editor**, if a slightly narrower default is preferred) is
sufficient — do not create additional IAM principals unless Decision D-7 (multi-person
collection access, from the Phase 1 Decision Register) becomes a real requirement. If it does,
add a named IAM principal per person, scoped to the minimum role needed to view usage and
manage API keys (not project Owner), rather than sharing one Owner account's credentials — this
is standard least-privilege practice and directly avoids the credential-sharing pattern that
already produced one real near-miss this engagement (a key visible in a shared screenshot).

### Quotas
Leave the **default 10,000 units/day** quota in place initially. §4's budget shows both the
pilot and the full minimal-design study fit comfortably within it — requesting a quota increase
before it is needed adds review latency and Console complexity with no present benefit. Revisit
only if real pilot-stage measurement (Phase 3) shows the estimate was wrong in the expensive
direction.

### Security settings
- Two-factor authentication on the Google account that owns this project, if not already
  enforced at the organizational level.
- No service-account JSON keys are needed for this use case — YouTube Data API v3's public,
  read-only endpoints (`search.list`, `playlistItems.list`, `videos.list`,
  `commentThreads.list`) authenticate with a simple API key, not OAuth2/service-account
  credentials; OAuth is only required for actions on a signed-in user's own account (uploads,
  playlist management), which this platform's collection workflow never performs. This
  materially simplifies the security surface versus what a naive "set up GCP for an API" plan
  might assume — there is no consent screen, no scopes, no token-refresh logic to secure here.

### Key rotation
- Rotate the API key immediately if it is ever displayed in a shared screenshot, chat log, or
  committed to git (this engagement's own established practice, reused here — the earlier
  incident from this session, discussed in a prior turn, is the concrete precedent, not a
  hypothetical).
- As a matter of routine hygiene rather than incident response: regenerate the key once at the
  boundary between Phase 3 (pilot) and Phase 5 (full collection), so a pilot-stage key never
  persists into the full study's data-collection window — cheap, and removes one more thing to
  audit later if a question about data provenance ever arises.

### Naming conventions
Apply one consistent naming pattern across every artifact this study produces at the Google
Cloud layer: `gaza-narrative-<component>` (e.g. the API key labeled `gaza-narrative-yt-api-key`
in the Console, not left unlabeled) — small, but it is exactly what makes a future audit of
"which key/project produced this data" fast rather than a forensic exercise, the same category
of problem this engagement's own provenance-column work (V1.0 freeze) solved at the software
layer; this is the same discipline applied one layer up, at the infrastructure layer.

---

## 3. API Strategy (YouTube Data API v3)

### Key creation and restrictions
One API key, created inside the dedicated project above, restricted per §2. No second
"production" key is needed at this study's scale — the pilot/full-study boundary is handled by
rotation (§2), not by running two keys concurrently, which would only fragment quota tracking
without a real benefit at this scale.

### Backup key strategy
Generate a **second, inactive standby key** in the same project at setup time, stored securely
(not in any file this platform reads automatically — a password manager or equivalent, per this
engagement's standing prohibition on handling credentials directly). If the primary key is
compromised or hits an unexpected restriction issue mid-collection, activating the standby is
faster than generating and re-propagating a new one under time pressure. This is a small,
cheap insurance policy, appropriate for a study collecting real data on a real timeline.

### Quota management and monitoring
- Google Cloud Console's own "APIs & Services → Dashboard" for this project gives real-time
  quota consumption per API — check it after every collection run during Phase 3/5, not only
  when something fails.
- Set a Console quota **alert** (not just the billing alert in §2) at 80% of daily quota, so a
  collection run that is consuming more than estimated is caught mid-run, not discovered the
  next day as a `quotaExceeded` failure.

### Logging
This platform's own structured (structlog JSON) per-run logs already capture what was collected
and when (established this engagement's own diagnostic practice, reused directly — no new
logging infrastructure is needed). The one Phase-2-specific addition: log, outside the
platform's own output (e.g. a simple dated note), the Google Cloud Console's reported quota
usage after each real collection run, so a discrepancy between "what the platform's own run log
says it collected" and "what Google's Console says was charged" is visible early, not just at
the end of the study when it's hard to reconstruct.

### Daily usage estimation and cost estimation
No monetary cost (YouTube Data API v3, confirmed §2). Daily *quota* usage estimation is covered
concretely in §5's budget tables — both stay well under the default 10,000-unit/day allocation,
so no daily pacing/throttling logic is needed for this study's scale.

---

## 4. Repository Configuration — What Will Need to Change (identified, not edited)

Every value below is a real, located field in the current repository. None is edited by this
report.

| File / location | Field | Current value | What changes for this study |
|---|---|---|---|
| `config/analysts.yaml` | Channel roster | The existing Turkish finfluencer roster | Replaced with three real entries (BBC News, Al Jazeera English, TRT World) — each needs a **real, verified `channel_id`** (or `handle`, per the file's own documented convention) looked up directly from YouTube, not guessed here; this report does not fabricate channel IDs. |
| `config/settings.yaml` | `study.description` | Describes the Turkish finfluencer study | Replaced with a description of this study (per the file's own convention: free text for the provenance record and replication README) — a real methods-relevant edit, not cosmetic, since this text is captured in every run's `provenance.json`. |
| `config/settings.yaml` | `study.root_seed` | `42` (the existing study's seed) | Recommend a **new, explicitly documented seed** for this study rather than silently inheriting the old one — keeps the two studies' randomness streams (topic-model initialization, any subsampling) provenance-distinct, and is a one-line, low-risk change to call out explicitly rather than assume. |
| `config/settings.yaml` | Observation window (the study's collection date range) | The Turkish study's own window | Set to the real, event-anchored window the Minimal Design (§4 of that document) left open pending reconnaissance — a Mandatory decision (§7, D-Window), not resolvable by this report. |
| `config/settings.yaml` | `sentiment.primary_model.name` / `.revision` | The Turkish-specific model, pinned | Replaced with the English model this report recommends (§6) once approved, pinned to a **real HuggingFace commit SHA** — `core/config.py`'s existing `is_placeholder_revision` check already refuses a literal placeholder, so this must be a real value at config-load time, not deferred. |
| `config/settings.yaml` | `sentiment.pseudo_neutral_band` | Tuned for the current Turkish model's probability outputs | **Requires recalibration**, not a direct carry-over — different models produce differently-calibrated probability outputs; the neutral-band boundaries tuned for one model do not necessarily transfer to another. Flagged here as a real methodological step (part of Phase 4 pilot validation), not assumed safe to leave unchanged. |
| `config/settings.yaml` | `topics.embedding_model` | `paraphrase-multilingual-MiniLM-L12-v2`, already multilingual | **Plausibly unchanged** — still requires the pilot-stage coherence check the Minimal Design already specifies (§6 of that document), not a config edit by default. |
| Environment variables | `YT_API_KEY`, `ANON_SALT` | The existing study's values | Fresh values for this study's dedicated project (§2/§3) and a fresh salt, never reused from the other study's values, set as environment variables only — never committed. |
| Runtime (not a file) | `Project` entity name (`POST /projects`'s `name` field, per `docs/research/QUICKSTART.md`) | N/A | A clear, study-specific name at creation time, following the naming-convention discipline in §2 — an API call argument, not a config-file edit. |

**Not changing:** `CITATION.cff`, `pyproject.toml` — these are software-release metadata, not
per-study configuration, and are correctly out of this table's scope.

---

## 5. English Sentiment Model Review (Decision D-1)

### Requirements, restated from the mission brief
English-language; suited to political/social-media discourse (not, e.g., product reviews or
movie reviews); hosted on HuggingFace with a real, pinnable commit revision (this platform's own
`core/config.py` enforces non-placeholder revisions); stable and actively maintained; carries a
license compatible with academic reuse and redistribution of the model reference (not the
weights) in a replication package; has enough community adoption/citation history in comparable
research to be a defensible, citable choice, not a novel unvetted pick.

### Candidates seriously evaluated

**A. `cardiffnlp/twitter-roberta-base-sentiment-latest`** (Cardiff NLP Group, Cardiff
University)
- **Domain match:** trained on ~124 million tweets (January 2018 – December 2021), fine-tuned
  and evaluated on the TweetEval benchmark — social-media text, the closest available match to
  YouTube comment discourse of the credible candidates reviewed.
- **Output structure:** three classes (negative / neutral / positive) — **matches this
  platform's own existing `sentiment_class` schema exactly**, including the `pseudo_neutral_band`
  mechanism `config/settings.yaml` already has wired for a three-way scheme. This is a real,
  concrete compatibility advantage, not a marginal one.
- **License:** MIT (confirmed on the model family's sibling model cards; verify directly on this
  specific model's card at pin time, per the Decision Register's own verification step).
- **Maintenance/community adoption:** part of the actively maintained TimeLMs project from an
  academic NLP research group with a substantial publication and citation record in exactly this
  space (social-media sentiment/stance research) — the kind of provenance an SSCI reviewer
  recognizes without needing it explained.
- **Reproducibility:** hosted with versioned commits on HuggingFace, directly satisfying this
  platform's own revision-pinning requirement without adaptation.
- **Open question, to close before final pin, not before this report:** confirm the model card's
  own reported benchmark accuracy/F1 directly at pin time — this report does not assert a
  specific number it cannot verify with confidence from search alone, and recommends this be a
  concrete Phase 2 execution step (read the live model card), not skipped.

**B. `siebert/sentiment-roberta-large-english`** (Christian Siebert, Hamburg)
- **Domain match:** fine-tuned and evaluated across 15 diverse text sources (reviews, tweets,
  and others) specifically for cross-domain generalization, rather than tuned to one domain —
  broader but less socially-native than Candidate A's tweet-specific training.
- **Output structure:** **binary only** (positive/negative — no neutral class). This is a real,
  structural mismatch with this platform's existing three-class `sentiment_class` schema and its
  `pseudo_neutral_band` mechanism; adopting it as the *primary* model would mean either dropping
  the neutral category platform-wide (a real methodological choice with consequences for how
  ambivalent/mixed war-discourse comments get coded, not a minor technical detail) or building a
  synthetic neutral band on top of binary probabilities, itself a debatable choice.
- **License:** Apache 2.0.
- **Reported accuracy:** the model's own published benchmark reports ~93.2% average accuracy
  across its 15 evaluation sets, a genuinely strong number, confirmed from the model's own
  documentation.
- **Reproducibility:** also hosted with versioned commits on HuggingFace.

### Candidates considered and set aside, with reasons stated (not silently dropped)
- **`distilbert-base-uncased-finetuned-sst-2-english`:** by far the most-downloaded generic
  sentiment model on HuggingFace, which is exactly why it is worth naming and rejecting
  explicitly rather than ignoring — its training domain (SST-2, movie-review sentences) is a
  poor match for social-media political discourse, and it is binary-only. High popularity is not
  the same claim as domain fit; do not default to it on download-count momentum alone.
- **`nlptown/bert-base-multilingual-uncased-sentiment`:** a 1-5-star product-review scale, wrong
  output structure and wrong domain for this study.
- **VADER (lexicon-based, via NLTK):** still genuinely used in political-communication research
  for its transparency and low computational cost, and is worth naming for completeness — but it
  is not a HuggingFace transformer model with a pinnable commit revision, so it does not fit this
  platform's `ModelReference`/revision-pinning architecture at all without a structural change
  this report is not proposing. Set aside on architectural-fit grounds, not quality grounds.

### Recommendation
**Primary: `cardiffnlp/twitter-roberta-base-sentiment-latest`**, for three converging reasons —
closer domain match (social media, not reviews), structural compatibility with this platform's
existing three-class sentiment schema (avoiding a nontrivial, consequential re-architecture of
the neutral-class handling), and an academic-research maintenance/citation profile appropriate
for an SSCI submission's own Methods-section defensibility.

**Secondary, for the Phase 4 validation step specifically, not as a replacement:**
`siebert/sentiment-roberta-large-english` as an independent convergent-validity check during
gold-sample validation — its different training regime and higher raw benchmark accuracy make it
a genuinely informative cross-check on the primary model's classifications on the same pilot
sample, precisely because it was *not* selected as primary. This uses both candidates' strengths
rather than discarding one outright.

**Not implemented by this report.** Selecting the primary model's exact commit revision and
writing it into `config/settings.yaml` is Phase 2 execution work, contingent on the project
owner's sign-off on this recommendation (Decision Register, D-1).

---

## 6. Quota Budget

Both tables use the same per-unit costs as the Minimal Design document, restated for this
report's self-containment: `commentThreads.list` ≈ 1 unit per ~100-comment page;
`playlistItems.list` (channel video discovery) ≈ 1 unit/page; `videos.list` (batchable metadata)
≈ 1 unit/call for up to 50 IDs.

### Pilot budget (Phase 3 — deliberately smaller than the full minimal design)
| Item | Value |
|---|---|
| Channels | 1 (recommend starting with the channel expected to have the most predictable comment volume, chosen at Phase 3 kickoff, not here) |
| Videos | 2-3 |
| Comment cap/video | 500 |
| Comment ceiling | ~1,000-1,500 |
| `commentThreads.list` estimate | ~10-15 units |
| Discovery/metadata calls | negligible (<5 units) |
| **Total estimated quota** | **well under 25 units — under 0.25% of the daily default** |

### Full-study budget (Phase 5 — the Minimal Design's own 3-channel scope)
| Item | Value |
|---|---|
| Channels | 3 |
| Videos | 18-24 |
| Comment cap/video | 500 |
| Comment ceiling | ~9,000-12,000 |
| `commentThreads.list` estimate | ~90-120 units |
| Discovery/metadata calls | negligible at this scale |
| **Total estimated quota** | **well under 500 units — under 5% of the daily default** |

Both figures leave large margin for re-runs, mistakes, and Phase 4's gold-sample re-checks
without approaching the 10,000-unit default ceiling — no quota-extension request is expected to
be necessary for either phase, pending real pilot-stage confirmation.

---

## 7. Pilot Collection Plan

Smaller than the full minimal design, deliberately — the pilot's job is to convert every
remaining estimate in this report into a measured number before committing to full collection,
not to produce publishable data itself.

- **Channels:** 1, selected at kickoff from the approved 3-channel roster.
- **Videos:** 2-3, from within the (still-to-be-pinned) event-anchored window, or from a nearby
  reconnaissance window if the exact final window isn't pinned yet — the pilot's purpose is
  measurement, not the study's own final data.
- **Comment cap:** 500/video (same cap as the full study, so the pilot's measured
  cost-per-comment figure transfers directly to the full-study estimate without rescaling).
- **Quota estimate:** §6's pilot table.
- **Expected runtime:** collection itself, real network-bound time proportional to comment
  volume (T-015/T-017's own prior measurement, ~400 units'-worth of Turkish-study collection,
  took on the order of minutes to tens of minutes per analyst — treat that as a rough order of
  magnitude, not a guarantee, for this much smaller pilot); topic modeling and sentiment
  inference on ~1,000-1,500 comments should complete quickly relative to T-029's own
  ~17,500-comment run, which itself completed in well-understood, bounded time once the earlier
  real-scale defects this engagement found and fixed were resolved.
- **Expected outputs:** one completed `CollectionRun`, two completed `AnalysisRun`s (topics,
  sentiment, using the new pinned English model), one finalized `Report` with 2 citations, one
  CSV/table export, one PDF export — the exact same artifact shape T-029 itself produced, now
  under real English-language, politically sensitive content for the first time.
- **Validation checks:** §8's module-by-module checklist, run against this pilot's own output.
- **Manual inspection checklist:**
  - Read a sample of `text_clean` values directly — confirm English text is cleaned sensibly (no
    Turkish-specific normalization artifacts leaking through).
  - Read a sample of `topic_label_pooled`/`topic_label_within` values — confirm topics are
    coherent, not degenerate (e.g. not one dominant catch-all topic swallowing most comments,
    which BERTopic can produce on an unfamiliar domain without tuning).
  - Read a sample of `sentiment_class` assignments against the actual comment text directly —
    a fast, informal sanity check ahead of Phase 4's formal gold-sample validation, not a
    replacement for it.
  - Open the PDF export and confirm the bounded-preview note (if the pilot's citation content
    exceeds 20 records) reads correctly and is not mistaken for complete data.
  - Confirm the CSV's new provenance columns (`sentiment_model_name`/`_revision`,
    `topics_model_name`/`_revision`, both `_analysis_run_id` columns) are populated and correct.
- **Success criteria:** all of §8's checklist items pass; the manual inspection above finds no
  gross defect (degenerate topics, obviously wrong sentiment on inspection, broken provenance);
  measured quota cost is within the same order of magnitude as §6's pilot estimate (a large
  deviation either way is itself a finding worth understanding before scaling to Phase 5, not
  something to shrug off).

---

## 8. Research Validation Checklist

Every major V1.0 module, to be checked off against the actual pilot run — phrased as
PASS/FAIL items, deliberately mirroring `t029_live_verification.py`'s own `check()` convention,
so this pilot's validation record reads in the same evidentiary style this platform's own
engineering sign-off already established.

| # | Module | Check |
|---|---|---|
| 1 | Collection | Real, live YouTube collection succeeds against the new (non-Turkish) channel roster; real parquet files written to disk under the run's `base_root`. |
| 2 | Preprocessing | `text_clean` output for English comments is sensible on manual inspection (§7); no crash or silent empty-output on non-Turkish text. |
| 3 | BERTopic | Both `pooled` and `within_analyst` configurations complete and produce a nonzero, non-degenerate topic count; `topic_count` field on the AnalysisRun response is greater than zero. |
| 4 | Sentiment | The newly-pinned English model completes real inference; `AnalysisRun` reaches `completed` status; `sentiment_class` values are populated, not null, across the run. |
| 5 | Master table | CSV/table export succeeds (200); row count matches the collected comment count; every documented column from `docs/research/OUTPUT_CODEBOOK.md` is present. |
| 6 | Citation | A `Report` with 2 citations (topics + sentiment) is built and reaches `citation_count == 2`; finalize succeeds. |
| 7 | CSV export | Real bytes returned, `X-Row-Count` header matches the master table's own row count. |
| 8 | PDF export | Real `%PDF`-prefixed bytes returned; if citation content exceeds the 20-record preview bound, the omission note is present and accurate (manually confirmed, §7). |
| 9 | Logs | Full structured (structlog JSON) log captured for the entire run, from collection through export — preserved per this report's own Logging guidance (§3), not just glanced at. |
| 10 | Provenance | The six provenance columns (§4's config table; added in the V1.0 freeze) are present on the exported CSV and correctly identify the new English model's name and pinned revision, not the old Turkish model's values. |
| 11 | Replication | The run's own `provenance.json` is present, complete (git SHA, config hash, environment versions, seed), and reflects this study's own new `root_seed`/`study.description` values, not the prior study's. |

All 11 must pass before Phase 3 is considered complete and Phase 4 (validation) begins.

---

## 9. Decision Register

### Mandatory (block Phase 2 execution / Phase 3 start)
- **D-1. Sentiment model approval.** This report's recommendation (§5,
  `cardiffnlp/twitter-roberta-base-sentiment-latest` primary) — approve, or direct otherwise.
- **D-GCP. Google Cloud project creation.** Requires the project owner's own Google account
  action — cannot be performed by this seat.
- **D-Key. API key generation**, inside the new project, with the restrictions §2/§3 specify —
  same constraint as D-GCP.
- **D-Channels. Real channel IDs** for BBC News, Al Jazeera English, TRT World — must be looked
  up directly from YouTube, not fabricated by this report.
- **D-Window. The exact event-anchored collection date window** — requires the project owner's
  own current, specific knowledge of the conflict timeline to select a defensible anchor event;
  not invented here.
- **D-4/D-5/D-6** (carried forward from the Phase 1 Decision Register, still open, still
  blocking): ethics/IRB routing, gold-sample reliability threshold, privacy/retention policy
  document.

### Recommended (should be resolved before Phase 3, not strictly blocking)
- **R-1. `study.root_seed` value** for this study (§4) — recommend a fresh, documented value;
  the project owner may reasonably choose to keep `42` instead, but should decide deliberately.
- **R-2. Standby API key generation** (§3) — cheap insurance, not mandatory.
- **R-3. Secondary/convergent-validity model** (SiEBERT, §5) — recommended for Phase 4, not
  required for Phase 3's pilot to proceed.

### Optional (Phase 5+, do not block Phase 2/3)
- **O-1. Quota-extension request** — only if Phase 3's measured quota cost materially exceeds
  §6's estimate.
- **O-2. IAM expansion for multiple collection operators** — only if Decision D-7 (Phase 1
  register) becomes real.

---

## 10. Risk Register (Phase-2-specific additions to the Phase 1 register)

| Risk | Category | Severity | Note |
|---|---|---|---|
| API key exposure via screenshot/chat/commit | Security | High | Concrete precedent already exists this engagement; §2/§3's restriction+rotation+standby-key plan is the direct mitigation. |
| Neutral-class handling changes if D-1 favors a binary-only model in practice | Methodological | Medium | Addressed by recommending the 3-class primary candidate specifically (§5); would need explicit re-litigation if the project owner prefers SiEBERT as primary instead. |
| `pseudo_neutral_band` miscalibration on the new model's probability outputs | Methodological | Medium | Named explicitly in §4's config table as requiring real recalibration, not a silent carry-over. |
| Pilot-stage quota/runtime estimate proves wrong | Technical | Low–Medium | Bounded by design — even a 5-10x overrun on the pilot's ~25-unit estimate stays trivial against the 10,000-unit daily default. |
| Channel ID lookup error (wrong channel collected) | Technical | Low | Mitigated by manual verification against each channel's real YouTube URL at Phase 2 execution time, before the first real collection call. |

---

## 11. Immediate Next Actions

In dependency order, for the next working session:

1. Project owner resolves the Mandatory Decision Register (§9) — model approval, GCP/key
   creation, real channel IDs, event window, ethics/reliability/privacy items.
2. Create the Google Cloud project and API key per §2/§3, using the exact naming conventions
   specified.
3. Look up and verify the three real channel IDs/handles directly on YouTube.
4. Pin the approved sentiment model's exact commit revision by reading its live model card.
5. With all of the above in hand, the next conversation can proceed directly to editing
   `config/analysts.yaml`/`config/settings.yaml` (per §4's table) and running the Phase 3 pilot
   — no further planning should be required at that point.

---

## Final Go / No-Go Recommendation

**Conditional Go.** Every planning artifact this report set out to produce is complete: the
Google Cloud and API strategy is fully specified, the exact repository configuration touch-points
are identified (not edited), a sentiment-model recommendation is made with full comparative
justification, and quota budgets exist for both the pilot and the full study — both comfortably
inside the default quota with no extension expected. The remaining blockers to Phase 3 are the
Mandatory decisions in §9, and every one of them requires either the project owner's own
real-world action (Google account access, a channel-ID lookup, a conflict-timeline judgment) or
an explicit approval this seat should not make unilaterally (the model choice, ethics routing).
This is the correct place for a Go/No-Go line to fall — infrastructure planning does not become
"more ready" by this seat doing more analysis; it becomes ready when the project owner acts on
what is already fully specified above.

---

## Addendum — Smoke Test Sign-off: 19/19 Checks Passed (2026-08-07)

Executed on the operator's own Windows machine (`gaza_pilot_smoke_test.py`, real
`YT_API_KEY`/`ANON_SALT` for the dedicated Gaza Google Cloud project, never handled by this
seat) against the isolated `config/settings.gaza_pilot.yaml`/`config/analysts.gaza_pilot.yaml`
(BBC News only, 2 videos, 50-comment cap):

**GAZA PILOT SMOKE TEST: 19/19 checks passed, 0 failed**

First attempt (checks 1 through 3c) passed cleanly — real collection (68 comments), real
English preprocessing (63 kept), real embeddings, real BERTopic in both `pooled` and
`within_analyst` configurations (topic_count=6, non-degenerate). Check 4a then failed with a
real `OSError`: the newly pinned `cardiffnlp/twitter-roberta-base-sentiment-latest` has no
`model.safetensors` file on the Hub, but `TransformerSentimentClassifier` had
`use_safetensors=True` hardcoded — a deliberate 2026-07-14 fix for a different, previously
real, reproduced Windows crash (WinError 1114 loading `torch/lib/c10.dll`) when loading legacy
pickle checkpoints on this environment.

**Root-caused, not patched blind** (see `BACKLOG.md`-style discipline applied here too):
confirmed via the Hub's own API that no safetensors file or auto-conversion branch exists for
this checkpoint, and that the same is true of the secondary candidate (`siebert/sentiment-
roberta-large-english`) — an older-checkpoint-family pattern, not specific to this one model.
`ModelReference` gained a `use_safetensors: bool = True` field (default preserves the Turkish
study's already-proven-safe behavior exactly; 154/154 targeted tests confirmed this before
handing back), and the Gaza pilot config set it `False` for cardiffnlp specifically, flagged
explicitly as a deliberate, reversible experiment that reintroduces the legacy pickle-loading
path — **not verified from this seat's sandbox** (Linux, and confirmed no network route to
huggingface.co there either), so it had to be tried for real on Windows.

**Second attempt: full pass.** The feared WinError 1114 crash did **not** reproduce for this
model on this machine — `use_safetensors=False` loaded `pytorch_model.bin` cleanly. Real
evidence, not assumption: this specific crash appears tied to something more specific than "any
legacy pickle load on this environment" (possibly the original Turkish checkpoint's own file
layout, or a since-changed condition) — worth keeping in mind if a *future* model swap hits the
same `OSError`, rather than assuming this result generalizes automatically.

All 19 checks passed: project/collection/preprocessing/embeddings/topics (both configurations)
/sentiment/report/citations/finalize/CSV export/provenance columns (confirmed
`sentiment_model_name` = the new English model, not the Turkish one)/PDF export. Manual
inspection sample: all 5 sampled comments classified `negative` — anecdotal only (n=5, and the
sampled comments were about an unrelated weight-loss/Ozempic video topic, not Gaza-specific
content, since this smoke test's observation window was a generic recent window, not the
study's eventual event-anchored one) — not a calibration conclusion; the `pseudo_neutral_band`
recalibration flagged in sec.4's config table remains open, to be assessed for real during
Phase 4 gold-sample validation, not from this smoke test.

**Status: end-to-end pipeline validation complete.** This clears the technical-validation
condition of this report's Go/No-Go (sec. "Final Go / No-Go Recommendation") — remaining
blockers to Phase 3's fuller Pilot Collection Plan are still the Mandatory Decision Register
items in sec.9 (event window, ethics/reliability/privacy, D-1 sign-off now additionally
informed by this real infra finding).

---

## Sources

- [cardiffnlp/twitter-roberta-base-sentiment-latest — Hugging Face](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest)
- [siebert/sentiment-roberta-large-english — Hugging Face](https://huggingface.co/siebert/sentiment-roberta-large-english)
- [siebert/sentiment-roberta-large-english — GitHub (Christian Siebert)](https://github.com/chrsiebert/sentiment-roberta-large-english)
