"""Final integrity/health report for the basaran recovery run.

Stabilization note: this script previously reported an empty
topic_evolution.parquet as "topic_evolution_rows": 0 with no indication
of whether that meant "healthy, nothing generated yet" or "corrupted,
regenerate immediately" - a health report that can't distinguish those
two states isn't doing its job. Every required input is now validated
non-empty immediately after loading, so a missing or unexpectedly empty
file stops the report with a clear error instead of being silently
folded into the JSON output as an unremarkable zero.
"""
import json
import pandas as pd

from finfluencer.core.exceptions import CorpusValidationError


def _require_nonempty(df: pd.DataFrame, name: str) -> None:
    """Fail loudly if a required input is missing or empty."""
    if df is None or df.empty:
        raise CorpusValidationError(
            f"Required input '{name}' is empty or missing - refusing to "
            f"report on it as if it were a normal, healthy zero. "
            f"Regenerate this file before rerunning final_health_report.py.",
            input_name=name,
            row_count=0 if df is None else len(df),
        )


ch = pd.read_parquet("data/raw/channels.parquet")
_require_nonempty(ch, "data/raw/channels.parquet")
vd = pd.read_parquet("data/raw/videos.parquet")
_require_nonempty(vd, "data/raw/videos.parquet")
cm = pd.read_parquet("data/raw/comments.parquet")
_require_nonempty(cm, "data/raw/comments.parquet")
tp = pd.read_parquet("data/processed/topics.parquet")
_require_nonempty(tp, "data/processed/topics.parquet")
sm = pd.read_parquet("data/processed/sentiment.parquet")
_require_nonempty(sm, "data/processed/sentiment.parquet")
ts = pd.read_parquet("data/processed/topic_sentiment.parquet")
_require_nonempty(ts, "data/processed/topic_sentiment.parquet")
te = pd.read_parquet("data/processed/topic_evolution.parquet")
_require_nonempty(te, "data/processed/topic_evolution.parquet")
em = pd.read_parquet("data/processed/embeddings_index.parquet")
_require_nonempty(em, "data/processed/embeddings_index.parquet")

analysts = sorted(vd["analyst_key"].unique())

report = {}
report["channel_per_analyst"] = ch.set_index("analyst_key")["channel_id"].to_dict()
report["video_per_analyst"] = vd["analyst_key"].value_counts().to_dict()
report["comment_per_analyst"] = cm["analyst_key"].value_counts().to_dict()
report["unique_comment_per_analyst"] = cm.groupby("analyst_key")["comment_id"].nunique().to_dict()

report["dup_comment_id_global"] = int((cm["comment_id"].value_counts() > 1).sum())
report["dup_video_id_global"] = int((vd["video_id"].value_counts() > 1).sum())
report["dup_comment_id_embeddings"] = int((em["comment_id"].value_counts() > 1).sum())
report["dup_comment_id_sentiment"] = int((sm["comment_id"].value_counts() > 1).sum())
report["dup_comment_id_topics"] = int((tp["comment_id"].value_counts() > 1).sum())

video_overlap = {}
comment_overlap = {}
for a in analysts:
    va = set(vd.loc[vd["analyst_key"] == a, "video_id"])
    ca = set(cm.loc[cm["analyst_key"] == a, "comment_id"])
    video_overlap[a] = {b: len(va & set(vd.loc[vd["analyst_key"] == b, "video_id"])) for b in analysts}
    comment_overlap[a] = {b: len(ca & set(cm.loc[cm["analyst_key"] == b, "comment_id"])) for b in analysts}
report["video_overlap_matrix"] = video_overlap
report["comment_overlap_matrix"] = comment_overlap

report["pooled_corpus_size"] = int((tp["configuration"] == "pooled").sum())
report["topic_counts"] = {
    cfg: int(tp.loc[tp["configuration"] == cfg, "topic_id"].nunique())
    for cfg in tp["configuration"].unique()
}
report["sentiment_class_counts"] = (
    sm["sentiment_class"].value_counts().to_dict() if "sentiment_class" in sm.columns else "kolon yok"
)
report["topic_sentiment_rows"] = len(ts)
report["topic_evolution_rows"] = len(te)

print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
