# Graphical Abstract — Design Specification
### Message versus Messenger Effects on Investor Sentiment: Evidence from Turkish Financial YouTube Comments

Delivered files: `Graphical_Abstract.svg` (vector, edit in Illustrator/Inkscape), `Graphical_Abstract.png` (2400×1080px, ~469 dpi at 13cm width), `Graphical_Abstract_highres.png` (4800×2160px). All built as clean vector shapes with real text (no AI-generated raster text), so every label is crisp and editable at any size — this is why it was produced directly as SVG rather than through Midjourney/DALL-E (see note at the end on why that matters for a data-accurate scientific figure).

Canvas: 2400×1080px (aspect ratio ≈ 2.22:1). Elsevier's minimum graphical-abstract spec is 531×1328px (h×w, ≈1:2.5); this design sits close to that ratio and exceeds the minimum resolution several times over. The paper title is intentionally *not* rendered inside the image, per Elsevier's own graphical-abstract guidance (the journal adds title/caption separately).

---

## 1. Layout overview (top to bottom, in four bands)

**Band 1 — Data & NLP pipeline (y: 0–29% of canvas height), three cards left to right:**
1. *Turkish Financial YouTube Ecosystem* — play-button icon, four analyst avatars (Tunç Şatıroğlu, Atilla Yeşilada, Mert Başaran, Selçuk Geçer; Şatıroğlu's avatar carries a thin gold ring, foreshadowing the headline finding), corpus stat line "955 Videos → 17,566 Comments."
2. *BERTopic Topic Modeling* — cluster icon, headline stat "128 topics," one-line method note.
3. *BERT Sentiment Classification* — split-circle sentiment icon, headline stat "Positive vs. Negative," validation note (Cohen's κ = 0.947).
Cards connected by right-pointing chevron arrows in accent blue.

**Band 2 — Message vs. Messenger core visual (y: 30–70%), the dominant center of the figure:**
A balance-scale icon anchored on a central pedestal. A small pill above the scale reads "INVESTOR SENTIMENT" — what the two sides are jointly weighed against.
- **Left pan = MESSAGE**: bold blue label, subtitle "(financial topics, content, economic issues)," newspaper + bar-chart icons, two theory pills below (*Investor Sentiment Theory*, *Limited Attention Theory*).
- **Right pan = MESSENGER**: bold slate label, subtitle "(credibility, opinion leadership, parasocial interaction)," megaphone + shield/trust icons, four theory pills in a 2×2 grid (*Source Credibility*, *Two-Step Flow Theory*, *Opinion Leadership*, *Parasocial Interaction*).
- A gold-accented callout card to the right of the scale singles out **Tunç Şatıroğlu** as the strongest, most persistent messenger effect — visually tying back to his highlighted avatar in Band 1.
- Directly below the scale, a compact two-bar chart gives the quantitative version of the same comparison: Topic (Message) R²=24.4% vs. Analyst (Messenger) R²=5.4%, with a footnote stating the full joint model R²=25.9% and that ~74% of variance remains unexplained — included deliberately for scientific honesty rather than overstating explanatory power.

**Band 3 — Key findings strip (y: 71–86%):** five compact icon+text cards, evenly spaced:
1. Topic explains substantially more variance than communicator identity.
2. Communicator identity remains significant net of topic composition.
3. (gold-accented) Şatıroğlu shows the strongest, most persistent messenger effect.
4. No contemporaneous link between sentiment and BIST100 returns.
5. Sentiment Granger-predicts short-term BIST100 returns.

**Band 4 — Closing statement banner (y: 87–100%):** full-width navy bar, centered white bold text:
> "Investor sentiment in digital financial ecosystems is jointly shaped by message content and communicator identity."

---

## 2. Exact figure text (verbatim, as it appears)

- Card headings: "Turkish Financial YouTube Ecosystem" / "BERTopic Topic Modeling" / "BERT Sentiment Classification"
- Analyst names: "Tunç Şatıroğlu," "Atilla Yeşilada," "Mert Başaran," "Selçuk Geçer"
- Stats: "955 Videos," "17,566 Comments," "128 topics identified across the pooled corpus," "Positive vs. Negative comment-level polarity," "Transformer-based, validated against human coding (Cohen's κ = 0.947)"
- Core comparison: "Variance Decomposition — Message vs. Messenger," "INVESTOR SENTIMENT," "MESSAGE (financial topics, content, economic issues)," "MESSENGER (credibility, opinion leadership, parasocial interaction)"
- Theory pills: "Investor Sentiment Theory," "Limited Attention Theory," "Source Credibility," "Two-Step Flow Theory," "Opinion Leadership," "Parasocial Interaction"
- Şatıroğlu callout: "Tunç Şatıroğlu — Strongest and most persistent messenger effect, robust across all estimation methods"
- Bar chart: "Variance Explained in Comment-Level Sentiment," "Topic (Message) 24.4%," "Analyst (Messenger) 5.4%," footnote "Full joint model R² = 25.9%; topic and analyst identity together leave ~74% of variance unexplained."
- Findings strip (verbatim, five items): as listed in Band 3 above.
- Bottom banner: "Investor sentiment in digital financial ecosystems is jointly shaped by message content and communicator identity."

## 3. Icon list

| Element | Icon |
|---|---|
| YouTube ecosystem | Rounded play-button glyph |
| Four analysts | Simple person-silhouette avatars (Şatıroğlu's ringed in gold) |
| Videos | Filmstrip icon |
| Comments | Speech-bubble icon |
| BERTopic | Three overlapping clustered circles |
| BERT Sentiment | Circle split into filled (+) / outline (–) halves |
| MESSAGE pan | Newspaper icon + ascending bar-chart icon |
| MESSENGER pan | Megaphone icon + shield/checkmark "trust" icon |
| Balance scale | Classic pivot-beam-and-pans glyph, level (not tilted — the numeric R² values carry the "which side is heavier" information precisely, rather than an imprecise tilt angle) |
| Theory pills | Small open-book glyph, repeated on all six pills |
| Şatıroğlu finding | Gold star |
| "Communicator remains significant" | Circled checkmark |
| "No contemporaneous link" | Two flat overlapping wave lines |
| "Granger-predicts" | Forward-curving arrow |

## 4. Color palette (Elsevier-compatible, blue/grey finance palette)

- Background: white `#FFFFFF`
- Navy (headers, banner): `#1B3A5C`
- Primary blue (MESSAGE side, pipeline accents): `#2E6F95`
- Light blue (secondary accents, arrows): `#4FA8C9`
- Slate (MESSENGER side): `#5B6B84`
- Grey (body/subtext): `#6B7280` / `#374151`
- Card backgrounds: `#F7F8FA`, borders `#E2E5EA`
- Single accent color (used only for the Şatıroğlu finding, sparingly, as is conventional in Elsevier/Cell Press graphical abstracts to draw the eye to one headline result): gold `#D9A441`

No gradients, no drop shadows, no photographic or 3D elements — flat, minimal, print-safe vector shapes throughout.

---

## 5. Note on Midjourney / DALL-E and why this was built as vector SVG instead

You asked for an image-generation prompt for Midjourney/DALL-E as a deliverable, so it's below. But it comes with an honest caveat, in the interest of scientific accuracy rather than just aesthetics: diffusion image generators do not render precise text, exact statistics, or consistent multi-element scientific layouts reliably — they routinely garble numbers (e.g. "24.4%" might come out as "244%" or illegible), misspell labels, and can't guarantee the six theory names, four analyst names, or five findings all appear correctly and legibly. For a journal figure that has to carry exact figures (R²=24.4%, κ=0.947, four named analysts, six named theories), that failure mode is disqualifying. This is why the actual deliverable was hand-built as a precise vector SVG instead, where every number and label is exact and editable.

If you still want to use Midjourney/DALL-E — for example, to generate a decorative background texture, an alternative icon style, or a fully illustrative (non-textual) version — here is a prompt tuned for that purpose:

> Minimalist scientific graphical abstract in Elsevier journal style, flat vector illustration, white background, professional blue and grey finance color palette (navy #1B3A5C, blue #2E6F95, slate grey #5B6B84, gold accent #D9A441 used sparingly). Horizontal banner composition, aspect ratio 2.2:1. Left to right: a YouTube ecosystem icon with four small user avatars, flowing into a topic-cluster icon and a sentiment-classification icon, converging into a large centered balance scale icon labeled MESSAGE on the left pan (newspaper and bar-chart icons) and MESSENGER on the right pan (megaphone and trust-shield icons), six small book-icon badges beneath representing communication and behavioral-finance theories, a small stock-chart icon to the right suggesting market data. Clean sans-serif typography, no gradients, no 3D effects, no photographic elements, no clutter, ample white space, flat icon style consistent with Cell Press or Journal of Business Research graphical abstracts. Do not render precise numeric data or fine print in the image — leave numeric labels blank or omit them entirely, as they will be added afterward in vector software.

That last instruction ("leave numeric labels blank") is the important part — treat any Midjourney/DALL-E output strictly as a decorative background or icon-style reference to trace over in vector software, never as the figure containing your actual statistics.

---

## Verification

- SVG validated as well-formed XML and renders correctly at both 2400×1080 and 4800×2160.
- All eight requirements from the brief are present: workflow pipeline, message-vs-messenger comparison (scale + bar chart, two of the three suggested formats), all six named theories, all five findings, the exact closing sentence, Elsevier-compatible flat blue/grey styling, and full layout/text/icon documentation plus an image-generation prompt.
