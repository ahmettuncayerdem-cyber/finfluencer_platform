# Minimal Publishable Validation Study Design
## "Audience Narrative Reception and Sentiment Across Differently-Positioned International News Channels: A Comparative Analysis of Gaza War YouTube Comments"

**Date:** 2026-08-07
**Companion to:** `docs/research/GAZA_PILOT_PHASE1_PLAN.md` (Phase 1 preparation plan — this
document is a design proposal that plugs into that plan's Phase 3/§3, not a replacement for it).
**Status:** Design proposal for the project owner's review and decision (Decision Register D-2).
Not yet approved, not yet executed. No repository, configuration, or code changes.

---

## 0. One correction to the brief, made explicit rather than quietly absorbed

The brief frames this as a study of "competing strategic narratives" carried by the channels
themselves. **This platform's pipeline analyzes comments, not the channels' own video/editorial
content.** The data this study will actually have is *audience* discourse — what viewers write in
response to each channel's coverage — not the channels' own framing. These are related but
distinct constructs, and a paper that claims to measure "channel narratives" using only comment
data would have a validity gap a reviewer will find immediately.

The design below is therefore framed as a study of **audience narrative reception and sentiment**
— how differently-positioned news channels' audiences differ in what they emphasize and how they
feel about it — which is what the data actually supports, is still a genuine and citable
contribution to platformized political communication research, and does not require adding any
video/transcript-content analysis capability this platform doesn't have. If the project owner's
actual interest is the channels' own editorial framing, that is a different, larger study
requiring a different data source (video transcripts/descriptions), and should be named as such
rather than approximated with comment data.

---

## 1. Design logic: why this is the *smallest* defensible version

Three independent constraints are minimized simultaneously by the same set of choices, not
traded off against each other:

- **Quota/compute cost** scales with total comment volume collected. The single biggest lever is
  **bounding comments per video** at collection time (a fixed cap, not "collect everything the
  channel ever posted"), which makes total cost predictable in advance regardless of how viral
  any one video turns out to be — the opposite of the original finfluencer study's whole-channel
  approach, which was appropriate there and is not appropriate for a minimal validation pilot.
- **Methodological risk** is minimized by choosing a **descriptive, comparative** research
  question (no causal claims), a small but real human-validation step (not skipped, not
  oversized), and channels selected for *maximal, citable institutional contrast* rather than
  broad coverage — a "most-different-systems" comparative logic (standard in comparative media
  research) that actually **increases** the chance of detecting real differences with a small N,
  rather than diluting them across many similar cases.
- **Software validation coverage** falls out of the same design almost for free: comparing across
  channels exercises the **pooled** BERTopic configuration; channel-specific framing exercises
  the **within-analyst** configuration; a genuinely new-language model exercises the
  model-swap/revision-pinning mechanism for the first time with a real, non-placeholder change;
  and the full Report → citation → CSV/PDF export path is exercised at real (not synthetic-test)
  scale for the first time since the provenance-column work.

## 2. Research questions

- **RQ1 (topical emphasis).** Do audience comment sections on differently-positioned
  international news channels differ in which Gaza-War-related topics they emphasize? —
  answered from the **pooled** BERTopic configuration (cross-channel comparability) plus the
  **within-analyst** configuration (channel-specific topic structure).
- **RQ2 (sentiment).** Does audience sentiment differ systematically by channel and by topic? —
  answered directly from the master table's own per-comment `sentiment_class`/`sentiment_prob`
  columns, cross-tabulated against `topic_id_pooled` and `analyst_key` (a standard groupby the
  researcher performs on the exported CSV — this platform's live-API path does not itself
  produce a topic×sentiment summary table; the CSV already contains everything needed to build
  one, which is the appropriate division of labor between the platform and the analyst).
- **RQ3 (optional/stretch, not required for publication viability).** Does topical/sentiment
  emphasis shift over the bounded time window? Only pursued if Phase 3 pilot data volume and
  time-window length support it — explicitly not a load-bearing claim of the minimal design, to
  avoid a second axis of uncertainty (temporal dynamics) stacking on top of the cross-channel
  comparison this design is actually built to detect well.

## 3. Channel selection (3, not 9)

Three channels, chosen for maximal institutional contrast rather than broad coverage — the
"most-different-systems" logic:

| Channel | Institutional positioning (factual, citable) |
|---|---|
| BBC News | UK public-service broadcaster, license-fee funded |
| Al Jazeera English | Doha-headquartered, Qatar state-funded, historically embedded regional coverage of this conflict |
| TRT World | Ankara-headquartered, Turkish state broadcaster |

This is a factual/institutional basis for selection (funding source, headquarters, editorial
lineage), not a claim about any channel's accuracy or bias — that comparison is the paper's
finding, not its premise. If the project owner prefers different channels, the same logic
applies: pick for maximal, citable institutional contrast, not familiarity or convenience, and
state the selection rationale in the Methods section explicitly (this is itself a defensible,
citable methodological choice, and reviewers will ask for it either way).

**Why 3, not the original 9:** a 3-channel most-different-systems design gives real comparative
leverage at roughly a third of the collection cost, and is a completely standard N for
comparative content-analysis studies in this literature — publishability here comes from design
rigor (contrast, pre-registration, validation), not channel count.

## 4. Sampling design

- **Time window:** a short, bounded period (target: 2-3 weeks) anchored to one specific,
  identifiable, citable escalation/event in the conflict's timeline. **Not fixed by this
  document** — pin the exact dates during Phase 3 reconnaissance, once the project owner
  confirms which specific event anchors the window (this needs current, specific knowledge of
  the conflict timeline that should come from the research team, not be assumed here).
- **Video sampling:** a fixed number of videos per channel within the window — target **6-8
  videos per channel** (18-24 videos total), selected via each channel's own upload feed
  (`playlistItems.list`, 1 quota unit/page) rather than repeated `search.list` calls (100
  units/query) wherever the platform's collection engine supports it — cheaper and removes
  keyword-search's own selection-bias question from the sampling design entirely.
- **Comment sampling:** a fixed cap per video — target **up to 500 comments per video** (all
  comments if a video has fewer), ordered by relevance if the platform's collection path
  supports that ordering option, otherwise by recency. This is the single most important lever
  in this whole design: it makes total cost predictable *before* collection starts, regardless
  of how much real engagement any one video attracts — directly closing the "unmeasured
  volume" gap the Phase 1 plan flagged, by design rather than by discovery.

## 5. Budget estimate (planning figures — confirm at Phase 3 pilot, not assumed final)

| Quantity | Estimate |
|---|---|
| Channels | 3 |
| Videos | 18-24 (6-8 × 3) |
| Comments/video cap | 500 |
| **Total comment ceiling** | **~9,000-12,000** |
| `commentThreads.list` cost | ~1 unit/~100-comment page → **~90-120 units** |
| Video discovery (`playlistItems.list`) | ~1 unit/page, negligible at this scale |
| Video metadata (`videos.list`, batchable) | ~1 unit/call, negligible at this scale |
| **Total estimated quota** | **well under 500 units — under 5% of the default 10,000/day quota** |

This leaves large margin for pilot-stage mistakes, re-runs, and Phase 4 validation-sample
re-checks without approaching the default quota ceiling, and specifically **removes Q-1 (quota-
extension risk) from this study's risk register** — a direct, quantified consequence of the
per-video comment cap, not a hope.

Compute cost (BERTopic + transformer sentiment inference) scales with total comment count and is
therefore also bounded by the same cap — at ~10,000 comments this is a small fraction of the
~17,500-comment run T-029 already proved completes in well-understood, bounded time.

## 6. Model readiness — decision required, not made here (Decision Register D-1)

Per `docs/implementation/V1.0_RESEARCH_READINESS_AUDIT.md` §4/§9: an English-language sentiment
model must be selected and pinned to a real HuggingFace commit revision before Phase 2 closes.
Two additional requirements specific to this design, not previously stated:

- Given RQ1/RQ2's comparative framing, whatever model is chosen must be applied **identically**
  across all three channels — this is automatic (one `sentiment.primary_model` config value
  applies platform-wide), but worth stating as an explicit methodological guarantee in the
  Methods section, since it is exactly the kind of thing a comparative-design reviewer checks.
- The topic-modeling embedding model (`paraphrase-multilingual-MiniLM-L12-v2`) is already
  multilingual and can plausibly remain unchanged (per the Phase 1 assessment) — still requires
  the same pilot-stage coherence check, at this design's smaller, cheaper scale.

## 7. Validation design (Phase 4, scaled to this design)

- **Human-coded gold sample:** ~200 comments, stratified across the 3 channels (roughly balanced,
  not proportional to raw volume, so the smallest channel's comments aren't underrepresented in
  the reliability estimate) and across predicted sentiment classes (oversample the model's
  predicted-negative and predicted-neutral comments slightly, since positive/negative asymmetry
  is common in war-discourse sentiment and a naively random sample can under-power reliability
  estimation on the minority class).
- **Reliability threshold:** a Decision Register item (D-5) still open — a common, citable
  convention for this kind of categorical coding is Krippendorff's alpha ≥ 0.667 (minimum
  acceptable) or ≥ 0.80 (good reliability); the project owner should set the actual bar and
  the consequence (proceed / re-code / reselect model) before coding begins, not after seeing
  the number.
- **Two coders minimum**, blind to the model's own predictions during coding, per standard
  practice and consistent with this repository's own prior gold-standard methodology
  (`gold_standard_sample_n500_CODER_FACING_blinded.csv` in `research_archive/` shows this exact
  "coder-facing, blinded" convention was already used once — reuse it, don't reinvent it).

## 8. What this design validates in Version 1.0, mapped explicitly

| Study design choice | V1.0 component exercised |
|---|---|
| 3-channel roster swap, first non-Turkish config | `config/analysts.yaml` roster-swap path, live for the first time with a real different roster |
| English-language text collection | Preprocessing pipeline on non-Turkish content, first real exercise |
| Cross-channel comparison (RQ1) | Pooled BERTopic configuration |
| Channel-specific framing (RQ1) | Within-analyst BERTopic configuration |
| New sentiment model | `ModelReference`/revision-pinning mechanism exercised with a genuinely new, non-placeholder value for the first time |
| Master table with `analyst_key`/topic/sentiment columns | The exact CSV schema `docs/research/OUTPUT_CODEBOOK.md` documents, at real (not synthetic-test) multi-channel scale |
| Provenance columns | First real-study exercise of `analysis_run_id`/model name+revision columns added this freeze pass |
| Report with 2 citations, finalize, CSV export, PDF export | The full live workflow T-029 proved, re-proved under different (English, multi-channel, politically sensitive) content for the first time |
| `replication.stage` discipline | Recommend running at `submission` (current default) through data collection/analysis, raised to `publication` before manuscript submission, per existing guidance |

## 9. Target special issue — open item, not assumed

This design is written generically for a computational social science / political communication
venue publishing comparative platform-discourse research on conflict framing — it does not
assume a specific special issue's CFP scope, because none was named. Confirm the actual target
venue and its specific thematic requirements before finalizing RQ framing (§2) — a named CFP may
narrow or reweight which of RQ1/RQ2/RQ3 should be foregrounded.

## 10. What this design deliberately does not do

- Does not claim to measure channel editorial narratives directly (§0).
- Does not attempt causal inference — purely descriptive/comparative, appropriate to the design's
  scale and appropriate to what observational comment data can actually support.
- Does not collect whole-channel, unbounded data — the per-video cap (§4) is a deliberate
  trade-off of completeness for cost-predictability and risk reduction, stated explicitly as a
  limitation in the eventual Methods section, not hidden.
- Does not resolve Decision Register items D-1 (model selection), D-2 (this design itself, now
  proposed but not approved), D-4 (ethics/IRB routing), D-5 (reliability threshold), or D-6
  (privacy/retention policy) — this document narrows D-2 to a concrete proposal; it does not
  discharge the others.
