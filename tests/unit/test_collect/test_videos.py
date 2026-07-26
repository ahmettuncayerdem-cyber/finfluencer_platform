"""Tests for finfluencer.collect.videos._month_stratified_sample (Commit 1.3).

These tests EXIST TO GUARD the two diagnostic ``_log.warning(...)`` calls
added around the existing month-stratified systematic-sampling algorithm:

1. ``month_stratified_sample_index_collision`` — logged when the systematic
   sampling positions for a single month collapse onto fewer than ``k``
   distinct indices.
2. ``month_stratified_sample_quota_mismatch`` — logged when the total
   number of selected videos across all months does not equal ``target_n``.

IMPORTANT ANALYTICAL NOTE (read before trusting these tests blindly):

The two conditions are NOT equally reachable via realistic inputs.

* The "quota_mismatch" condition IS naturally reachable — a highly
  skewed month distribution (many months with exactly 1 video plus one
  month with most of the videos) causes the per-month quota
  rounding/redistribution logic (unchanged by this commit, lines 85-105
  of the module) to converge to a quota SUM that differs from
  ``target_n``. This is exercised in ``TestQuotaMismatchLogging`` with
  concrete, empirically-verified numbers. In every configuration swept
  (7500 synthetic trials across a range of skew levels and corpus
  sizes), this condition only ever fired in the OVER-delivery direction
  (``actual_n`` greater than ``target_n``) or not at all -- never
  under-delivery. That asymmetry is why the event is named
  "quota_mismatch" rather than "under_delivered": the mismatch can go
  either way in principle, and in practice only goes one way today.

* The "index_collision" condition, by contrast, was swept exhaustively
  (n up to 200, k up to n, 200 seeds per combination, plus the exact
  floating-point boundary case ``start == step``) and NO combination
  produced a collision. A short proof sketch: whenever this branch runs,
  k < n is guaranteed by the caller, so step = n/k is STRICTLY > 1;
  for a strictly-increasing arithmetic sequence with common difference
  > 1, floor() of consecutive terms is always strictly increasing too
  (frac(pos_i) + step > 1 unconditionally since frac >= 0 and step > 1),
  so no two floored positions can coincide, and the final ``min(...,
  n-1)`` clamp is mathematically provably never needed either (the last
  raw position is always < n). Reaching this branch would require
  float64 precision loss making a computed ``n/k`` round down to
  exactly 1.0, which needs k on the order of 2**52 -- not a realistic
  video count for this platform.

  Consequently, ``TestIndexCollisionLogging`` below exercises this
  branch by monkeypatching ``numpy.random.default_rng`` to return a
  value OUTSIDE the real ``rng.uniform(0, step)`` contract. This proves
  the logging guard itself is correct IF that branch is ever reached
  (e.g. by a future refactor that changes the sampling formula), but it
  does NOT demonstrate that the branch is reachable today via genuine
  randomness. This distinction is deliberate and should not be
  papered over.
"""

from __future__ import annotations

from typing import Any

import structlog

from finfluencer.collect import videos as videos_mod
from finfluencer.collect.videos import _month_stratified_sample
from finfluencer.core.contracts import VideoRecord


# ============================================================================
# Shared helpers
# ============================================================================


def _vr(video_id: str, month: str, day: str = "15") -> VideoRecord:
    """Minimal valid VideoRecord for a given ``YYYY-MM`` month bucket."""
    return VideoRecord(
        analyst_key="satiroglu",
        video_id=video_id,
        published_at=f"{month}-{day}T00:00:00Z",
        title="t",
        duration_sec=100,
        views=1,
        comment_count=0,
    )


def _assert_no_duplicates(records: list[VideoRecord]) -> None:
    ids = [v.video_id for v in records]
    assert len(ids) == len(set(ids)), f"duplicate video_ids in result: {ids}"


# ============================================================================
# Normal path: no skew, no logging expected
# ============================================================================


