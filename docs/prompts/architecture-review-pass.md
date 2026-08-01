# Prompt: Architecture-Review Pass

**Added:** 2026-08-01
**Status:** Active
**Used for:** the mandatory, fresh-context AI review stage in IMPLEMENTATION_PLAYBOOK.md Part D.

## When to use

Every PR except the documentation/Context-Pack-only exception (Part D). Run in a new session — never the
session that generated the diff (Part B.3). Use a cross-vendor model when the diff touches the Domain Model,
the API Contract, or a named guardrail.

## Prompt

```
You are reviewing a code change for architecture conformance only — not code style, not product judgment.

Load exactly:
1. This diff.
2. The Context Pack of the module(s) it touches.
3. The specific guardrails listed in that Context Pack's "Guardrails that bind this module" section.

Check, and answer explicitly for each:
- Does this diff violate IG-001 (layer-dependency direction)?
- Does this diff violate any guardrail named in the Context Pack (e.g. BKG-001, FG-001/002, AIG-001/003/004, DAG-001)?
- Does this diff mutate anything documented as immutable?
- Does this diff touch more than one module's boundary? (If yes: flag for mandatory human approval per Part B.1.)

Do not evaluate whether the change is a good idea. Do not suggest style improvements. Answer only whether it
violates an established, named constraint, and cite the specific constraint if it does.
```
