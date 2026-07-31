"""Publication grounding data pull. Run from repo root with venv active:
    python pub_data_pull.py > pub_data.json

Stabilization note: this script writes values directly into publication-
grounding data. It previously failed silently on an empty
topic_evolution.parquet - time_bin_min/max would resolve to the string
"nan" instead of raising, because pandas .min()/.max() on an empty column
return NaN rather than erroring. Every required input is now validated
non-empty immediately after loading, so a missing or corrupted upstream
file stops this script with a clear error instead of producing quietly
wrong numbers in pub_data.json.
"""
import json
import pandas as pd

from finfluencer.core.exceptions import CorpusValidationError


def _require_nonempty(df: pd.DataFrame, name: str) -> None:
    """Fail loudly if a required input is missing or empty.

    Without this check, an empty upstream file (e.g. a corrupted or
    not-yet-regenerated topic_evolution.parquet) silently propagates as
    NaN/empty results through downstream computations - a scalar like
    ``str(pd.Series([]).min())`` becomes the literal string ``"nan"``
    with no exception raised. This is exactly what happened to
    ``time_bin_min``/``time_bin_max`` before this check existed.
    """
    if df is None or df.empty:
        raise CorpusValidationError(
            f"Required input '{name}' is empty or missing - refusing to "
            f"produce publication-grounding data from it. Regenerate this "
            f"file before rerunning pub_data_pull.py.",
            input_name=name,
            row_count=0 if df is None else len(df),
        )


cm = pd.read_parquet("data/raw/comments.parquet")
_require_nonempty(cm, "data/raw/comments.parquet")
vd = pd.read_parquet("data/raw/videos.parquet")
_require_nonempty(vd, "data/raw/videos.parquet")
tp = pd.read_parquet("data/processed/topics.parquet")
_require_nonempty(tp, "data/processed/topics.parquet")
sm = pd.read_parquet("data/processed/sentiment.parquet")
_require_nonempty(sm, "data/processed/sentiment.parquet")
ts = pd.read_parquet("data/processed/topic_sentiment.parquet")
_require_nonempty(ts, "data/processed/topic_sentiment.parquet")
te = pd.read_parquet("data/processed/topic_evolution.parquet")
_require_nonempty(te, "data/processed/topic_evolution.parquet")

out = {}

out["sentiment_file_ok"] = True
out["sentiment_rows"] = len(sm)
out["sentiment_dup_comment_id"] = int((sm["comment_id"].value_counts() > 1).sum())

out["comments_posted_date_min"] = str(cm["posted_date"].min())
out["comments_posted_date_max"] = str(cm["posted_date"].max())
out["videos_published_at_min"] = str(vd["published_at"].min())
out["videos_published_at_max"] = str(vd["published_at"].max())

pooled = ts[ts["configuration"] == "pooled"].sort_values("n_comments", ascending=False)
_require_nonempty(pooled, "topic_sentiment.parquet[configuration=='pooled']")
out["pooled_top15"] = pooled[["topic_id", "topic_label", "n_comments", "positive_ratio", "mean_sentiment_prob"]].head(15).to_dict("records")

big = pooled[pooled["n_comments"] >= 50]
out["most_positive_5"] = big.sort_values("positive_ratio", ascending=False)[["topic_label", "n_comments", "positive_ratio"]].head(5).to_dict("records")
out["most_negative_5"] = big.sort_values("positive_ratio")[["topic_label", "n_comments", "positive_ratio"]].head(5).to_dict("records")

merged = cm[["comment_id", "analyst_key"]].merge(sm[["comment_id", "sentiment_class", "sentiment_prob"]], on="comment_id")
tab = merged.groupby(["analyst_key", "sentiment_class"]).size().unstack(fill_value=0)
tab["pos_ratio"] = tab.get("positive", 0) / tab.sum(axis=1)
out["sentiment_by_analyst"] = tab.reset_index().to_dict("records")

wa = tp[tp["configuration"] == "within_analyst"].merge(cm[["comment_id", "analyst_key"]], on="comment_id")
out["within_analyst_topic_counts"] = wa.groupby("analyst_key")["topic_id"].nunique().to_dict()

out["time_bin_count_pooled"] = int(te[te["configuration"] == "pooled"]["time_bin"].nunique())
out["time_bin_min"] = str(te["time_bin"].min())
out["time_bin_max"] = str(te["time_bin"].max())

out["outlier_topic_ratio_pooled"] = float(pooled.loc[pooled["topic_id"] == -1, "n_comments"].sum() / pooled["n_comments"].sum())

out["n_video_total"] = int(vd.shape[0])
out["n_comment_total"] = int(cm.shape[0])

print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
