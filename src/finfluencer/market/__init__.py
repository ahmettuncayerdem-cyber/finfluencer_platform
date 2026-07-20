"""
finfluencer.market
====================

Market-integration extension — a completely independent downstream
stage (see `outputs/manuscript/finfluencer_tr_2025_market_integration_design.docx`).

This package never imports from or writes to the existing NLP pipeline
modules (`finfluencer.collect`, `finfluencer.preprocess`,
`finfluencer.sentiment`, `finfluencer.topics`, `finfluencer.embeddings`,
`finfluencer.analysis`). It reads their Parquet outputs (e.g.
`comments.parquet`, `sentiment.parquet`) as frozen, read-only inputs
and writes new artefacts under `data/market/` and
`data/processed/market_sentiment/` only.
"""
