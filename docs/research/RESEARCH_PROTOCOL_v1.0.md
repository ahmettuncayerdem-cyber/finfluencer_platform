# Research Protocol v1.0

## Audience Reception of Competing Strategic Narratives in International News Coverage of the Gaza War: A Comparative YouTube Comment Analysis

**Document status:** Immutable blueprint. Deviations during execution must be logged in §16
(Protocol Amendment Log), not made silently — this is itself part of this protocol's
reproducibility commitment, not bureaucratic overhead.

**Prepared by:** Principal Computational Social Science Methodologist role, per operator
authorization (2026-08-07). Supersedes no prior document; builds directly on and does not
re-derive `docs/research/GAZA_PILOT_MINIMAL_DESIGN.md` (approved research design),
`docs/research/GAZA_PILOT_PHASE1_PLAN.md` (Decision Register D-1–D-11), and
`docs/research/GAZA_PILOT_PHASE2_INFRASTRUCTURE.md` (technical baseline, closed, 19/19 smoke
test passed 2026-08-07 — not reopened here).

**Target venue (confirmed by operator):** İletişim ve Diplomasi Dergisi (Communication and
Diplomacy), special issue "Küresel Çağda Anlatılar, Algılar ve Temsil" (Narratives, Perceptions
and Representation in the Global Age), December 2026 issue.

**Timeline posture (confirmed by operator):** Accelerated protocol for this submission window.
Scope is deliberately compressed relative to the Minimal Design's original figures — every
compression is stated explicitly in §7/§13, not silently assumed.

**Ethics posture (confirmed by operator):** Operator has institutional ethics committee access;
§10 is written as a submittable application summary, not a placeholder.

---

## 1. Feasibility Assessment — Real Constraints, Verified Not Assumed

This section exists because a protocol that ignores its own venue's real constraints is not a
protocol, it is a wish. Every figure below was fetched directly from the journal's own DergiPark
page and author-guidelines page on 2026-08-07, not recalled from training knowledge.

