# Program Director Report — Phase 1: Research Preparation Plan
## Validation Study: "Competing Strategic Narratives of the Gaza War on YouTube"

**Date:** 2026-08-07
**Prepared by:** Program Director / Lead Software Architect / Research Infrastructure Lead
**Platform state referenced:** `phase2-development` @ `v1.0.0` (commit `1457c01`), Version 1.0
Research Readiness freeze complete (`docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md`)
**Status:** Planning artifact. No repository, configuration, or code changes are proposed or
performed by this report. Architecture remains frozen per standing instruction — Persistence
Layer and Authentication are not revisited anywhere below.

---

## Executive Summary

Version 1.0 is real, evidenced, and adequate as an *engine*: the full Collection → Preprocess →
Topics → Sentiment → Report → Export loop is proven against real data (T-029, 16/16 checks), the
freeze pass closed the researcher-documentation and provenance-traceability gaps this platform
previously had, and the test suite is clean. That is not in question, and this report does not
re-litigate it.

What this report is about is different: whether the *specific* study proposed — competing
strategic narratives of the Gaza War, in English, across nine international news channels — is
ready to begin collecting data. It is not, yet, and should not be treated as a small variation on
the platform's existing Turkish finfluencer study. Three things distinguish it sharply enough to
warrant a real Phase 1 rather than a config edit and a re-run: the sentiment model is
language-mismatched for this content and must be replaced (a decision, not yet made); the topic
is politically sensitive in a way the original study never was, which changes the ethics,
security, and reputational risk profile materially; and the platform's own quota/scale
assumptions were calibrated against a different kind of channel (a handful of individual
finfluencers) than what this study proposes (major international news broadcasters, whose comment
volume and velocity on a war topic are unknown quantities to this platform today, not just
untested — genuinely unmeasured).

None of this blocks starting Phase 1. It blocks starting *collection*. The recommendation below is
a **Go for Phase 1 (planning), Conditional/No-Go for Phase 3 (pilot collection) until the Required
Decisions in the Decision Register are made** — a distinction this report treats as load-bearing
throughout, not a formality.

---

## 1. Repository Readiness Verification

**Is Version 1.0 Freeze sufficient for this mission?** Sufficient as an engineering foundation;
not sufficient, by itself, as research-project readiness — the two are different claims, and
conflating them is exactly the failure mode this section exists to prevent.

Confirmed sufficient:
- CI, Ruff, MyPy, unit tests, cross-platform testing: green, per this engagement's own
  established record (Release Blocker #7 and the surrounding delta history,
  `docs/implementation/PROGRAM_DIRECTOR_REPORT.md`).
- The full product-visible workflow (Project → Collection → Topics → Sentiment → Report →
  Export) is live-verified against real YouTube data, not just fixtures (T-029).
- Provenance is now traceable in the exported artifact itself (`analysis_run_id`/model
  name+revision columns), not only in a side-channel `provenance.json`.
- Researcher-facing documentation exists (`docs/research/QUICKSTART.md`,
  `docs/research/OUTPUT_CODEBOOK.md`) and was written directly from the platform's own proven
  code path, not aspirationally.
- `replication.stage` enforces real discipline (`submission` tier) rather than sitting at the
  permissive default past MVP sign-off.

**Not blockers for Phase 1 planning, but real, load-bearing facts for Phase 2 onward** — listed
here once, referenced rather than repeated in every later section:
- **No live-mode server entry point.** `create_app(use_live_collection=True)` has only ever been
  exercised via `TestClient`, in-process. Fully functional; not a listening HTTP service. Any
  automation this study needs (scheduled re-collection, a dashboard, multiple people driving
  runs) has to be built on top of a Python script calling `TestClient`, not on `curl`/Postman
  against a running server, unless that gap is closed first — which is new infrastructure work,
  out of this report's no-code scope, and not assumed done below.
- **No Persistence Layer** (unchanged, per standing instruction). Every artifact from every run
  lives in an OS temp directory until manually copied out. For a study collecting from nine
  major channels over a real time window, this is an operational discipline problem, not a
  paperwork one — see §2's Backup Strategy.
- **Single dev-user, no real Identity/Auth.** Fine for one researcher; a real constraint the
  moment more than one person needs to run collection independently (see Decision Register,
  D-7).
