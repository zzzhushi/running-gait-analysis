"""Static-site pose extraction, driven through a real browser.

Local-only. The static site decodes video and runs MediaPipe inside the browser
(`web/js/pose.js`), and no other suite reaches that path: the engine tests read committed
pose fixtures, and those fixtures come from the Python extractor.

`web/js/pose.js` demuxes and decodes with WebCodecs when available, which is what these
tests exist to hold in place: a `<video>`/`requestVideoFrameCallback` playback path can
silently drop a large fraction of a high-frame-rate clip's frames on WebKit, at any
playback rate, where decoding demuxed samples directly does not depend on the compositor
and is exact on every engine tested.

Run with:  pytest tests/browser -s
Run against a specific engine:  GAITLAB_BROWSER=webkit pytest tests/browser -s
Repeat runs with:  GAITLAB_BROWSER_RUNS=5 pytest tests/browser -s
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from gaitlab.core.events import detect_events
from gaitlab.core.schema import PoseSequence
from extractor.timestamps import probe_timestamps

DATA = Path(__file__).resolve().parents[1] / "data"
CLIP = "female_high_cadence"

# The engine suite's cadence tolerance, with its BlazePose allowance applied.
CADENCE_TOLERANCE_PCT = 4.0

# Calibrated to measured run-to-run inference jitter on a complete frame grid, which
# persists across MediaPipe delegates and is not something this suite tries to eliminate.
# A regression back to a sparse or irregular grid produces spreads far past this
# threshold, so it stays a reliable signal without chasing ordinary inference variance.
CADENCE_STABILITY_TOLERANCE_SPM = 8.0

# A frame the browser never presents is a frame MediaPipe never sees. The reference
# extraction of the same file supplies the count the browser is measured against.
FRAME_SHORTFALL_TOLERANCE_PCT = 5.0

# The CPU delegate avoids depending on a working GPU/WebGL stack, which CI runners
# and headless browsers do not reliably provide.
_EXTRACT = """
async ([url, view]) => {
  const { extract } = await import('/web/js/pose.js');
  return await extract(url, view, () => {}, "CPU");
}
"""


def _record() -> dict:
    return json.loads((DATA / f"{CLIP}.groundtruth.json").read_text())


def _reference() -> dict:
    return json.loads((DATA / f"{CLIP}.pose.blazepose.json").read_text())


def _undetected(pose: dict) -> float:
    """Fraction of frames the pose model returned nothing for."""
    blank = sum(1 for fr in pose["frames"] if all(p[2] == 0.0 for p in fr))
    return blank / len(pose["frames"])


@pytest.fixture(scope="module")
def extractions(page, site, tmp_path_factory) -> list[dict]:
    """Pose dicts from `GAITLAB_BROWSER_RUNS` extractions of the same clip.

    Each run is written out: a browser extraction is not reproducible after the fact,
    so a failure is only diagnosable from the pose it actually produced.
    """
    runs = int(os.environ.get("GAITLAB_BROWSER_RUNS", "1"))
    out_dir = Path(os.environ.get("GAITLAB_BROWSER_ARTIFACTS")
                   or tmp_path_factory.mktemp("browser-pose"))
    url = f"{site}/tests/data/{CLIP}.mp4"
    view = _record()["view"]
    out = []
    for i in range(runs):
        pose = page.evaluate(_EXTRACT, [url, view])
        path = out_dir / f"{CLIP}.browser.{i + 1}.json"
        path.write_text(json.dumps(pose))
        seq = PoseSequence.from_pose_dict(pose)
        cadence = detect_events(seq).cadence_spm
        print(f"  run {i + 1}: {len(pose['frames'])} frames, {pose['fps']:.1f} fps, "
              f"cadence {cadence:.1f} spm, {_undetected(pose) * 100:.0f}% undetected "
              f"-> {path}")
        out.append(pose)
    return out


def test_presents_every_frame_of_the_clip(extractions):
    expected = len(_reference()["frames"])
    for i, pose in enumerate(extractions):
        got = len(pose["frames"])
        shortfall = (expected - got) / expected * 100
        assert shortfall <= FRAME_SHORTFALL_TOLERANCE_PCT, (
            f"run {i + 1}: extracted {got} of {expected} frames "
            f"({shortfall:.0f}% never reached the pose model); "
            f"reported fps {pose['fps']:.1f}"
        )


def test_exported_timestamps_match_container_presentation_pts(extractions):
    """Issue #99: decoded-frame clocks must include the MP4 video edit list.

    The committed clip has media_time=256 at a 1/15360 media timebase. Raw
    MP4Box CTS is therefore 16.667 ms ahead of FFprobe's presentation PTS.
    This compares every exported pose timestamp, not just the first frame.
    """
    expected = probe_timestamps(str(DATA / f"{CLIP}.mp4"))
    assert expected is not None
    for pose in extractions:
        actual = pose["timestamps"]
        assert len(actual) == len(expected) == len(pose["frames"])
        assert all(b > a for a, b in zip(actual, actual[1:]))
        assert max(abs(a - b) for a, b in zip(actual, expected)) <= 0.000051
        assert "edit list" in pose["timestamp_source"]


def test_no_edit_list_control_keeps_original_composition_pts(page, site):
    """The tiny FFmpeg-generated control deliberately has no elst box."""
    clip = "browser_no_editlist"
    traced = subprocess.run(["ffprobe", "-v", "trace", "-i", str(DATA / f"{clip}.mp4")],
                            capture_output=True, text=True, check=False)
    assert traced.returncode == 0
    assert "type:'elst'" not in traced.stderr
    pose = page.evaluate(_EXTRACT, [f"{site}/tests/data/{clip}.mp4", "side-right"])
    expected = probe_timestamps(str(DATA / f"{clip}.mp4"))
    assert expected is not None
    assert len(pose["frames"]) == len(pose["timestamps"]) == len(expected) == 8
    assert max(abs(a - b) for a, b in zip(pose["timestamps"], expected)) <= 0.000051
    assert "no edit list" in pose["timestamp_source"]


def test_playback_fallback_still_uses_its_own_timestamps(page, site):
    """Issue #99's MP4Box mapping must not leak into the <video> fallback."""
    js = """
    async (url) => {
      const original = globalThis.VideoDecoder;
      globalThis.VideoDecoder = undefined;
      try {
        const { extract } = await import('/web/js/pose.js');
        return await extract(url, 'side-right', () => {}, 'CPU');
      } finally {
        globalThis.VideoDecoder = original;
      }
    }
    """
    pose = page.evaluate(js, f"{site}/tests/data/browser_no_editlist.mp4")
    assert len(pose["frames"]) == len(pose["timestamps"]) > 0
    assert pose["timestamp_source"] in ("measured", "assumed")