class TestNoLoggingOnNormalPath:
    def test_single_month_no_warnings(self):
        """A single-month pool can never hit either warning: quotas trivially
        sum to target_n (one month, no redistribution needed), and the
        collision branch is structurally unreachable (see module docstring)."""
        videos = [_vr(f"v{i}", "2025-03", day=f"{(i % 27) + 1:02d}") for i in range(10)]

        with structlog.testing.capture_logs() as captured:
            result = _month_stratified_sample(videos, target_n=5, seed=7)

        assert len(result) == 5
        assert captured == []
        _assert_no_duplicates(result)

    def test_moderately_skewed_months_no_warnings(self):
        """Three months with unequal but non-extreme sizes (20/15/10) still
        converge quotas to exactly target_n in one redistribution pass --
        this is the realistic, common case for this platform's actual
        analyst upload cadences."""
        videos: list[VideoRecord] = []
        videos += [_vr(f"jan{i}", "2025-01", day=f"{(i % 27) + 1:02d}") for i in range(20)]
        videos += [_vr(f"feb{i}", "2025-02", day=f"{(i % 27) + 1:02d}") for i in range(15)]
        videos += [_vr(f"mar{i}", "2025-03", day=f"{(i % 27) + 1:02d}") for i in range(10)]

        with structlog.testing.capture_logs() as captured:
            result = _month_stratified_sample(videos, target_n=20, seed=7)

        assert len(result) == 20
        assert captured == []
        _assert_no_duplicates(result)


# ============================================================================
# Under-capacity: sampling not entered at all
# ============================================================================


class TestUnderCapacityEarlyReturn:
    def test_fewer_videos_than_target_returns_all_unchanged_no_logging(self):
        """len(videos) <= target_n takes the early-return branch (line 77-78,
        untouched by this commit) -- no RNG use, no quota logic, no
        possibility of either warning firing."""
        videos = [_vr(f"v{i}", "2025-01") for i in range(3)]

        with structlog.testing.capture_logs() as captured:
            result = _month_stratified_sample(videos, target_n=10, seed=1)

        assert result == videos
        assert captured == []


# ============================================================================
# Quota-sum mismatch (asymmetric in practice: only ever over-delivers)
# ============================================================================


class TestQuotaMismatchLogging:
    def test_skewed_months_trigger_mismatch_warning(self):
        """9 months with exactly 1 video each, plus 1 month with 100 videos,
        target_n=10. The per-month quota floor (``max(1, round(...))``)
        forces each of the 9 tiny months to quota=1 (9 total), and the
        single-pass residual-redistribution loop (lines 93-105, NOT
        modified by this commit) only ever adjusts ONE month per pass --
        it cannot fully claw back the resulting excess in one iteration.
        Verified concrete numbers: quotas sum to 17, not 10, so the
        actual delivered count is 17 -- MORE than target_n. This is a
        pre-existing quota-convergence limitation this commit does not
        fix; it only makes it observable."""
        videos: list[VideoRecord] = []
        for i in range(9):
            videos.append(_vr(f"tiny{i}", f"2025-{i + 1:02d}"))
        for j in range(100):
            videos.append(_vr(f"big{j}", "2025-10"))

        with structlog.testing.capture_logs() as captured:
            result = _month_stratified_sample(videos, target_n=10, seed=123)

        assert len(result) == 17
        warnings = [c for c in captured if c["event"] == "month_stratified_sample_quota_mismatch"]
        assert len(warnings) == 1
        assert warnings[0]["target_n"] == 10
        assert warnings[0]["actual_n"] == 17
        assert warnings[0]["log_level"] == "warning"
        _assert_no_duplicates(result)

    def test_no_mismatch_warning_when_quotas_converge(self):
        """Regression guard for the positive case: the balanced-months
        scenario from TestNoLoggingOnNormalPath must NOT emit this event
        (already covered by ``captured == []`` there; restated narrowly
        here against just this specific event name for clarity)."""
        videos: list[VideoRecord] = []
        videos += [_vr(f"jan{i}", "2025-01", day=f"{(i % 27) + 1:02d}") for i in range(20)]
        videos += [_vr(f"feb{i}", "2025-02", day=f"{(i % 27) + 1:02d}") for i in range(15)]
        videos += [_vr(f"mar{i}", "2025-03", day=f"{(i % 27) + 1:02d}") for i in range(10)]

        with structlog.testing.capture_logs() as captured:
            _month_stratified_sample(videos, target_n=20, seed=7)

        mismatch_events = [c for c in captured if c["event"] == "month_stratified_sample_quota_mismatch"]
        assert mismatch_events == []


