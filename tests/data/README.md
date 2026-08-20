# Test data

Fixtures for the integration tests in `tests/integration/`.

Everything else in the suite runs on synthetic pose from `gaitlab/synthetic.py`, where the
answer is known because the generator put it there. That catches arithmetic errors but not
modelling errors — the generator and the detector share assumptions, so a detector that
finds "foot strike" half a step late looks perfectly correct against synthetic input. These
files exist so at least one test is anchored to something the engine did not produce.

## `male_side.*`

| File | What it is |
|---|---|
| `male_side.mp4` | Treadmill, side view, runner facing image-left. 720x1280, 30 fps, 360 frames, 12.0 s — a re-encoded trim (t=10-22s) of a 40s source recording. |
| `male_side.pose.json` | Landmarks extracted from it with `extractor/extract_pose.py` (RTMPose-Halpe26). What the tests actually load. |
| `male_side.groundtruth.json` | Measured cadence + provenance, and the physiological bands the tests assert. |

Ground truth is **168.9 ± 0.5 spm**, measured from raw pixels by two independent methods
that involve no pose model and no part of this engine — consistent with 168.6 ± 0.3 spm
measured the same way on the un-trimmed 40s source. Regenerate it with:

```
python3 scripts/measure_cadence_groundtruth.py tests/data/male_side.mp4
```

The tests load `male_side.pose.json`, not the video, so they need no ffmpeg, no rtmlib, and
no model download — they run in CI in well under a second. The `.mp4` is committed so the
ground truth stays reproducible and so extraction itself can be tested, not just the engine
— see "Two layers, both real" below. If either file is absent the integration tests skip
rather than fail.

**Consent.** The person in `male_side.mp4` has given explicit consent to have this clip
committed to this public repository under its MIT license, indefinitely and re-forkable.
Record the same for any clip you add — see "Before adding another clip" below.

## Two layers, both real

The video and the pose JSON test different things and both are committed on purpose:

| Layer | Input | Catches | CI cost |
|---|---|---|---|
| Engine (`tests/integration/test_male_side_clip.py`) | `.pose.json` | metric/event regressions | <1s, no deps, runs every push |
| Extraction | `.mp4` | extractor regressions, model swaps | needs rtmlib/onnxruntime + ~700MB of models; run on a schedule or when `extractor/` changes, not per-commit |

Pose-only would be faster but hollow: the ground truth (168.9 spm) was measured from raw
pixels, not from pose, specifically so it stays valid if the extractor is ever swapped —
that guarantee is void if the video that number was measured against isn't kept.

## Re-extracting the pose

```
python3 extractor/extract_pose.py tests/data/male_side.mp4 --view side-left \
    -o tests/data/male_side.pose.json
```

Needs `rtmlib onnxruntime opencv-python`. If the extractor changes, re-run this, then
re-run the integration tests: `test_pose_fixture_is_intact` will catch a truncated or
model-swapped fixture.

## Before adding another clip

Three things worth being deliberate about, in order of how easy they are to fix later:

- **Consent is not fixable later.** This is a public MIT repo — clone/fork copies live
  outside your control the moment they're pushed, and git history does not forget. Get
  explicit, recorded consent from whoever is in the clip *before* committing it, matching
  the note above. `conftest.py`'s golden fixture stays deliberately synthetic — that default
  still holds; adding a real clip is the exception, not a precedent to lean on.
- **Trim before you extract, not after.** Re-extracting pose from a shorter cut is a second
  round of RTMPose (minutes of CPU) and a second manual "does this still validate everything"
  pass — do that once, on the final cut. `male_side.mp4` was verified against its untrimmed
  source before the trim was kept: same score/grade/findings, cadence within 0.3% of the
  trim's own measured truth, every metric within ~10% (see `trim_provenance` in
  `male_side.groundtruth.json`). 10-15s at typical running cadence is usually enough — that's
  ~15-20 strides per foot, plenty for the engine's per-metric medians.
- **Video doesn't delta-compress.** Every commit of a re-encoded or re-trimmed version of
  the same clip stores a full new blob in `.git/objects` forever — settle the trim before
  the first commit rather than iterating on it in-repo. A 10-15s re-encode (crf 20-23) is
  usually 1-3 MB; avoid committing raw phone footage (which runs 5-10x larger for the same
  duration). See `.git/objects` size math below before this becomes a problem at scale.

## Git LFS — not yet, revisit past ~50MB

The whole repo's `.git` history is currently ~7MB. This clip adds ~2MB (video + pose JSON).
At 1-3MB per clip (see above), even 15-20 clips covering every view/fps/body-type
combination worth testing stays under 50MB total — well inside what plain git handles
comfortably; GitHub's own guidance is to keep repos under a few hundred MB before it's
worth the operational cost.

LFS is worth it when either becomes true:

- **Total committed media crosses roughly 50MB**, or any single file nears GitHub's 100MB
  hard limit.
- **Clips get iterated on in-repo** (re-encoded, re-trimmed) often enough that history bloat
  from non-delta-compressible video becomes the dominant cost — LFS stores only the current
  pointer target in the main history, at the price of every contributor needing `git-lfs`
  installed, CI needing `lfs: true` on checkout, and GitHub's free LFS tier (1GB storage,
  1GB/month bandwidth) potentially needing a paid data pack.

Given the trim discipline above, that threshold is a while off. If it's ever crossed,
migrating existing history into LFS (`git lfs migrate import`) rewrites commit hashes — plan
it as a deliberate one-time migration, not a decision to make mid-PR.

## What is still missing

No clip here can settle where initial contact actually falls. At 30 fps a whole stance is
about 7 frames, so competing event-anchor definitions differ by 2-3 frames and none can be
resolved. `LIFT_FRACTION` in `gaitlab/core/events.py` is currently bounded by physical
constraints rather than calibrated. **One 120 or 240 fps clip** — any modern phone's slow-mo
mode — would settle it permanently. That is the highest-value addition to this directory.
