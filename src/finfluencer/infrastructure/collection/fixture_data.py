"""Canned Collection Engine dataset (BACKLOG.md T-010).

Keyed to the real `config/analysts.yaml` roster (four Turkish financial-influencer analysts:
``satiroglu``, ``yesilada``, ``basaran``, ``gecer``) so this fixture can be driven by the same
``config/settings.yaml``/``config/analysts.yaml`` every existing test already loads via
``finfluencer.core.config.load_settings`` -- no parallel fixture Settings object is invented.
One video and two comments per analyst is enough to exercise the full four-stage pipeline
(channels -> videos -> comments -> transcripts) without needing a large corpus; volume is not
what T-010 is proving.

Publication dates fall inside `config/settings.yaml`'s observation window (2025-01-01 to
2025-12-31, section `study.observation_window`). Every video is well under the 60-second Shorts
threshold's *exclusion* boundary (durations here are all > 60s, i.e. not Shorts) and contains no
`promo_keywords` substrings, so every video is `eligible=True` -- eligibility-rule testing is
the existing engine's own test suite's job (already covered there), not re-derived here.
"""

from __future__ import annotations

from typing import Any

#: analyst_key -> the lookup string collect/channels.py actually passes to
#: `resolve_channel()` (channel_id if the roster has one, else the handle) -> canonical
#: channel_id this fixture resolves it to. Mirrors config/analysts.yaml exactly:
#: satiroglu has a real channel_id already; the other three only have a handle.
CHANNEL_LOOKUP_TO_ID: dict[str, str] = {
    "UCGBytjbMXiF1nbe6HD7iORQ": "UCGBytjbMXiF1nbe6HD7iORQ",  # satiroglu (channel_id in roster)
    "@atillayesilada": "UCFIXTURE0000000YESILADA",  # yesilada (handle only in roster)
    "@MertBasaranOfficial": "UCFIXTURE0000000BASARAN",  # basaran (handle only in roster)
    "@selcukgecer": "UCFIXTURE0000000000GECER",  # gecer (handle only in roster)
}

#: channel_id -> channel_metadata() return dict, per providers/platform/base.py's contract
#: (must include uploads_ref).
CHANNEL_METADATA: dict[str, dict[str, Any]] = {
    "UCGBytjbMXiF1nbe6HD7iORQ": {
        "channel_id": "UCGBytjbMXiF1nbe6HD7iORQ",
        "title": "Tunç Şatıroğlu",
        "description": "Fixture channel for satiroglu (T-010).",
        "published_at": "2018-01-01T00:00:00Z",
        "uploads_ref": "UUFIXTURE_SATIROGLU",
        "subscriber_count": 100_000,
        "video_count": 1,
        "view_count": 1_000_000,
    },
    "UCFIXTURE0000000YESILADA": {
        "channel_id": "UCFIXTURE0000000YESILADA",
        "title": "Atilla Yeşilada",
        "description": "Fixture channel for yesilada (T-010).",
        "published_at": "2017-01-01T00:00:00Z",
        "uploads_ref": "UUFIXTURE_YESILADA",
        "subscriber_count": 80_000,
        "video_count": 1,
        "view_count": 500_000,
    },
    "UCFIXTURE0000000BASARAN": {
        "channel_id": "UCFIXTURE0000000BASARAN",
        "title": "Mert Başaran",
        "description": "Fixture channel for basaran (T-010).",
        "published_at": "2019-01-01T00:00:00Z",
        "uploads_ref": "UUFIXTURE_BASARAN",
        "subscriber_count": 60_000,
        "video_count": 1,
        "view_count": 300_000,
    },
    "UCFIXTURE0000000000GECER": {
        "channel_id": "UCFIXTURE0000000000GECER",
        "title": "Selçuk Geçer",
        "description": "Fixture channel for gecer (T-010).",
        "published_at": "2020-01-01T00:00:00Z",
        "uploads_ref": "UUFIXTURE_GECER",
        "subscriber_count": 40_000,
        "view_count": 200_000,
        "video_count": 1,
    },
}

#: uploads_ref -> list of video IDs (newest-first), per enumerate_videos()'s contract.
UPLOADS_TO_VIDEO_IDS: dict[str, list[str]] = {
    "UUFIXTURE_SATIROGLU": ["VIDFIX_SATIROGLU_001"],
    "UUFIXTURE_YESILADA": ["VIDFIX_YESILADA_001"],
    "UUFIXTURE_BASARAN": ["VIDFIX_BASARAN_001"],
    "UUFIXTURE_GECER": ["VIDFIX_GECER_001"],
}

