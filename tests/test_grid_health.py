"""Completeness of a pose sequence's own sampling grid.

An extractor that silently samples a fraction of a clip's frames still reports a
self-consistent frame rate, because the rate is computed from the frames it kept. The
loss is only visible in the surviving gaps: they become multiples of the source's frame
interval, so that interval — and the frame count the file really had — can be recovered
from the timestamps alone, with no reference extraction and no ground truth.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaitlab.core.grid import grid_health

DATA = Path(__file__).resolve().parent / "data"

# A grid missing more than this fraction of the source's frames cannot carry event timing
# at the precision the metrics assume.
MIN_CAPTURED = 0.95


def _poses():
    for path in sorted(DATA.glob("*.pose.*.json")):
        d = json.loads(path.read_text())
        if d.get("timestamps"):
            yield path.name, d["timestamps"]


@pytest.mark.parametrize("name,timestamps", list(_poses()))
def test_committed_fixtures_have_a_complete_grid(name, timestamps):
    h = grid_health(timestamps)
    assert h.captured_fraction >= MIN_CAPTURED, (
        f"{name}: kept {h.captured} of the {h.implied} frames implied by a "
        f"{h.interval * 1000:.1f} ms frame interval ({h.captured_fraction:.0%})"
    )


def test_a_browser_grid_that_dropped_half_the_clip_is_flagged():
    rec = json.loads((DATA / "female_high_cadence.grid.browser.json").read_text())
    h = grid_health(rec["timestamps"])
    assert h.captured_fraction < MIN_CAPTURED
    # Recovered from the gaps alone; the recorded source frame count is not an input.
    assert h.implied == pytest.approx(rec["source_frames"], rel=0.05)


def test_a_uniform_grid_is_complete():
    fps = 120.0
    assert grid_health([i / fps for i in range(600)]).captured_fraction == 1.0


def test_sporadic_drops_are_detected():
    """Real capture loss is uneven, which is what leaves the source interval visible."""
    fps = 120.0
    kept = [i for i in range(600) if i % 3]          # two of every three frames
    h = grid_health([i / fps for i in kept])
    assert h.captured_fraction == pytest.approx(2 / 3, abs=0.02)
    assert h.interval == pytest.approx(1 / fps, rel=0.02)


def test_uniform_decimation_is_indistinguishable_from_a_slower_clip():
    """A grid thinned at a constant stride carries no evidence of the frames removed.

    Detection depends on surviving gaps being uneven multiples of the source interval.
    Capture loss driven by display refresh can be near-uniform, so this check is a floor
    on what is detectable from timestamps, not a guarantee.
    """
    fps = 120.0
    assert grid_health([2 * i / fps for i in range(300)]).captured_fraction == 1.0