- **Sentiment model is Turkish-specific** (`config/settings.yaml`'s `sentiment.primary_model`,
  currently `savasy/bert-base-turkish-sentiment-cased`). This is not a nuance — it is a hard
  blocker for English-language content specifically, confirmed already in the Quickstart's own
  warning, now the central fact this whole plan is organized around.
- **One global config file, not per-study.** `config/settings.yaml`/`config/analysts.yaml` are
  singular, platform-wide files. Running the existing Turkish finfluencer study and this new
  English-language Gaza study are not simultaneously representable in the current config
  layout — switching between them today means manually swapping file contents, which is an
  operational/process decision (Decision Register D-3), not something this report resolves by
  itself.

**Blockers, specifically for this study, identified by this report:** none of the above are
*platform* defects — the platform did exactly what a v1.0 freeze should do: prove the engine
works and document its real, current boundaries honestly. The blockers belong to §7 (Decision
Register) precisely because they are the project owner's calls to make, not engineering defects
to fix silently.

---

## 2. Research Preparation Roadmap

Every step required before a single comment is collected, organized by category.

### Google Cloud / YouTube API setup
- A **dedicated Google Cloud project** for this study, separate from any project already used for
  the Turkish finfluencer study — keeps quota, billing alerts, and API key rotation independent
  per study, and avoids one study's quota exhaustion silently blocking the other.
- YouTube Data API v3 enabled on that project; a fresh API key generated and restricted (HTTP
  referrer / IP restriction where practical, API restriction to YouTube Data API v3 only).
- Read Google's current API Services Terms of Service and Developer Policies before collection
  begins, not after — specifically the requirements to publish a privacy policy describing what
  is collected/stored/why, to avoid indefinite storage of user data, to provide a data-deletion
  process, and to maintain "reasonable and appropriate" security controls over collected data.
  These are direct obligations on this project, not background reading (sources below).

### Quota planning
- Default quota is **10,000 units/day per project** (Google's standard allocation, confirmed
  current as of this report). `search.list` costs 100 units/call; `commentThreads.list` costs 1
  unit per **page** (not per comment) — a heavily-commented video can require many pages.