def test_cadence_matches_measured_truth(extractions):
    truth = _record()["metrics"]["cadence_spm"]
    for i, pose in enumerate(extractions):
        seq = PoseSequence.from_pose_dict(pose).validate()
        cadence = detect_events(seq).cadence_spm
        err = abs(cadence - truth) / truth * 100
        assert err <= CADENCE_TOLERANCE_PCT, (
            f"run {i + 1}: cadence is {cadence:.1f} spm, measured truth is {truth} "
            f"({err:.1f}% off, tolerance {CADENCE_TOLERANCE_PCT}%)"
        )


def test_repeated_extractions_agree(extractions):
    """The same file through the same build must stay within measured inference noise.

    Frame acquisition itself is deterministic (WebCodecs decodes every sample the
    container declares, independent of run); CADENCE_STABILITY_TOLERANCE_SPM covers
    remaining jitter from the browser's own inference pipeline, not from the grid.
    """
    if len(extractions) < 2:
        pytest.skip("set GAITLAB_BROWSER_RUNS>1 to compare runs")
    cadences = [detect_events(PoseSequence.from_pose_dict(p)).cadence_spm
                for p in extractions]
    spread = max(cadences) - min(cadences)
    assert spread <= CADENCE_STABILITY_TOLERANCE_SPM, (
        f"cadence varies by {spread:.1f} spm across {len(cadences)} runs of the same "
        f"clip: {', '.join(f'{c:.1f}' for c in cadences)}"
    )
