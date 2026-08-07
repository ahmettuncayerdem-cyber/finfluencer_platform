<!--
Full explanation of every item below lives in IMPLEMENTATION_PLAYBOOK.md, Part D.
This checklist is the terse, at-the-point-of-use copy — if you change the meaning
of an item here, update Part D in the same PR, and vice versa.
-->

## What does this PR do, in one sentence?



## Which module / Context Pack does this touch?



## Definition of Ready (confirm before requesting review)

- [ ] Relevant Domain entities/invariants already exist, or their addition is this PR's first step
- [ ] Relevant API Contract slice exists or is authored here
- [ ] Context Pack exists for the touched module, or is created in this PR
- [ ] This PR maps to one architectural layer's responsibility, not several
- [ ] Any wrapped existing-engine code has its integration decision (reuse / wrap / adapt / rewrite) recorded, with a reason
- [ ] Acceptance criteria are expressed as tests

## Definition of Done (confirm before merge)

- [ ] CI green: type-check, lint, IG-001 layer-direction rule, unit + integration tests
- [ ] No plaintext secret, credential, or PII anywhere in the diff
- [ ] Tenant-scoped queries are actually scoped
- [ ] Long-running/job-handling code is idempotent and checkpoint-resumable
- [ ] No immutable entity (per PRODUCT_ARCHITECTURE.md §10.1) is mutated in place
- [ ] AI architecture-review pass completed, fresh context, no unresolved guardrail flag
      (cross-vendor reviewer used if this touches Domain Model, API Contract, or a named guardrail)
- [ ] Human review completed
- [ ] Context Pack updated in this same PR

## Exception claimed?

- [ ] This PR touches only comments / documentation / a Context Pack — AI architecture-review stage skipped per Part D's carve-out (CI + human approval still required)