- This platform's own prior live-network validation (T-015/T-017, `docs/implementation/
  PROGRAM_DIRECTOR_REPORT.md`) measured roughly ~400 units for one Turkish finfluencer analyst's
  full collection pipeline. **That number does not transfer to this study.** Major international
  news channels covering a high-salience war topic plausibly draw far higher comment volume and
  velocity per video than a finfluencer channel — this is a real unknown, not an assumption
  either way, and needs direct reconnaissance (see Pilot Strategy, §3) before a full-collection
  quota budget can be trusted.
- If reconnaissance shows the default 10,000/day quota is insufficient for the intended scope,
  Google's formal quota-extension request process takes real calendar time — start it early,
  not when already blocked.

### Project naming, credentials, API security
- A distinct project/tenant name in this platform's own terms (e.g. via the `Project` entity
  the Quickstart workflow creates) that is unambiguous in exports/logs — not reused from or
  confusable with the existing Turkish finfluencer study's naming.
- `YT_API_KEY` and `ANON_SALT` for this study, generated fresh, never reused from the existing
  study's values, held only as environment variables (never committed — this platform's own
  standing rule, unchanged).
- A credential-rotation plan: who holds the real key, how it is rotated if exposed (this
  engagement has already had one real near-miss this session with a key visible in a shared
  screenshot — the process for that scenario should be decided now, not improvised again).

### Directory layout, artifact storage, versioning
- Because there is no Persistence Layer, decide **now**, not after the first run, where
  `base_root`'s contents get copied after every collection/analysis run, using a naming
  convention that embeds the study name, run date, and `collection_run_id` — this platform will
  not do this for you.
- Decide whether this study's `config/settings.yaml`/`config/analysts.yaml` overrides are kept
  as a separate, clearly-named copy (e.g. `config/settings.gaza-pilot.yaml`) with the exact
  procedure for pointing `create_app()` at it, given the global-config constraint noted in §1.
- A version-tagging convention for this study's own data snapshots (distinct from the software's
  own `v1.0.0` git tag) — e.g. `gaza-pilot-pilot-collection-2026-08-XX` — so a specific dataset
  version is unambiguously citable later, independent of which software commit produced it (the
  new provenance columns already capture the latter).

### Logging and backup strategy
- Preserve the full structured (structlog JSON) log output of every run, not just the final
  summary — this engagement's own experience this session (two real defects and one
  environment-correlated anomaly, all diagnosed from exactly this log stream) is the concrete
  argument for why.
- A backup cadence stated in writing before collection starts (e.g. "copy `base_root` contents to
  <permanent location> immediately after every run, then again to an off-machine backup at least
  daily during active collection") — not "when convenient."

---

## 3. Research Design Preparation

Preparation only — this report does not draft the study itself.

- **Research scope.** The stated topic ("competing strategic narratives") already implies a
  comparative design across channels/outlets, which is a meaningfully different analytical
  target than the original study's single-community sentiment/topic description. Confirm with
  the project owner whether the comparative framing (narrative differences *between* channels) or
  a pooled framing (aggregate discourse *about* the war, channel as a covariate) is the intended
  primary research question — the two imply different sampling and analysis choices downstream.
- **Channel selection strategy.** Nine channels are named (BBC News, TRT World, Al Jazeera
  English, CNN, Sky News, France24, DW News, NBC News, WION). Before treating this as final:
  document the selection *rationale* (e.g. geographic/institutional diversity of state or
  state-adjacent funding, audience reach, English-language availability) as a citable
  methodological choice, not an implicit given — reviewers of a comparative-narrative study will
  ask why these nine and not others.
- **Sampling strategy.** Whole-channel collection (every video in a time window) vs. a defined
  video-selection rule (e.g. top-N by views, or every video matching a keyword filter) has direct
  quota and dataset-size consequences (§2) and must be decided before reconnaissance, not
  emergent from whatever quota happens to allow.
- **Time window.** Not specified by the mission brief — needs an explicit start/end date tied to
  the actual research question (e.g. a specific escalation period vs. a longer comparative
  window), independent of platform capability.
- **Expected dataset size.** Cannot be responsibly estimated yet — depends on the still-unmeasured
  comment-volume-per-video reality for these specific channels (§2's quota planning gap) and on
  the sampling strategy above. Treat any number offered before pilot reconnaissance as a guess,
  not a plan input.
- **Pilot strategy.** A small, explicit pilot (e.g. one channel, one week, a handful of videos)
  before committing to full-scale collection — not just for engineering validation (Phase 3/4
  below) but specifically to get a real comment-volume measurement to replace the unknown in §2's
  quota planning, and to produce the first real English-language text sample for model validation
  (§4).
- **Validation strategy.** This platform's own `research_archive/` (git-ignored, not shipped, but
  present locally from the prior study) already demonstrates the precedent this study should
  repeat: a human-coded gold sample with inter-rater reliability reporting, run once against a
  small sample before trusting any sentiment number at scale. This is not optional for a topic
  where "positive"/"negative" sentiment framing is contested and consequential in a way it
  rarely is for financial commentary.

---

## 4. Model Readiness Assessment

Requirements only, per instruction — no specific model is recommended here.

| Component | Status | Requirement |
|---|---|---|
| **Sentiment classifier** (`sentiment.primary_model`) | **Must be replaced.** Currently Turkish-specific; will not produce valid output on English text. | Must support English. Must be a real, pinned HuggingFace commit revision (`core/config.py`'s `is_placeholder_revision` check already enforces this at config-load time — no code change needed, just a real value, not a placeholder). Should have some documented provenance/validation history appropriate to news/political discourse, not only general-purpose sentiment benchmarks — general social-media sentiment models are not automatically valid for war-narrative-specific framing (§5, ME-1). |
| **Topic-modeling embedding model** (`topics.embedding_model`) | **Can plausibly remain** — `paraphrase-multilingual-MiniLM-L12-v2` is already multilingual and includes English. | Requires validation, not just language-coverage assumption: confirm topic coherence on a pilot sample of this study's actual text (political/conflict discourse can produce different embedding-space behavior than financial commentary even in a model's "supported" language). |
| **Text preprocessing / cleaning pipeline** | Requires validation. | English text has different cleaning needs (contractions, differing punctuation/emoji conventions, no Turkish-specific normalization rules) than the pipeline was tuned against. Needs a pilot-sample check, not an assumption of drop-in compatibility. |
| **BERTopic pipeline parameters** (UMAP/HDBSCAN settings, `config/settings.yaml`'s `topics` section) | Requires validation. | Tuned against Turkish finfluencer discourse's typical comment length/structure; whether the same hyperparameters produce coherent topics on this study's content is an empirical question for the pilot, not an assumption. |
| **Any target-of-affect / auxiliary sentiment heads** (`sentiment.target_of_affect`, currently disabled per this engagement's own earlier config work) | Requires an explicit decision. | If this study's research question needs target-specific sentiment (e.g. sentiment toward specific actors/entities named in comments, plausible for a narrative-framing study), enabling and validating this component is new scope — decide whether it's in or out before Phase 2, not discovered mid-analysis. |

---

## 5. Risk Register

| ID | Risk | Category | Severity | Notes |
|---|---|---|---|---|
| T-1 | Comment volume/velocity on major news channels is unmeasured; quota/storage/compute assumptions calibrated on a different kind of channel | Technical | High | Directly addressed by the Pilot Strategy (§3); do not scope full collection before this is measured. |
| T-2 | No live-mode server entry point; all automation must go through a `TestClient`-driven script | Technical | Medium | Workable for a single-researcher pilot; a real constraint if multiple people need independent collection runs. |
| T-3 | No Persistence Layer; data loss risk between runs if manual backup discipline (§2) lapses | Technical | Medium–High | Entirely a process risk now, not a platform defect — the platform's limitation is already fully documented (`docs/research/QUICKSTART.md`). |
| T-4 | Two previously-unexplained live-run anomalies this engagement (correlated with, not proven caused by, laptop battery state) could recur under a larger, longer collection run | Technical | Low–Medium | Not reproduced under stable power; monitor, don't ignore, during Phase 3. |
| ME-1 | Construct validity: a sentiment/topic pipeline's technical language-compatibility is not the same claim as its validity for war-narrative discourse specifically | Methodological | **High** | The single most important risk in this table. Addressed by the Validation Strategy (§3) and Model Readiness (§4) — not solvable by model selection alone; requires the human-coded gold-sample step every time, not once. |
| ME-2 | Comparative-narrative research question (§3) requires a channel-selection rationale defensible to reviewers; ad hoc channel choice invites a validity challenge | Methodological | Medium | Resolve as part of Research Design, before Phase 3. |
| ME-3 | Topic coherence/BERTopic hyperparameters unvalidated on this content type | Methodological | Medium | Pilot-stage check (§4). |
| ET-1 | Human-subjects-adjacent data: even anonymized, YouTube commenters did not consent to being research subjects on a politically charged topic; standard "publicly available data" reasoning is necessary but not sufficient for a topic this sensitive | Ethical | **High** | AoIR's *Internet Research: Ethical Guidelines 3.0* is the current, standard reference framework for exactly this judgment call (source below) — route this through the project's institutional ethics/IRB process explicitly, not assumed exempt because data is public. |
| ET-2 | Risk of the research team, or the platform itself, becoming a target of complaint, harassment, or bad-faith scrutiny given the topic's real-world sensitivity | Ethical / Security | Medium | A legitimate operational-security consideration, not alarmism — decide data-handling and public-communication practices (e.g. what gets shared publicly vs. kept internal) before, not during, a controversy. |
| L-1 | YouTube API Services Terms of Service compliance: published privacy policy, no indefinite data retention, user data-deletion process, "reasonable and appropriate" security controls are direct developer obligations, not optional | Legal | **High** | Concrete, actionable, and currently unaddressed by this platform for any study — needs a real privacy-policy document and retention/deletion process before this study's data collection, not just before publication. |
| L-2 | Copyright/reuse rights over collected comment text, especially if quoting individual comments in a publication | Legal | Medium | Standard academic fair-use practice for research quotation likely applies but should be confirmed against the target journal's own policy and the institution's legal guidance, not assumed. |
| Q-1 | Default 10,000 units/day quota may be insufficient once real comment volume is measured (§2); Google's quota-extension process takes real time | API quota | Medium–High | Start the extension request early if the pilot indicates it's needed — do not wait until blocked. |
| LG-1 | English-language sentiment/topic model selection and validation is the single hardest technical dependency in this plan (§4) | Language | High | No component of this plan proceeds past the pilot without this resolved. |
| PS-1 | Political sensitivity of the topic itself: any published finding about "competing strategic narratives" of an active or recent conflict will attract scrutiny from multiple directions regardless of how neutrally it is conducted | Political sensitivity | High | Not a reason not to do the research — a reason to over-invest in methodological transparency (full provenance, published codebook, pre-registered comparative design) specifically because the topic invites challenge. This platform's own provenance/citation infrastructure (§1) is a genuine asset here, not incidental. |
| R-1 | Reproducibility: `replication.stage` currently `submission`, not `publication` — model-revision pinning is enforced, but the clean-git-tree gate for CLI report generation specifically is not yet active | Reproducibility | Medium | Raise to `publication` before the actual submission-bound manuscript export, per `docs/research/OUTPUT_CODEBOOK.md`'s own existing guidance — already documented, not a new finding. |
| PB-1 | Publication risk: a comparative-narrative finding about a live or recent conflict is more likely to draw pre-publication or post-publication challenge than the original finfluencer study was | Publication | Medium–High | Mitigated, not eliminated, by ME-1/R-1's methodological rigor requirements above. |

---

## 6. Execution Roadmap

Each phase's exit criteria are the gate into the next — a phase is not "mostly done," it either
meets its exit criteria or it doesn't.

### Phase 1 — Planning *(this report)*
**Goal:** produce a complete, evidence-grounded preparation plan without touching the repository.
**Deliverables:** this report; the Decision Register (§7) routed to the project owner.
**Exit criteria:** project owner has reviewed and resolved every item in the Decision Register's
"Required decisions" list.

### Phase 2 — Infrastructure setup
**Goal:** stand up everything §2 requires, without yet collecting study data.
**Deliverables:** dedicated Google Cloud project + API key; study-specific config
override file (naming/location per D-3); directory layout and backup process in place and
tested with dummy data; privacy policy and data-retention/deletion process drafted (L-1);
sentiment model selected and pinned to a real revision (§4, contingent on D-1).
**Exit criteria:** a full dry run of the Quickstart workflow (§1 of `docs/research/QUICKSTART.md`)
succeeds against the new config, with a single test video, producing a real (even if trivial)
CSV/PDF export with the new model's provenance columns populated correctly.

### Phase 3 — Pilot collection
**Goal:** collect a small, bounded real sample (§3's Pilot Strategy) to replace every "unknown"
this report has flagged with a measured number.
**Deliverables:** real comment-volume/quota measurements per channel; a real English-language
text sample for model validation; first real topic-model output for coherence review.
**Exit criteria:** quota cost per channel is known within a usable margin of error; no
platform-stability anomaly reproduces under this pilot's real load (T-4 monitored); pilot data
volume is enough to proceed to gold-sample construction in Phase 4.

### Phase 4 — Pilot validation
**Goal:** the methodological validation step ME-1 requires, done once before scaling, not after.
**Deliverables:** human-coded gold sample of the pilot's sentiment output with inter-rater
reliability statistic; topic-coherence review by the research team; a documented go/no-go
judgment on whether the selected sentiment model (Phase 2) is adequate, or needs reselection.
**Exit criteria:** inter-rater reliability meets the threshold the project owner sets (a
Required Decision, D-5) before Phase 5 begins. If it does not, return to Phase 2's model
selection — do not proceed to full collection on an unvalidated model.

### Phase 5 — Full collection
**Goal:** execute the study's real data collection at the scope §3 defines.
**Deliverables:** the full raw dataset, backed up per §2's discipline, for every collection run
as it completes (not batched at the end).
**Exit criteria:** collection completes within quota/time budget, or the quota-extension request
(Q-1) was filed with enough lead time that it didn't block this phase.

### Phase 6 — Analysis
**Goal:** run topics + sentiment analysis over the full dataset; build the Report/citations
per the existing, proven workflow.
**Deliverables:** finalized Report(s), CSV/table export(s) with full provenance, manuscript
figures/tables.
**Exit criteria:** exported artifacts pass the same kind of manual completeness/sanity check this
engagement's own T-029 sign-off used (spot-check real rows, confirm provenance columns, confirm
PDF preview note is present and accurate, not mistaken for complete data).

### Phase 7 — Publication
**Goal:** produce the SSCI-level manuscript and its replication package.
**Deliverables:** manuscript; replication package (`replication.stage` raised to `publication`
first, per R-1); archived artifacts per §2's versioning convention.
**Exit criteria:** journal submission, with every reproducibility claim in the Methods section
directly traceable to a specific `analysis_run_id`/model revision/git tag — the exact capability
this platform's own freeze pass (§1) exists to provide.

---

## 7. Decision Register

### Required decisions (block Phase 2 start)
- **D-1. Sentiment model selection for English-language content.** No default exists; this report
  identifies requirements only (§4).
- **D-2. Research design specifics** (§3): comparative vs. pooled framing, channel-selection
  rationale, sampling rule, time window.
- **D-3. Config-override mechanism for this study**, given the platform's single global config
  file — a separate named config file the project owner maintains, or another convention.
  Operational choice, not an engineering one.
- **D-4. Ethics/IRB routing** for this specific study (ET-1) — which institutional process
  applies, and whether it has been initiated.
- **D-5. Inter-rater reliability threshold** for the Phase 4 gold-sample validation gate — this
  report does not set one.
- **D-6. Privacy policy and data-retention/deletion process** (L-1) — must exist as a real
  document before collection, not before publication.

### Optional decisions (can be made during Phase 2/3, don't block Phase 1 closing)
- **D-7. Multi-person collection access** — relevant only if more than one researcher needs to
  run collection independently; if so, the no-live-server-entrypoint gap (§1) becomes a Required
  decision instead of Optional.
- **D-8. Target-of-affect component** (§4) — enable for entity-specific sentiment, or leave
  disabled.
- **D-9. Whether to pursue the YouTube API quota-extension request preemptively** or only if
  Phase 3's pilot shows it's needed.

### Future decisions (Phase 5+, not needed to leave Phase 1)
- **D-10. `replication.stage` → `publication`** timing (R-1) — needed before manuscript
  submission, not before collection.
- **D-11. Whether to close the no-live-server-entry-point gap (T-2)** as a real engineering task —
  explicitly out of this report's scope; a future decision for whoever next picks up engineering
  work on this platform, not this study's problem to solve unless D-7 makes it one.

---

## 8. Go / No-Go Assessment

**Phase 1 (this planning phase): Go — already satisfied by this report.**

**Phase 2 (infrastructure setup): Conditional Go** — may begin once D-1 through D-6 (the Required
Decisions) are resolved by the project owner. Nothing technical blocks starting infrastructure
setup in parallel with finalizing D-2 (research design specifics), but D-1 (model selection) and
D-6 (privacy/retention policy) should be resolved before any real credential is provisioned or
any real comment is collected, even in Phase 2's own dry run.

**Phase 3 (pilot collection): No-Go until Phase 2's exit criteria are met**, specifically: a real
model is selected and pinned (not a placeholder), and a successful single-video dry run has
produced a correctly-provenanced export. Collecting real data on an unvalidated or
placeholder-configured pipeline would waste real quota and produce data that cannot be trusted
without redoing the work.

This assessment is not a statement that the platform is inadequate — it proved itself in exactly
the way T-029 was designed to prove. It is a statement that *this specific study* has real,
identified preparation work ahead of it, distinct from and larger than a config swap, and that
naming that work honestly now is cheaper than discovering it mid-collection.

---

## Sources

- [commentThreads: list — YouTube Data API — Google for Developers](https://developers.google.com/youtube/v3/docs/commentThreads/list)
- [YouTube API Quota: 100 Searches Burn 10,000 Units (2026) — SocialCrawl](https://www.socialcrawl.dev/blog/youtube-data-api-2026)
- [YouTube's API Quota Is 10,000 Units/Day — DEV Community](https://dev.to/siyabuilt/youtubes-api-quota-is-10000-unitsday-heres-how-i-track-100k-videos-without-hitting-it-5d8h)
- [YouTube API Services Terms of Service — Google for Developers](https://developers.google.com/youtube/terms/api-services-terms-of-service)
- [YouTube API Services Terms of Service (EMEA) — Google for Developers](https://developers.google.com/youtube/terms/api-services-terms-of-service-emea)
- [YouTube API Services — Developer Policies — Google for Developers](https://developers.google.com/youtube/terms/developer-policies)
- [Association of Internet Researchers — AoIR](https://aoir.org/)
- [Association of Internet Researchers — Wikipedia](https://en.wikipedia.org/wiki/Association_of_Internet_Researchers)
