# Entity-Centric Migration — Priority Reassessment (Post Step 0.1)

**Scope.** Not a redesign. The ten-part target architecture, the database/contracts redesign, and the six-phase structure in `Entity_Centric_Migration_Plan_v2.md` stand unchanged. This document re-examines *when* and *why* each remaining step (1.1 through 5.2) is worth doing, given the confirmed fact that the current production corpus has zero cross-analyst video/comment duplication — the opposite of what most of the original sequencing assumed.

**What changed, in one sentence.** Phase 1/2's original justification was "stop active duplication from happening"; that active duplication does not currently exist, so Phase 1/2 lose urgency. Phase 3's justification was "fix the fingerprint bug the duplication exposed"; that bug is a latent code defect independent of whether duplication is currently present, so Phase 3 keeps its urgency and, on inspection, has no hard dependency on Phase 1 — meaning it can and should move earlier, not later.

---

## Per-step reassessment

### Step 1.1 — Creator membership resolver as a standalone function
1. **Still required?** Yes.
2. **Current justification:** no longer "stop duplicate fetching happening right now" (nothing is being duplicated). Now: extracts logic currently duplicated between the one-time backfill script and any future live resolution, and is the first concrete case for Phase 4's resolver registry.
3. **Priority change:** lowered. Not blocking any correctness fix; can move behind Phase 3.
4. **Simpler to implement?** No change — same "extract existing logic into a function" difficulty regardless of duplication status.
5. **Real problem or future-proofing?** Future-proofing. It was already partly this in the original plan; the reassessment makes that explicit rather than implicit.

### Step 1.2 — Rewrite `collect_videos()`/`collect_comments()` to consume `EntityVideoLink` output
1. **Still required?** Yes, eventually.
2. **Current justification:** the original claim — "immediate, measurable reduction in duplicate API calls and storage on the very next full collection run" — is not true today; there is no duplication to reduce. Justification now: (a) defends against recurrence of the exact bug class that caused the 144-video figure (a second channel-collision, or a future channel change), (b) becomes load-bearing, not merely defensive, the moment Phase 4 introduces entity types (`topic`, `campaign`) whose membership genuinely overlaps.
3. **Priority change:** lowered relative to Phase 3. Raised again once Phase 4 is imminent — it is a hard prerequisite there, not optional.
4. **Simpler to implement?** Not simpler technically, but *lower-risk to validate right now*: refactoring collection logic against a corpus with no duplication to reconcile is a cleaner testing environment than doing it against live duplication later.
5. **Real problem or future-proofing?** Future-proofing today; becomes a real, load-bearing fix again at Phase 4.

### Step 1.3 — Add `resolve_membership` stage to `run_pipeline()`
Inherits 1.1/1.2's answers directly — same downgrade, same conditions for re-upgrading at Phase 4.

### Step 2.1 — Remove the per-analyst loop from `preprocess/pipeline.py`
1. **Still required?** Yes, marginally.
2. **Current justification:** the original "proves the pattern before the expensive stages" framing stands, but its *efficiency* framing (avoiding reprocessing duplicate comments) is now moot — there is nothing duplicated to reprocess. What remains is pure code-simplicity: one fewer looping/checkpoint-naming axis to reason about.
3. **Priority change:** lowered. No urgency; batchable with other cleanup.
4. **Simpler to implement?** Marginally easier to *validate* now — old-vs-new output equivalence is close to trivial to check on a duplicate-free corpus.
5. **Real problem or future-proofing?** Mostly future-proofing / technical debt reduction now, though it remains correct preparation for Phase 4's eventual overlapping-membership entities.

### Step 2.2 — Remove the per-analyst loop from `embeddings/pipeline.py` and `sentiment/pipeline.py`
1. **Still required?** Yes, eventually.
2. **Current justification:** the original claim that "this is where the migration starts paying for itself in wall-clock time" is **not currently true** — there is no redundant embedding/sentiment computation happening today, because there are no duplicate comments to compute over twice. The compute-savings argument is void until duplication reappears.
3. **Priority change:** lowered, more than 2.1 — this was the step whose benefit was most explicitly tied to eliminating wasted compute, which is exactly the assumption Step 0.1 disproved for the current corpus.
4. **Simpler to implement?** No meaningful change in difficulty.
5. **Real problem or future-proofing?** Future-proofing only, for now.

### Step 3.1 — Implement `AnalysisScope` contract and `resolve_scope()`
1. **Still required?** Yes — unaffected by the duplication finding, because the fingerprint-mismatch bug is a defect in *how `run_topics`/`run_topic_evolution` independently re-derive scope*, not a symptom of duplicated data. Duplication only made the bug visible; removing duplication didn't remove the bug, it just stopped triggering it.
2. **Current justification:** strengthened, if anything. The bug can resurface from any future data change that makes the two functions' independent re-derivations disagree — a new analyst, a re-run with different preprocessing config, or (concretely) Phase 4's own new entity types — not only from duplicate videos specifically.
3. **Priority change: raised.** This step has no hard dependency on Phase 1 — it can be built directly against Phase 0's already-implemented canonical tables (`comments_canonical.parquet`), which already exist and, on the current corpus, are identical in content to the raw tables since there's nothing to deduplicate. Recommend moving Phase 3 ahead of Phase 1/2 in execution order.
4. **Simpler to implement?** Yes, in the one way that matters most: the plan's own highest-value validation check — "run old and new resolution paths, assert identical comment-ID sets" — is close to trivial to pass right now, precisely because there's no duplication to create disagreement between them. This is the cleanest possible baseline to lock the fix in against. Waiting means doing this validation later against a corpus that may again contain the ambiguity the check exists to catch.
5. **Real problem or future-proofing?** A real, present (if currently dormant) code-correctness defect — not future-proofing.

