# Overstride stage 1: frame and timebase evidence (issue #81)

The [manifest](assets/overstride-timebase-manifest.json) names all six committed RTMPose
fixtures and fixes one sample frame at each source rate. The indices are independent of
the contact detector. The [report](assets/overstride-timebase-report.json) is regenerated
from the committed pose JSON and MP4 files. For every clip it records input SHA-256 hashes,
frame counts, first/last times, PTS span, median frame interval, effective and container
frame rates, container duration, coded and display dimensions, rotation, and explicit
pass/fail checks. It also lists intervals more than 1.5 times the median frame interval;
these are timing discontinuities, **not** proof of a decoder drop.

The two committed, reviewer-visible anchors are:

- [120 fps female_overstride frame 262](assets/overstride-timebase-female_overstride-frame-262.png)
- [30 fps male_side frame 120](assets/overstride-timebase-male_side-frame-120.png)

Each is decoded by zero-based frame index and overlaid with that index's pose points.
The footer burns in the index, pose time, current container PTS, frame count, rate, and
validation limit. PNG metadata carries the same identifiers and the video/pose hashes.
Neither frame claims to be a validated contact or a correct landmark placement.

## Regenerate and verify

Install development dependencies and `ffmpeg`/`ffprobe`, then run:

```bash
python scripts/gen_overstride_timebase_evidence.py
python scripts/gen_overstride_timebase_evidence.py --check
pytest tests/test_overstride_timebase_evidence.py
```

The test suite regenerates the report and images into a temporary directory. It compares
report bytes and PNG metadata exactly, then allows only small visual differences between
decoder/font versions (at most 1 mean channel level and 0.5% strongly changed pixels).
The CLI `--check` compares pixels exactly on the current host. CI installs `ffmpeg`
explicitly; the test skips only on a local machine without the video tools.

## What the checks establish

All six pose sequences have the same number of frames as the current video probe and
container declaration. Every stored timestamp is strictly increasing and matches the
corresponding current video PTS within **0.000051 s** (the legacy JSON is rounded to four
decimal places). The video duration agrees with PTS span plus a median frame interval
within one median interval and rounding allowance. Pose display dimensions agree with
the rotation-adjusted video dimensions; the fixed-index PNGs additionally require an
exact-size decoded frame before overlay. This avoids silently resizing a mismatched video.

The old fixture files do **not** record which timestamp provider their original extractor
used. Matching current ffprobe PTS is strong agreement with the present video, but cannot
retroactively prove the extractor used ffprobe or that the pose was produced from these
particular video bytes. New extracts can record provider provenance; these legacy fixtures
must remain labeled “provider unrecorded.” The PNGs support visual alignment review, but
automated pixel equality only guards against renderer drift. A reviewer still needs to
inspect whether the skeleton is plausibly aligned.

This stage does **not** validate anatomical landmarks, initial-contact timing, the
leg-length denominator, the overstride value, or a clinical threshold. Those belong to
later stages of the [overstride validation plan](../metrics/overstride.md).
