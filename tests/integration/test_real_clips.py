"""Engine output against cadence measured from raw pixels, for every committed clip.

Each clip carries a `<clip>.groundtruth.json` naming what it asserts. Adding a clip means
adding that record and a pose fixture, not writing a test — which is what keeps the suite
from drifting into six near-identical modules as the corpus grows.

A clip earns its own module only when it has something specific to say; see
test_female_overstride_clip.py, which owns the frame-rate-independence and ground-tilt checks.

The coverage tests at the bottom exist because data-driven suites fail quietly. A mistyped
metric key, a deleted record, or a corpus that no longer spans low cadence would all leave
the suite green while testing less than it appears to.
"""

from __future__ import annotations

import json

import pytest

from tests.integration.clipcase import (
    DURATION_TOLERANCE_PCT, UNMEASURED, UNVALIDATED, analyse, check, load_clips,
)

CLIPS = load_clips()
# No module-level skip: every fixture here is a committed file, never genuinely absent, and
# a blanket skip previously hid the exact failure the coverage guards below exist to catch --
# if the whole corpus were deleted or misnamed, CLIPS == [] would skip everything, including
# test_corpus_spans_the_cadence_range_that_breaks_detection, and CI would stay green.


def _ids(clip):
    return clip.id


@pytest.fixture(scope="module", params=CLIPS, ids=_ids)
def case(request):
    return request.param, analyse(request.param)


def test_metrics_match_measured_truth(case):
    clip, actual = case
    checked = 0
    for key, expected in clip.metrics.items():
        if clip.xfail_reason(key):
            continue
        assert key in actual, f"{clip.id}: engine reports no {key!r}"
        check(clip, key, expected, actual[key])
        checked += 1
    assert checked, f"{clip.id}: asserted nothing — every metric is xfailed?"


def test_xfailed_metrics_still_fail(case):
    """An xfailed metric must still be failing, or the record is stale.

    Skipping a metric in the record removes it from test_metrics_match_measured_truth, so
    without this a fix would leave the assertion permanently switched off. This is what
    pytest's strict xfail does; data-driven cases need it spelled out.
    """
    clip, actual = case
    for key, expected in clip.metrics.items():
        reason = clip.xfail_reason(key)
        if not reason:
            continue
        with pytest.raises(AssertionError):
            check(clip, key, expected, actual[key])


def test_composites_match_measured_truth(case):
    clip, actual = case
    for name, should_fire in clip.composites.items():
        fired = name in actual["_findings"]
        assert fired == should_fire, (
            f"{clip.id}: composite {name!r} "
            f"{'did not fire but should have' if should_fire else 'fired but should not have'}"
        )


def test_strike_count_matches_cadence(case):
    """Counting events catches what averaging hides.

    Cadence comes from gaps between events, so a detector inventing one extra event per
    stride can still report a plausible median gap while finding twice the contacts.
    """
    clip, actual = case
    if "cadence_spm" not in clip.metrics or isinstance(clip.metrics["cadence_spm"], dict):
        pytest.skip("no measured cadence")
    expected = clip.metrics["cadence_spm"] / 60.0 * actual["duration_s"]
    found = sum(actual["_strikes"].values())
    err = abs(found - expected) / expected * 100
    assert err <= 10.0, (
        f"{clip.id}: {found} strikes over {actual['duration_s']:.2f}s, but the measured "
        f"cadence implies ~{expected:.0f} ({err:.0f}% off)"
    )


def test_both_feet_are_tracked(case):
    """A side view occludes the far leg; if it degrades badly, per-side metrics are noise."""
    clip, actual = case
    left, right = actual["_strikes"]["l"], actual["_strikes"]["r"]
    assert min(left, right) > 0, f"{clip.id}: one foot produced no contacts"
    imbalance = abs(left - right) / max(left, right) * 100
    assert imbalance <= 20.0, (
        f"{clip.id}: left/right strike counts differ by {imbalance:.0f}% (L={left} R={right})"
    )


def test_pose_fixture_matches_its_record(case):
    """The fixture must be from the extractor its filename claims, and span the clip's
    real duration -- catching a truncated fixture or a stale duration_s alike."""
    clip, actual = case
    assert clip.record["clip"].split(".")[0] == clip.name
    source = json.loads(clip.pose_path.read_text())["source"]
    assert clip.extractor in source.replace("mediapipe-", ""), (
        f"{clip.id}: fixture says source {source!r}"
    )
    expected = clip.record["duration_s"]
    err = abs(actual["duration_s"] - expected) / expected * 100
    assert err <= DURATION_TOLERANCE_PCT, (
        f"{clip.id}: fixture duration {actual['duration_s']:.2f}s vs recorded "
        f"{expected}s ({err:.1f}% off)"
    )


def test_every_clip_has_a_fixture_for_every_extractor():
    """A missing fixture silently halves coverage, since load_clips only yields what exists."""
    from tests.integration.clipcase import EXTRACTORS

    by_name = {}
    for clip in CLIPS:
        by_name.setdefault(clip.name, set()).add(clip.extractor)
    for name, found in sorted(by_name.items()):
        missing = set(EXTRACTORS) - found
        assert not missing, f"{name}: no pose fixture for {sorted(missing)}"


# ------------------------------------------------------------------ coverage guards

def test_every_metric_key_is_real():
    """A mistyped key would otherwise assert nothing and pass."""
    from gaitlab.metrics.defs import METRIC_DEFS

    known = {str(getattr(k, "value", k)) for k in METRIC_DEFS} | {"cadence_spm"}
    for clip in CLIPS:
        for key in list(clip.metrics) + list(clip.record.get("xfail", {})):
            assert key in known, (
                f"{clip.id}: {key!r} is not a metric the engine reports. A typo here "
                f"silently removes an assertion."
            )


def test_every_metric_is_validated_or_listed():
    """Adding a metric forces a decision rather than silence."""
    from gaitlab.metrics.defs import METRIC_DEFS

    asserted = {k for clip in CLIPS for k in clip.metrics}
    for key in METRIC_DEFS:
        key = str(getattr(key, "value", key))
        assert key in asserted or key in UNVALIDATED or key in UNMEASURED, (
            f"metric {key!r} is asserted by no clip and is not listed in UNVALIDATED. "
            f"Either give some clip a measured value for it, or record why there isn't one."
        )


def test_corpus_spans_the_cadence_range_that_breaks_detection():
    """Gait-event detection doubled below ~120 spm while every synthetic test passed.

    Only a real low-cadence clip caught it, so losing that end of the range would restore
    the blind spot without any test failing.
    """
    values = [c.metrics["cadence_spm"] for c in CLIPS if "cadence_spm" in c.metrics]
    assert values, "no clip asserts cadence at all"
    assert min(values) <= 110, (
        f"lowest cadence in the corpus is {min(values)} spm. Detection historically broke "
        f"below ~120 and nothing else caught it."
    )


def test_every_clip_asserts_something():
    for clip in CLIPS:
        assert clip.metrics or clip.composites, f"{clip.id}: record asserts nothing"
