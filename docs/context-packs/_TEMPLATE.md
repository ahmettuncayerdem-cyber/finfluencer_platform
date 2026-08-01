# Context Pack — <module name>

Copy this file into the module's own package directory as `CONTEXT_PACK.md`.
Update it in the same PR as any change that alters this module's shape — never as a follow-up task.
Full workflow: IMPLEMENTATION_PLAYBOOK.md Part B.2.

## Purpose

One paragraph: what this module does and why it exists.

## Domain entities and invariants owned or touched

Point at the actual types (file + symbol), don't restate PRODUCT_ARCHITECTURE.md §10.1 in prose.

## API Contract operations implemented

Point at the actual schema operations this module implements.

## Guardrails that bind this module

Only the subset that actually applies here — not the full AIG/BKG/FG/DAG/IG list.

## Integration decisions (existing-engine code, if any)

For each piece of wrapped/adapted/rewritten legacy code: what it was, what classification was assigned
(production ready / wrapper required / adaptation required / rewrite required — see IMPLEMENTATION_ROADMAP.md §3),
and why.

## Known technical debt

Deliberate shortcuts only, each with a reason and, where possible, a revisit trigger. Not a TODO list.

## Gotchas

Anything a fresh AI session would otherwise get wrong about this module specifically.