| Constraint | Verified fact | Implication for this protocol |
|---|---|---|
| Submission window | Currently **closed**. Opens 01.09.2026, closes 15.09.2026 (may close earlier "if submission volume is high"). Today: 07.08.2026. | 25 days to window open, 39 days to hard close. §13's timeline is built backward from 15.09.2026, not forward from an assumed comfortable runway. |
| Required uploads | Copyright Transfer Form, **Similarity Report**, **Ethics Committee Approval Certificate** — all three mandatory at submission, per the journal's own announcement page. | Ethics approval (§10) is on the critical path, not a parallel nice-to-have — addressed as the first, not last, execution step. |
| Reference management | As of 2026, submissions must be prepared with Zotero/EndNote/Mendeley/Word's citation manager; papers not so prepared are returned unreviewed. | Manuscript preparation must use one of these tools from the first citation, not retrofitted. |
| Format | Turkish title + English title; Turkish abstract 200–220 words; English abstract 200–250 words; **extended English abstract 600–800 words before the introduction**; sections: Introduction, Conceptual Background, Method, Analysis/Discussion, Conclusion, Acknowledgements, References. Times New Roman 12pt, 1.5 spacing, 2.5cm margins. Double-blind (no author info in the manuscript file; separate cover page). | §12 maps this study's content onto exactly these sections and word budgets, not a generic IMRaD template. |
| Length | **≤ 9,000 words total**, including both abstracts, keywords, the extended English abstract, footnotes, acknowledgements, and bibliography. | This is a tight ceiling for a computational social science paper with a real analysis section and a substantial theory framework. §12 treats this as a binding design constraint on how much can be reported in-line versus pushed to a public replication package (already a platform capability — `replication.stage` / `finfluencer export`, per the technical baseline). |
| Indexing (correcting a prior overstatement) | TR Dizin, Index Copernicus, DRJI, ResearchBib, ASOS Index, İdealonline. **Not** SSCI/Scopus/Web of Science. An earlier document in this project's history described this line of work as targeting "SSCI-quality" — that description is corrected here: it was an unverified assumption, not a checked fact, and is retracted. | Framed throughout as a rigorous, TR Dizin-indexed national-venue contribution — a legitimate and appropriate target, described accurately rather than inflated. |
| Publisher / editorial character | Cumhurbaşkanlığı İletişim Başkanlığı (Turkish Presidency's Directorate of Communication); Editor-in-Chief Prof. Dr. Burhanettin Duran. Recent issues include a "15 Temmuz" special issue and an April 2025 "Filistin Özel Sayısı." | Noted as relevant editorial context, not as license to compromise analytical neutrality — see §4.3 (positionality) and §9.4 (the study's own explicit non-partisanship commitment, which if anything is *more* important to state explicitly given this venue's institutional character, not less). |
| Review timeline vs. publication target | Journal's own published statistics: pre-check ~18 days, peer review ~108 days, publication ~21 days ≈ **147 days average** from submission. A 15.09.2026 submission at that average pace lands in **February 2027**, not the December 2026 issue. | **Real, unresolved tension, stated plainly, not papered over.** Special issues sometimes run an expedited parallel track under guest editors, but the journal's own public pages make no such guarantee. §14 (Risk Register) carries this as an open risk, not a resolved one — the operator should not be surprised if the December 2026 target slips regardless of how well this protocol is executed, because that risk is structural to the venue, not to this study's quality. |
| Thematic fit | Real CFP topic list includes: "Stratejik Anlatılar ve Uluslararası Siyaset," "Savaş, Çatışma ve Barış Söylemleri," "Kimlik, Milliyetçilik ve Ötekilik," "İsrail ve Orta Doğu'da Değişen Güvenlik Dinamikleri," "Uluslararası Hukuk, Normlar ve Temsil Sorunları." | Confirmed alignment — not assumed. §3 explicitly maps this study onto "Stratejik Anlatılar ve Uluslararası Siyaset" as its primary topical fit. |

**Critical prior-art finding (must be addressed, not an optional related-works citation):**
Boyacı Yıldırım, M. (2026). "Kamuoyunun Dijital Tanıklığı: Uluslararası Haberlerde Gazze Üzerine
Kullanıcı Söylemlerinin Duygu ve Konu Temelli Analizi." *TRT Akademi*, 11(26), 374–411 —
published 31 January 2026, using **BERTopic + BERT-based sentiment analysis on YouTube comments
from 11 international news organizations' Gaza-conflict videos**, explicitly framed around the
"framing–reception relationship." This is real, current, closely adjacent prior art in a sibling
Turkish state-affiliated journal, discovered via direct search on 2026-08-07, not assumed away.
§4.4 states this study's differentiation from it explicitly and substantively, because a reviewer
familiar with the Turkish communication-studies literature will find it in about the same search
this protocol used, and the manuscript must pre-empt that comparison rather than be caught by it.

---

## 2. Executive Summary

This protocol designs a comparative, theory-driven study of how audiences on three
institutionally distinct international English-language news channels (BBC News, Al Jazeera
English, TRT World) respond — topically and affectively — to coverage of a real, current,
citable inflection point in the Gaza War: the late-July 2026 "Board of Peace" Hamas-disarmament
roadmap announcement and its contested implementation. Framed through Strategic Narrative theory
(Miskimmon, O'Loughlin & Roselle) rather than generic framing-effects language, the study treats
YouTube comment sections as an observable site of *narrative reception and contestation* —
where a state-linked, a regionally embedded, and a Western public-service broadcaster's
differently positioned coverage of the same real-world event meets differently positioned
audiences, producing measurably different topical emphases and affective responses. The
platform infrastructure this rests on is real, live-verified, and closed to further engineering
scope (`docs/research/GAZA_PILOT_PHASE2_INFRASTRUCTURE.md` addendum, 19/19 checks passed). This
document's job is the research design, not the software, and it is written to be executable
starting today under a hard 15 September 2026 submission deadline.

---

## 3. Theoretical Framework

### 3.1 Primary lens: Strategic Narrative Theory

Miskimmon, O'Loughlin, and Roselle's Strategic Narrative framework (*Strategic Narratives:
Communication Power and the New World Order*, Routledge, 2013; Roselle, Miskimmon & O'Loughlin,
2014, "Strategic narrative: A new means to understand soft power," *Media, War & Conflict*;
Miskimmon & O'Loughlin, 2025, "Strategic narrative: its origins and evolution, its connection to
public diplomacy, and some future paths," *Place Branding and Public Diplomacy*) theorizes how
political and media actors project narratives to shape how international order, conflict, and
identity are understood — and, crucially for this study, that such narratives can be
**contested or uncontested** in their reception. This is a public-diplomacy-native theoretical
vocabulary, a deliberate fit for a journal literally named *Communication and Diplomacy* and for
a CFP topic explicitly titled "Stratejik Anlatılar ve Uluslararası Siyaset." The three channels
selected (§5) are not arbitrary comparison cases but three distinct strategic-narrative
projection points: a Western public-service broadcaster (BBC), a regionally embedded,
state-funded broadcaster with deep institutional history covering this specific conflict (Al
Jazeera English), and a Turkish state broadcaster's international arm (TRT World) — three actors
plausibly narrating the same ceasefire-and-disarmament event differently, to audiences who may
receive those narratives with correspondingly different degrees of contestation.

The 2025 extension of this literature (Lerner, Miskimmon & O'Loughlin, "Thinking outside the
box: From frames to strategic ontologies in the analysis of media, war, and conflict," *Media,
War & Conflict*, 2025) is used explicitly in this study's Conceptual Background to justify
moving beyond a pure framing-effects vocabulary toward "strategic ontologies" — how audiences'
own comments do not just register a frame but actively construct competing accounts of what the
ceasefire *is* (a breakthrough, a stalled failure, a stage-managed performance) — directly
operationalized by this study's topic-modelling output (§8) rather than assumed.

### 3.2 Secondary lens: audience reception and affective publics

- **Hall (1980), "Encoding/Decoding"** — the foundational warrant for treating audience comments
  as a site of meaning-*making*, not passive reception of a channel's encoded frame; grounds this
  study's own §0-equivalent correction (already made in the Minimal Design: this is a study of
  *audience narrative reception*, not of channel editorial content).
- **Entman (1993), "Framing: Toward Clarification of a Fractured Paradigm"** — the standard
  citation for what a "frame" analytically is, used to precisely name what this study's
  BERTopic output is (and is not) evidence of: topical/emphasis patterns in reception, not a
  content analysis of the source videos' own frames (which this platform does not collect).
- **Papacharissi (2015), *Affective Publics: Sentiment, Technology, and Politics*** — the
  theoretical bridge from this platform's automated sentiment classification to a defensible
  social-scientific construct ("affective publics"), rather than presenting `sentiment_class` as
  a bare technical output.

### 3.3 Positionality statement (required content, stated explicitly rather than left implicit)

This study analyzes publicly posted comments under news content produced by three
organizationally and nationally distinct broadcasters, one of which (TRT World) is affiliated
with the Turkish state that also publishes the target journal. The protocol commits explicitly
(§9.4) to identical, symmetric treatment of all three channels at every methodological step —
same collection parameters, same model, same coding protocol, same reporting template — as the
concrete, checkable safeguard against any appearance of asymmetric treatment. This statement is
written into the protocol itself, in advance, precisely so it cannot be an after-the-fact
defense.

### 3.4 Differentiation from Boyacı Yıldırım (2026)

Both studies use BERTopic + BERT-family sentiment analysis on YouTube comments under
international news channels' Gaza coverage — that overlap is real and must be named, not
obscured. This study differs on four concrete, checkable axes, each already load-bearing in the
existing approved design, not invented post hoc to manufacture distance:

| Axis | Boyacı Yıldırım (2026) | This study |
|---|---|---|
| Channel selection logic | 11 channels selected by keyword ("Gaza") + high view count — a broad, convenience-adjacent sample | 3 channels selected by an explicit **most-different-systems comparative logic** (funding source, headquarters, editorial lineage) — a smaller N with real, stated comparative leverage (`GAZA_PILOT_MINIMAL_DESIGN.md` §3) |
| Theoretical frame | Framing–reception relationship generally (Entman, Papacharissi, affective publics) | Strategic Narrative theory specifically (§3.1) — an IR/public-diplomacy-native contribution, not restated framing theory |
| Human validation | Not reported in the abstract; no stated reliability check on the automated NLP outputs | A blinded, two-coder gold-standard reliability check (§9) with a pre-specified Krippendorff's alpha threshold — addresses a standard, citable limitation of purely computational sentiment/topic studies |
| Temporal anchor | Not event-anchored (broad "Gaza" keyword, unspecified window) | Anchored to one specific, named, dated, citable event (§6) — a bounded, replicable sampling frame |

This table itself belongs in the manuscript's Conceptual Background section as the explicit
novelty statement, not left implicit for a reviewer to reconstruct.

---

## 4. Research Questions

Retained from `GAZA_PILOT_MINIMAL_DESIGN.md` §2, now explicitly reframed through §3.1's
theoretical lens (wording changed to reflect the theory, substance unchanged):

- **RQ1 (narrative emphasis).** Do audience comment sections on the three differently
  strategically-positioned channels differ in which aspects of the ceasefire/disarmament
  narrative they emphasize (e.g., breakthrough/hope framing vs. violation/failure framing vs.
  actor-blame framing)? — answered via pooled and within-channel BERTopic output.
- **RQ2 (affective reception).** Does audience sentiment toward this narrative differ
  systematically by channel and by topic — i.e., is the same real-world event received with
  measurably different affect depending on which channel's narrative projection it is embedded
  in? — answered via `sentiment_class`/`sentiment_prob` cross-tabulated against
  `topic_id_pooled`/`analyst_key`.
- **RQ3 (contestation, stretch/exploratory, not load-bearing for the core claim).** Within a
  single channel's comment section, is there evidence of *contested* rather than *uncontested*
  reception (e.g., bimodal sentiment distribution, explicit disagreement threads) — a direct,
  exploratory operationalization of Miskimmon et al.'s contested/uncontested narrative concept?
  Retained as optional per the Minimal Design's own discipline against stacking uncertain claims;
  included only if time and word budget (§1) allow in the final manuscript.

---

## 5. Research Design

Unchanged from `GAZA_PILOT_MINIMAL_DESIGN.md` §1/§3: a most-different-systems comparative design
across exactly three channels (BBC News, Al Jazeera English, TRT World), justified on factual
institutional grounds, not re-derived here. Real, verified channel IDs already on file in
`config/analysts.gaza_pilot.yaml` (Al Jazeera English and TRT World currently commented out,
ready to activate — see §7).

---

## 6. Temporal Anchor — A Concrete, Real, Citable Event (resolves the previously open D-Window item)

**Proposed anchor: the "Board of Peace" Hamas-disarmament roadmap announcement, 31 July 2026**
— mediated by Egypt, Qatar, Turkey, and the US, announced by President Trump alongside the
US-led Board of Peace and International Stabilization Force for Gaza, covering a phased Hamas
disarmament and Israeli withdrawal roadmap. Verified via direct search (Al Jazeera, 31 July
2026; UN News, 2 August 2026 reporting continued Israeli strikes despite the announced truce —
confirming this is a genuinely contested, not uncontroversially "resolved," event, which is
exactly the analytical condition RQ1–RQ3 need).

**Proposed observation window: 24 July – 10 August 2026** (18 days) — brackets the announcement
with one week of pre-announcement baseline and 10 days of post-announcement reaction, long
enough for comment accumulation, short enough to keep quota/compute cost inside the
already-verified budget (`GAZA_PILOT_PHASE2_INFRASTRUCTURE.md` §6). This window is immediately
collectible as of this protocol's writing (7 August 2026) — no waiting on a future event.

**This is a proposal, not a unilateral final decision** — it is the single most substantively
research-design-laden choice in this protocol, and per this whole engagement's standing practice
of not making such calls unilaterally, it should be confirmed (or replaced with a better-informed
alternative, if the operator has more current knowledge of the conflict timeline than a
2026-08-07 search snapshot provides) as the literal first action of Week 1 (§13), before any
collection call is made — a same-day confirmation, not a blocking delay.

---

## 7. Sampling Strategy (compressed for the accelerated timeline — every reduction stated explicitly)

| Parameter | Minimal Design (original) | This protocol (compressed) | Why compressed |
|---|---|---|---|
| Channels | 3 | 3 (unchanged) | Channel count is the comparative design's core leverage — not a place to cut. |
| Videos/channel | 6–8 | **4–5** | Fewer videos within the now-fixed 18-day window (vs. the original's flexible 2–3 week window) while keeping at least 2 videos/channel pre- and post-announcement for within-window comparison. |
| Comments/video cap | 500 | **300** | Reduces total volume and, more importantly, gold-standard coding load (below) to fit the compressed timeline without threatening the comparative design itself. |
| Total comment ceiling | ~9,000–12,000 | **~3,600–4,500** | Direct consequence of the above; still comfortably above minimum viable N for BERTopic + sentiment analysis at 3-way comparison scale. |
| Gold-standard validation sample | ~200, stratified | **~120, stratified** (40/channel) | Smallest sample size that still supports a defensible Krippendorff's alpha estimate at this N; below ~100 total, reliability estimates become unstable — 120 is the floor, not an arbitrary round number. |
| Video discovery method | `playlistItems.list` | Unchanged | Already the cheaper, less-biased method; no reason to change under time pressure. |

Quota impact of the compression: proportionally *lower* than the already-tiny Phase 2 budget
(~500 units) — well under 200 units for the full compressed collection. Quota was never the
binding constraint; researcher and coder time is, and this table compresses exactly that.

---

## 8. Data Collection Protocol

Executed via the already-approved, isolated `config/settings.gaza_pilot.yaml` /
`config/analysts.gaza_pilot.yaml` and `gaza_pilot_smoke_test.py`'s proven pattern (real
`create_app(use_live_collection=True)` workflow) — **not redesigned here**. Concrete changes
needed to move from smoke-test to real data collection (identify only, per the technical
baseline's own closure — the operator or a follow-up engineering pass executes these):

1. `config/analysts.gaza_pilot.yaml`: uncomment Al Jazeera English and TRT World (real channel
   IDs already on file); set `max_videos_per_analyst` / `max_comments_per_video` per §7's table
   (currently set to smoke-test-scale 2/50).
2. `config/settings.gaza_pilot.yaml`: `study.observation_window` → §6's proposed dates (once
   confirmed); `study.description` → this protocol's own study description (§2).
3. HDBSCAN parameters (`min_cluster_size`/`min_samples`), currently reduced for the ~63-comment
   smoke test, likely need re-tuning at the ~3,600–4,500-comment real-collection scale — a real,
   flagged technical follow-up, not assumed to transfer automatically either direction.

---

## 9. Measurement, Coding, and Validation

### 9.1 Automated measures (already validated, per the technical baseline)
- `sentiment_class` / `sentiment_prob`: cardiffnlp/twitter-roberta-base-sentiment-latest,
  pinned revision `3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7`, real-run-verified 2026-08-07.
- `topic_id_pooled`/`topic_label_pooled` (cross-channel) and `topic_id_within`/`topic_label_within`
  (per-channel): BERTopic, both configurations real-run-verified non-degenerate (topic_count=6
  at smoke-test scale; requires re-verification at full scale per §8 item 3).

### 9.2 Human gold-standard validation (the concrete answer to §3.4's differentiation claim)
- **Sample:** ~120 comments, stratified across the 3 channels (40/channel, not proportional to
  raw volume — protects the smallest channel's comments from underrepresentation in the
  reliability estimate) and oversampling the model's predicted-negative and predicted-neutral
  classes, per the Minimal Design's own already-stated rationale (§7 there).
- **Coders:** minimum two, blind to the model's own predictions during coding — reusing this
  repository's own prior "coder-facing, blinded" convention
  (`research_archive/gold_standard_sample_n500_CODER_FACING_blinded.csv`), not reinvented.
- **Reliability threshold:** Krippendorff's α ≥ 0.667 minimum acceptable, ≥ 0.80 preferred —
  standard convention for categorical content coding (Krippendorff, 2004, *Content Analysis: An
  Introduction to Its Methodology*). **Consequence rule, stated in advance (this is what makes it
  a real threshold and not a formality):** if α < 0.667 on the sentiment classes, the manuscript
  reports this explicitly as a limitation and downgrades RQ2's claims from "systematic
  differences" to "descriptive patterns, not confirmed by independent human coding" — the
  finding is reported honestly either way, not suppressed if it comes in low.

### 9.3 Statistical analysis plan
- RQ1: chi-square test of independence (topic distribution × channel), pooled configuration;
  Cramér's V for effect size.
- RQ2: Kruskal-Wallis test (sentiment score × channel), given non-normality expected in bounded
  probability scores; Dunn's post-hoc pairwise (already the platform's configured default,
  `config/settings.yaml`'s `statistics.post_hoc_pairwise`, reused for consistency).
- RQ3 (if included): qualitative/descriptive only — bimodality inspection of sentiment
  distribution per channel-topic cell; not claimed as a formal statistical test given its
  exploratory status.
- Multiple-comparison correction: Benjamini-Hochberg FDR across the primary tests (RQ1, RQ2),
  matching the platform's own already-configured default (`statistics.fdr_method`) rather than
  introducing a new convention for this manuscript alone.

### 9.4 Symmetry commitment (operationalizing §3.3's positionality statement)
Every step above — collection parameters, model, coding protocol, statistical tests — is applied
**identically** across all three channels, with zero channel-specific tuning at any stage. This
is a testable claim: the final config files and analysis scripts are the single, shared artifact
applied to all three, available in the replication package (§12).

---

## 10. Ethics Committee Application Summary

Since the operator has confirmed institutional ethics committee access, this section is written
as a submittable summary, not a placeholder.

**Study title:** Audience Reception of Competing Strategic Narratives in International News
Coverage of the Gaza War: A Comparative YouTube Comment Analysis

**Data source:** Publicly posted, non-restricted YouTube comments under public news videos from
three international news organizations (BBC News, Al Jazeera English, TRT World). No private
accounts, no direct messages, no content requiring authentication to view.

**Human subjects status:** Commenters are not directly recruited, contacted, surveyed, or
interacted with. Data consists of naturally occurring public discourse, collected via the
YouTube Data API v3's public, unauthenticated-read endpoints under YouTube's own Terms of
Service. This is standard practice under most institutional frameworks for observational digital
trace data (consistent with AoIR's *Internet Research: Ethical Guidelines 3.0*, already cited as
this project's ethics reference in `GAZA_PILOT_PHASE1_PLAN.md`), but is not itself a claim that
no ethics review is needed — the review is being sought precisely to have an independent
determination, not to pre-empt one.

**Anonymization:** Commenter identifiers are HMAC-hashed with a dedicated, non-reused salt
(`ANON_SALT`) before anything touches disk — irreversible, applied at first ingestion, already
implemented and live-verified (`collect/comments.py`, exercised in the 2026-08-07 smoke test).
Raw, re-identifiable text is never published; only `text_clean` (cleaned, de-identified content)
appears in any output.

**Retention:** Per `config/settings.yaml`'s `ethics.retention_days` default (90 days) — flagged
here, consistent with the Phase 1 Decision Register's own D-6, as a default carried forward
rather than a considered choice specific to this study; the ethics committee's own guidance on
an appropriate retention period for this data type should supersede this default, not the
reverse.

**Risk assessment:** Minimal risk. No individual commenter is identified, quoted with attributable
identity, or contactable from this study's outputs. The channels studied are large international
news organizations, not private individuals; the object of analysis is aggregate discourse
patterns, not any single commenter's views.

**Content sensitivity:** The subject matter (an active armed conflict) is emotionally and
politically sensitive. The study makes no claims about which channel's coverage or which
audience's reaction is more "correct," consistent with §3.3/§9.4's symmetry commitment, and does
not reproduce full comment text at any length that could be construed as amplifying any specific
individual's statement.

---

## 11. Manuscript Structure — Mapped to the Journal's Exact Required Sections

| Journal-required section | This study's content | Approx. word budget (within the 9,000-word total ceiling) |
|---|---|---|
| Turkish title / English title | — | — |
| Turkish abstract (200–220 words) | Condensed summary | 220 |
| English abstract (200–250 words) | Condensed summary | 250 |
| Extended English abstract (600–800 words, before Introduction) | Full study summary: motivation, theory, design, key findings, contribution | 800 |
| Introduction | Motivation: why audience reception of Gaza-conflict narratives, why this venue's thematic fit (§1 table), the real July 2026 anchor event (§6) | 500 |
| Conceptual Background | §3 in full — Strategic Narrative theory, secondary framing/reception lenses, explicit differentiation table from Boyacı Yıldırım (2026) | 1,500 |
| Method | §5–9 condensed: design, sampling (with the compression explicitly justified), measurement, validation, statistical plan | 1,800 |
| Analysis / Discussion of Findings | RQ1–RQ3 results, tied back to Strategic Narrative theory's contested/uncontested reception concept | 2,500 |
| Conclusion | Contribution, limitations (explicitly including the compressed-timeline sampling reductions and the reliability-threshold consequence rule from §9.2), future work | 800 |
| Acknowledgements | Platform/infrastructure acknowledgement, ethics committee approval reference | 100 |
| References | Full bibliography (§17 as the working list) | ~600–900 (est.) |
| **Total** | | **~9,000** (at ceiling — leaves no slack; §16 tracks any overage as a required amendment) |

Full underlying data, code, and replication package are **not** squeezed into the 9,000-word
manuscript — they are pointed to via the platform's own `finfluencer export`/replication-package
mechanism (`replication.stage: "submission"`, already the platform's live default), consistent
with how the journal's own citation conventions expect electronic-source referencing.

---

## 12. Timeline — Backward-Planned from 15 September 2026

| Dates | Milestone |
|---|---|
| 7–8 Aug (Days 1–2) | Confirm or replace §6's event anchor (same-day decision, not a blocking delay). Submit ethics committee application (§10) — the single longest lead-time item, started first. |
| 9–15 Aug (Days 3–9) | Activate full 3-channel `config/analysts.gaza_pilot.yaml`; apply §7's compressed sampling config; run full-scale collection; re-verify BERTopic non-degeneracy at real scale (§8 item 3) — using the already-proven smoke-test script, scaled, not redesigned. |
| 16–20 Aug (Days 10–14) | Draw and code the ~120-comment gold-standard sample (2 blinded coders); compute Krippendorff's α; apply §9.2's consequence rule if threshold not met. |
| 21–25 Aug (Days 15–19) | Run RQ1/RQ2 statistical analysis (§9.3); produce the master table, citation-backed Report, replication package export. |
| 26 Aug–2 Sep (Days 20–27) | Draft manuscript against §11's exact section/word map. |
| 3–6 Sep (Days 28–31) | Internal review pass against the journal's Author Guidelines checklist (§1 table) — format, word count, double-blind compliance, reference-manager-prepared bibliography. |
| 7–10 Sep (Days 32–35) | Buffer for ethics committee response latency and any required revision; finalize Copyright Transfer Form, Similarity Report. |
| **1–15 Sep** | **Submission window** — target submission as early in this window as the above allows, not at the 15th, given the "may close early if volume is high" caveat from §1. |

This timeline assumes the ethics committee approval (started Day 1) does not take materially
longer than ~3 weeks — a real assumption, not a guarantee, and the single largest schedule risk
in the entire protocol (§14).

---

## 13. Risk Register (protocol-specific — extends, does not repeat, the Phase 1/2 registers)

| Risk | Category | Severity | Mitigation / honest status |
|---|---|---|---|
| Ethics committee approval takes longer than ~3 weeks | Schedule | **High** | Started Day 1, not deferred; no mitigation beyond early submission exists at this seat — genuinely outside this protocol's control. |
| December 2026 issue target vs. ~147-day average review time | Schedule | **High** | Stated plainly in §1 as an unresolved structural tension; not this study's quality issue, the venue's own stated statistics. |
| Reviewer identifies overlap with Boyacı Yıldırım (2026) as insufficiently differentiated | Novelty/acceptance | Medium | §3.4's differentiation table is written to be the manuscript's own explicit pre-emption of this exact concern, not left to hope a reviewer doesn't notice. |
| Real-scale BERTopic produces degenerate topics (unlike the small smoke-test sample) | Technical | Medium | Explicitly flagged as an open, re-verify-before-trusting item (§8 item 3), not assumed to transfer from the 63-comment smoke test. |
| Gold-standard α falls below 0.667 | Methodological | Medium | Consequence rule pre-specified (§9.2) — reported honestly as a downgraded claim, not hidden or the threshold quietly lowered post hoc. |
| 9,000-word ceiling forces cutting the Conceptual Background or Analysis section below what the theory needs | Manuscript quality | Medium | §11's word budget already reflects this tension; any further cut is logged in §16, not made silently during drafting. |
| Compressed sampling (§7) yields too little topic/sentiment variance to detect real channel differences | Statistical power | Low–Medium | The most-different-systems design (§5) is specifically chosen to maximize detectable contrast at small N — the original design rationale for exactly this scenario, now doing double duty under time pressure. |

---

## 14. Decision Register (consolidated — final open items only, reconciled with Phase 1/2 registers, not renumbered from scratch)

### Mandatory (block submission)
- **D-Window.** §6's proposed anchor event/window — confirm or replace, Day 1.
- **D-4 (carried from Phase 1, now resolved by operator).** Ethics/IRB routing — resolved:
  operator has institutional access; §10 is the submittable summary.
- **D-5 (carried from Phase 1).** Reliability threshold — resolved in this protocol: α ≥ 0.667
  minimum, with the §9.2 consequence rule.
- **D-6 (carried from Phase 1, still open).** Privacy/retention policy beyond the 90-day
  platform default — should be set by the ethics committee's own guidance (§10), not this
  protocol.

### Recommended
- **R-New-1.** Confirm RQ3 (contestation, §4) is included in the final manuscript only if §11's
  word budget allows after RQ1/RQ2 are fully reported — a real, pre-committed cut criterion, not
  a vague "if there's room."
- **R-New-2.** Re-tune HDBSCAN parameters at full-collection scale (§8 item 3) before trusting
  topic output for the manuscript's actual findings.

---

## 15. What This Protocol Does Not Cover (explicit boundary, consistent with the operator's own instruction)

Persistence Layer, Authentication, software architecture, the sentiment/topic engine internals,
and the Google Cloud/API infrastructure are unchanged and out of scope here, per the operator's
explicit instruction that Phase 2 is closed as the technical baseline. This protocol's only
technical dependency on that baseline is the three config/script touch-points named in §8 —
identified, not redesigned.

---

## 16. Protocol Amendment Log

*(To be filled in during execution — any deviation from this document's specified sample sizes,
window, thresholds, or word budget is logged here with a date and one-line reason, not made
silently. Empty at time of writing, 2026-08-07.)*

| Date | Section | Original | Amended to | Reason |
|---|---|---|---|---|
| — | — | — | — | — |

---

## 17. Sources

- Miskimmon, A., O'Loughlin, B., & Roselle, L. (2013). *Strategic Narratives: Communication Power
  and the New World Order.* Routledge.
- Roselle, L., Miskimmon, A., & O'Loughlin, B. (2014). Strategic narrative: A new means to
  understand soft power. *Media, War & Conflict*, 7(1).
- Miskimmon, A., & O'Loughlin, B. (2025). Strategic narrative: its origins and evolution, its
  connection to public diplomacy, and some future paths. *Place Branding and Public Diplomacy.*
- Lerner, A. B., Miskimmon, A., & O'Loughlin, B. (2025). Thinking outside the box: From frames to
  strategic ontologies in the analysis of media, war, and conflict. *Media, War & Conflict.*
- Hall, S. (1980). Encoding/decoding. In *Culture, Media, Language.* Hutchinson.
- Entman, R. M. (1993). Framing: Toward clarification of a fractured paradigm. *Journal of
  Communication*, 43(4).
- Papacharissi, Z. (2015). *Affective Publics: Sentiment, Technology, and Politics.* Oxford
  University Press.
- Boyacı Yıldırım, M. (2026). Kamuoyunun Dijital Tanıklığı: Uluslararası Haberlerde Gazze Üzerine
  Kullanıcı Söylemlerinin Duygu ve Konu Temelli Analizi. *TRT Akademi*, 11(26), 374–411.
  https://doi.org/10.37679/trta.1829435
- Krippendorff, K. (2004). *Content Analysis: An Introduction to Its Methodology.* Sage.
- İletişim ve Diplomasi Dergisi — Author Guidelines. https://dergipark.org.tr/en/pub/iletisimvediplomasi/writing-rules
- İletişim ve Diplomasi Dergisi — Journal homepage / submission dates.
  https://dergipark.org.tr/tr/pub/iletisimvediplomasi
- "Gaza Board of Peace announces Hamas disarmament agreement: What we know." Al Jazeera, 31 July
  2026. https://www.aljazeera.com/news/2026/7/31/gaza-board-of-peace-announces-hamas-disarmament-agreement-what-we-know
- "Israel violates Lebanese airspace, kills over two dozen in Gaza in weekend strikes." UN News,
  2 August 2026. https://news.un.org/en/story/2026/08/1168067
