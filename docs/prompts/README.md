# Versioned Prompts

Standing, reusable prompts only — the ones used repeatedly. One-off, single-use messages are not saved here.
This exists for the same reason AIG-003 requires the *product's* AI prompts to be versioned and provenance-tracked
(PRODUCT_ARCHITECTURE.md §11.4): it would be inconsistent to demand that discipline of the product while treating
the prompts that build the product as disposable chat text. Full policy: IMPLEMENTATION_PLAYBOOK.md Part B.7.

Rules: a prompt is added here only once it has actually been used more than once, not speculatively. A prompt is
never edited in place once in use — a change is a new dated entry, the old one marked superseded, matching the ADR
convention in `docs/adr/`.

## Index

- `architecture-review-pass.md` — the fresh-context prompt used for every mandatory AI architecture-review pass (IMPLEMENTATION_PLAYBOOK.md Part D)