# ============================================================================
# Index collision (structurally unreachable via real RNG -- see module
# docstring). Exercised via a monkeypatched RNG that returns an
# out-of-contract value, to prove the guard itself behaves correctly.
# ============================================================================


class _OutOfContractRng:
    """Stub RNG whose .uniform() deliberately violates the real
    ``[low, high)`` contract, to force the defensive clamp-collision
    branch that real ``numpy.random.Generator.uniform`` output cannot
    reach for any realistic (n, k) in this codebase (see module
    docstring for the proof)."""

    def uniform(self, low: float, high: float) -> float:
        return high * 2.0


class TestIndexCollisionLogging:
    def test_out_of_contract_rng_triggers_collision_warning(self, monkeypatch: Any):
        monkeypatch.setattr(
            videos_mod.np.random, "default_rng", lambda seed: _OutOfContractRng(),
        )
        # Single month, 3 videos, quota 2 -- with a well-behaved RNG this
        # would deterministically produce 2 distinct indices (see
        # TestNoLoggingOnNormalPath); the stub RNG forces a collapse to 1.
        videos = [_vr(f"v{i}", "2025-01", day=f"{10 + i:02d}") for i in range(3)]

        with structlog.testing.capture_logs() as captured:
            result = _month_stratified_sample(videos, target_n=2, seed=999)

        collision_events = [c for c in captured if c["event"] == "month_stratified_sample_index_collision"]
        assert len(collision_events) == 1
        assert collision_events[0]["month"] == "2025-01"
        assert collision_events[0]["requested"] == 2
        assert collision_events[0]["got"] == 1
        assert collision_events[0]["log_level"] == "warning"

        # The collision cascades into an overall quota mismatch too (1
        # selected vs. target_n=2) -- both warnings are expected together.
        mismatch_events = [c for c in captured if c["event"] == "month_stratified_sample_quota_mismatch"]
        assert len(mismatch_events) == 1
        assert mismatch_events[0]["target_n"] == 2
        assert mismatch_events[0]["actual_n"] == 1

        assert len(result) == 1
        _assert_no_duplicates(result)


# ============================================================================
# Determinism / reproducibility contract (Methods §3.2.3)
# ============================================================================


class TestDeterminism:
    def test_same_seed_same_input_yields_identical_output(self):
        """Reproducibility contract: the exact same (videos, target_n, seed)
        must yield an identical, order-preserving result every time --
        this commit must not have disturbed that (it only adds logging
        around the existing algorithm, never touches the RNG draw order
        or the selection formula itself)."""
        videos: list[VideoRecord] = []
        videos += [_vr(f"jan{i}", "2025-01", day=f"{(i % 27) + 1:02d}") for i in range(20)]
        videos += [_vr(f"feb{i}", "2025-02", day=f"{(i % 27) + 1:02d}") for i in range(15)]
        videos += [_vr(f"mar{i}", "2025-03", day=f"{(i % 27) + 1:02d}") for i in range(10)]

        result_a = _month_stratified_sample(videos, target_n=20, seed=7)
        result_b = _month_stratified_sample(videos, target_n=20, seed=7)

        assert [v.video_id for v in result_a] == [v.video_id for v in result_b]

    def test_different_seed_can_yield_different_output(self):
        """Sanity check on the other direction: a different seed is not
        REQUIRED to differ (astronomically unlikely to coincide, but not
        a hard guarantee), so this asserts the empirically-observed
        outcome for this fixed scenario rather than a general law."""
        videos: list[VideoRecord] = []
        videos += [_vr(f"jan{i}", "2025-01", day=f"{(i % 27) + 1:02d}") for i in range(20)]
        videos += [_vr(f"feb{i}", "2025-02", day=f"{(i % 27) + 1:02d}") for i in range(15)]
        videos += [_vr(f"mar{i}", "2025-03", day=f"{(i % 27) + 1:02d}") for i in range(10)]

        result_a = _month_stratified_sample(videos, target_n=20, seed=7)
        result_c = _month_stratified_sample(videos, target_n=20, seed=8)

        assert [v.video_id for v in result_a] != [v.video_id for v in result_c]
