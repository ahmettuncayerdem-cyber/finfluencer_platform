"""
finfluencer.core — Cross-cutting infrastructure.

Modules
-------
    config           : Pydantic-validated YAML settings loader
    logging          : structured JSON logging (structlog)
    checkpoint       : three-tier checkpoint manager
    reproducibility  : seed derivation, provenance, environment snapshots
    contracts        : inter-module Pydantic schemas
    exceptions       : platform-wide exception hierarchy  (this file's sibling)
    registry         : plugin discovery
    budgets          : memory and quota budgets

Import order dependency (topologically sorted):
    exceptions  →  contracts  →  config  →  logging  →  reproducibility
                                                 →  checkpoint
                                                 →  registry
                                                 →  budgets

Modules further down in the graph may import from those above, never the
reverse. Violating this ordering will produce circular import errors.
"""
