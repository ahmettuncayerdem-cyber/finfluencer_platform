"""
finfluencer.collect — Phase 2 data-collection stages.

Each module in this subpackage orchestrates one collection stage,
consuming a PlatformProvider (via registry) and producing typed
Parquet frames under data/raw/.

Import order:
    quota → channels → videos → comments → transcripts → market_series

Every stage is checkpointed via CheckpointManager (Tier-1 JSONL append
per record, Tier-2 .done marker with config-slice hash).
"""