### Step 3.2 — Rewrite `run_topics()` to take `scope_id`
Inherits 3.1's answers. One addition: this is the higher-difficulty half of the fix (683-line file, careful surgery) — doing it now, while corpus state is simple and well-understood, is lower-risk than doing it later.

### Step 3.3 — Rewrite `run_topic_evolution()` to read the persisted fingerprint
Inherits 3.1's answers. This is the literal fix for the bug that motivated the whole migration. Worth stating plainly: on the current corpus, `run_topics` and `run_topic_evolution` most likely already agree today, coincidentally, because there's nothing to disagree about — which makes right now the ideal moment to structurally guarantee that agreement, rather than waiting until a future data change reintroduces the conditions for disagreement and this becomes a live-manuscript-affecting bug again.

### Step 3.4 — Update `analysis/topic_sentiment.py`
Inherits 3.1's answers; low difficulty, unaffected in shape by this reassessment.

### Step 4.1 — Implement `topic`/`campaign`/`event`/`custom` resolvers
1. **Still required?** Yes — unaffected by the Step 0.1 finding either way. This was already framed as extensibility, not a bug fix, before this reassessment.
2. **Current justification:** unchanged — delivers the actual "domain-agnostic platform" capability.
3. **Priority change:** none in relative terms (still correctly sequenced after Phase 3). In absolute terms it can start sooner than originally implied, since Phase 3 is now recommended earlier.
4. **Simpler to implement?** No change.
5. **Real problem or future-proofing?** Explicitly future-proofing, as originally framed. This is the one phase the Step 0.1 finding doesn't touch.

### Step 5.1 — Package-and-cut-over the shadow analysis pipeline
1. **Still required?** Yes — entirely unaffected by the duplication finding. This is about the reproducibility of the *already-published* manuscript's tables, a live concern regardless of corpus duplication state.
2. **Current justification:** if anything, more urgent now, for a reason specific to this reassessment: Phase 3 is being moved earlier, and Phase 3 is exactly the step that renames/generalizes the `configuration` column the shadow scripts read (`topics.parquet`). Auditing which of the ~15 shadow scripts still read `configuration` should happen *before* that column's meaning changes, not after.
3. **Priority change: raised, and resequenced.** Recommend running this step's audit in parallel with, or immediately before, Phase 3 — not left at the end as originally sequenced. This directly matches the original plan's own risk table, which already flagged this ordering as preferable; the duplication finding just removes the reason (Phase 1/2 urgency) that was crowding it out.
4. **Simpler to implement?** No change — still a packaging/testing exercise on already-working logic, per the prior engineering audit.
5. **Real problem or future-proofing?** A real, present problem — protecting already-published results — unrelated to the duplication finding.

### Step 5.2 — Run `cutover_entity_model`, deprecate old tables
1. **Still required?** Yes, unchanged — the formal completion of the migration.
2. **Current justification:** unchanged.
3. **Priority change:** stays last, contingent on 5.1's audit being clean and Phase 3 being stable and validated. Its calendar position shifts only because 5.1 and Phase 3 both move earlier.
4. **Simpler to implement?** No change.
5. **Real problem or future-proofing?** Real — closes out the platform's dual-data-model risk. Unaffected by the duplication finding.

---

## Revised roadmap

| Order | Step(s) | Change from original plan |
|---|---|---|
| 1 | Step 0.1 | Done. |
| 2 | Step 5.1 (shadow-pipeline audit/packaging) | **Moved from last to second.** Run in parallel with or just before Phase 3, to catch `configuration`-column readers before Phase 3 changes that column. |
| 3 | Phase 3 — Steps 3.1 → 3.2 → 3.3 → 3.4 | **Moved ahead of Phase 1/2.** No hard dependency on Phase 1; fixes a real latent defect; easiest validation window is now, on a duplicate-free corpus. |
| 4 | Phase 1 — Steps 1.1 → 1.2 → 1.3 | **Postponed**, not removed. Downgraded from "fixes active duplication" to "hardening + Phase 4 prerequisite." Do before Phase 4, not before Phase 3. |
| 5 | Phase 2 — Steps 2.1 → 2.2 | **Postponed**, not removed. Kept immediately after Phase 1 (Phase 2 consumes Phase 1's output shape); downgraded from "compute savings" to "code simplification + Phase 4 prerequisite." |
| 6 | Phase 4 — Step 4.1 | Unchanged in relative position (still after 1–3), unaffected in justification by this reassessment. |
| 7 | Step 5.2 (cutover, deprecate old tables) | Unchanged — last, contingent on 5.1 and Phase 3 being stable. |

**Nothing is recommended for outright removal.** Every step remains justified; five of the twelve remaining steps (1.1, 1.2, 1.3, 2.1, 2.2) change from "fixes an active problem" to "postponed hardening/prerequisite work," and four steps (3.1–3.4) move earlier because they fix a real defect that duplication only ever made *visible*, not caused. Step 5.1 also moves earlier, for a reason independent of the duplication finding: it protects the already-published manuscript from a schema change Phase 3 is about to make.

## Recommended next step

Begin the Step 5.1 audit now (identify every reader of `topics.parquet`'s `configuration` column, including the shadow scripts), in parallel with starting Step 3.1 (`AnalysisScope` contract). Neither requires code changes to ship yet — 5.1 is an audit, 3.1 is a new, additive schema. Awaiting your go-ahead before starting either.
