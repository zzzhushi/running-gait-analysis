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

## `female_overstride.*`

| File | What it is |
|---|---|
| `female_overstride.mp4` | Treadmill, side view, runner facing image-right. 720x1280, **120 fps**, 1160 frames, 9.675 s. Re-encode of a 1080x1920 HEVC phone clip; not trimmed (the source is only 9.675 s). |
| `female_overstride.pose.json` | Landmarks from `extractor/extract_pose.py` (RTMPose-Halpe26). What the tests load. |
| `female_overstride.groundtruth.json` | Measured cadence, contact and flight, full provenance, and the root-cause analysis of what the engine gets wrong on it. |

Ground truth is **102.8 ± 0.6 spm**, from four independent pixel signals (head-top row,
silhouette centroid, leg-band motion energy, foot-band spread), each read by both a
fine-grid DFT and a 4-harmonic autocorrelation ladder, plus two cross-checks of different
physics. All eight estimates land in 102.28–103.91 spm. Contact time (**505 ± 25 ms**) and
flight (**75 ± 15 ms**) are *measured*, not literature bands — that is what 120 fps buys.

**This fixture was added because it failed.** `male_side.mp4` sits at 168.9 spm, where
gait-event detection happens to work, so it could only show the engine had not regressed.
This clip sits at 102.8 spm, where detection doubled: 126.87 spm, 34 strikes where ~17 are
real, a 57.3% duty factor alongside 199 ms of flight, and a ground-tilt warning on a level
clip. Cadence is now 102.96 spm (0.16% off) and the rest went with it.

Two assertions are still `xfail(strict=True)` — contact time and duty factor — for a
different reason: `LIFT_FRACTION` cannot fit both clips at once. This clip's measured 505 ms
needs 0.30, which puts male_side above a 50% duty factor. See the note on
`test_contact_time_is_physiological` and the sweep in `gaitlab/core/events.py`. The markers
are the todo list: strict means the run fails the moment they start passing.

The frame rate was never the cause. This clip carries real 120 fps container timestamps and
the engine reads them correctly (`effective_fps` = 119.896); it failed identically with a
perfect timebase.

**Consent.** The runner in `female_overstride.mp4` is the repository maintainer, who gave
explicit consent on 2026-09-15 to commit it here under the MIT license, indefinitely and
re-forkable — the same terms recorded for `male_side.mp4`.

Re-extract with:

```
python3 extractor/extract_pose.py tests/data/female_overstride.mp4 --view side-right \
    -o tests/data/female_overstride.pose.json
```

## Two layers, both real

The video and the pose JSON test different things and both are committed on purpose:

| Layer | Input | Catches | CI cost |
|---|---|---|---|
| Engine (`tests/integration/test_*_clip.py`) | `.pose.json` | metric/event regressions | <1s, no deps, runs every push |
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

The whole repo's `.git` history was ~7MB before any clip. `male_side.*` adds ~2MB and
`female_overstride.*` ~3.8MB (a 120fps clip costs more per second than a 30fps one).
At 2-4MB per clip, even 10-15 clips covering every view/fps/body-type
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

The 120 fps clip this section used to ask for now exists (`female_overstride.mp4`), and it
did settle where initial contact falls: stance is ~60 frames rather than ~7, so contact time
is measured (505 ± 25 ms) instead of argued over. `LIFT_FRACTION` in
`gaitlab/core/events.py` turned out to be unfittable rather than merely uncalibrated: no
single value satisfies both clips, because it thresholds a fraction of the ankle's vertical
range and most of that range is swing-phase lift. Defining contact by foot velocity matching
ground velocity is the open replacement.

**The single highest-value addition now is a second 120 fps clip at a different cadence,
with contact time measured from pixels.** Contact detection currently has one measured
constraint (`female_overstride`, 505 ms) and one literature band (`male_side`, at 30 fps
where a stance is ~7 frames and any method is quantization-limited). With one measured
point every threshold that fits one clip misses the other, and there is no way to tell
whether the model is wrong or the unmeasured clip's true contact is simply different. Two
measured points make it testable instead of fittable.

Still missing from every clip here:

- **A known-length reference in frame, at the runner's depth.** Every cm and km/h figure in
  `female_overstride.groundtruth.json` is inferred from anthropometrics.
- **The treadmill's displayed speed**, which four metrics depend on.
- **Two seconds of empty belt before stepping on.** Temporal-median background subtraction
  is unusable on a treadmill — a stationary runner makes the median *become* her body — and
  a real background plate is the only fix.
- **Something with a true vertical edge**, so camera roll can be measured rather than
  assumed. Both clips currently make their angle measurements conditional on it.
- **A band or contrasting sock on one leg.** When both legs are the same colour they cannot
  be told apart wherever they overlap, which is what makes far-leg angles unmeasurable.
- **A clip that is not a treadmill**, if overground support is ever in scope.