#: video_id -> the field dict fetch_video_metadata() turns into a VideoRecord (analyst_key and
#: selected are filled in by collect/videos.py itself, not here).
VIDEO_METADATA: dict[str, dict[str, Any]] = {
    "VIDFIX_SATIROGLU_001": {
        "video_id": "VIDFIX_SATIROGLU_001",
        "published_at": "2025-03-01T09:00:00Z",
        "title": "Piyasa Yorumu - Mart 2025",
        "description": "Günlük piyasa değerlendirmesi.",
        "duration_sec": 600,
        "views": 12_000,
        "likes": 800,
        "comment_count": 2,
        "made_for_kids": False,
        "category_id": "25",
        "eligible": True,
        "exclusion_reason": "",
    },
    "VIDFIX_YESILADA_001": {
        "video_id": "VIDFIX_YESILADA_001",
        "published_at": "2025-04-15T10:00:00Z",
        "title": "Makro Görünüm - Nisan 2025",
        "description": "Küresel ve yerel makro analiz.",
        "duration_sec": 900,
        "views": 8_000,
        "likes": 400,
        "comment_count": 2,
        "made_for_kids": False,
        "category_id": "25",
        "eligible": True,
        "exclusion_reason": "",
    },
    "VIDFIX_BASARAN_001": {
        "video_id": "VIDFIX_BASARAN_001",
        "published_at": "2025-05-20T11:00:00Z",
        "title": "Uzun Vadeli Yatırım Stratejisi",
        "description": "Portföy oluşturma prensipleri.",
        "duration_sec": 720,
        "views": 5_000,
        "likes": 250,
        "comment_count": 2,
        "made_for_kids": False,
        "category_id": "25",
        "eligible": True,
        "exclusion_reason": "",
    },
    "VIDFIX_GECER_001": {
        "video_id": "VIDFIX_GECER_001",
        "published_at": "2025-06-10T12:00:00Z",
        "title": "Hisse Senedi Seçimi",
        "description": "Değerleme ve zamanlama.",
        "duration_sec": 540,
        "views": 4_000,
        "likes": 150,
        "comment_count": 2,
        "made_for_kids": False,
        "category_id": "25",
        "eligible": True,
        "exclusion_reason": "",
    },
}

#: video_id -> list of raw comment field dicts (analyst_key/commenter_hash/text_clean/tokens/
#: n_tokens/emojis are filled in downstream -- collect_comments and preprocess own that shape;
#: fetch_top_level_comments already returns fully-shaped CommentRecords per its own contract,
#: so this fixture returns them pre-shaped, matching what a real provider would do).
COMMENTS_BY_VIDEO: dict[str, list[dict[str, Any]]] = {
    "VIDFIX_SATIROGLU_001": [
        {"comment_id": "C_SAT_1", "posted_date": "2025-03-01", "text": "Çok faydalı bir video, teşekkürler."},
        {"comment_id": "C_SAT_2", "posted_date": "2025-03-02", "text": "Bu konuda daha fazla içerik bekliyoruz."},
    ],
    "VIDFIX_YESILADA_001": [
        {"comment_id": "C_YES_1", "posted_date": "2025-04-15", "text": "Analiziniz için teşekkürler."},
        {"comment_id": "C_YES_2", "posted_date": "2025-04-16", "text": "Katılmıyorum ama ilginç bir bakış açısı."},
    ],
    "VIDFIX_BASARAN_001": [
        {"comment_id": "C_BAS_1", "posted_date": "2025-05-20", "text": "Uzun vadeli bakış açınızı seviyorum."},
        {"comment_id": "C_BAS_2", "posted_date": "2025-05-21", "text": "Portföy örneği için teşekkürler."},
    ],
    "VIDFIX_GECER_001": [
        {"comment_id": "C_GEC_1", "posted_date": "2025-06-10", "text": "Değerleme yöntemini açıklar mısınız?"},
        {"comment_id": "C_GEC_2", "posted_date": "2025-06-11", "text": "Faydalı bir özet olmuş."},
    ],
}

#: video_id -> transcript fetcher result, matching collect/transcripts.py's `_default_fetcher`
#: return shape exactly (available/text/language/reason).
TRANSCRIPTS_BY_VIDEO: dict[str, dict[str, Any]] = {
    "VIDFIX_SATIROGLU_001": {
        "available": True, "text": "Bugün piyasalarda...", "language": "tr", "reason": "",
    },
    "VIDFIX_YESILADA_001": {
        "available": True, "text": "Küresel makro görünüme baktığımızda...", "language": "tr", "reason": "",
    },
    "VIDFIX_BASARAN_001": {
        "available": True, "text": "Uzun vadeli yatırımda...", "language": "tr", "reason": "",
    },
    "VIDFIX_GECER_001": {
        "available": True, "text": "Hisse senedi seçerken...", "language": "tr", "reason": "",
    },
}
