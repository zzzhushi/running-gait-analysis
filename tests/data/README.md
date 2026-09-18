# Test data

Fixtures for the integration tests in `tests/integration/`.

Everything else in the suite runs on synthetic pose from `gaitlab/synthetic.py`, where the
answer is known because the generator put it there. That catches arithmetic errors but not
modelling errors — the generator and the detector share assumptions, so a detector that
finds "foot strike" half a step late looks perfectly correct against synthetic input. These
files exist so at least one test is anchored to something the engine did not produce.

## The clips

| Clip | View | Cadence | fps | Activity |
|---|---|---|---|---|
| `female_high_cadence` | side-right | 207 spm | 120 | treadmill run, high cadence |
| `female_side_view` | side-right | 190 spm | 120 | treadmill run |
| `female_rear_view` | rear | 181 spm | 120 | treadmill run from behind |
| `male_side` | side-left | 168.9 spm | 30 | treadmill run |
| `female_bounding` | side-right | 129 spm | 120 | bounding drill |
| `female_overstride` | side-right | 102.8 spm | 120 | slow run, long stride |

Each clip has a `<clip>.mp4`, one `<clip>.pose.<extractor>.json` per extractor, and a
`<clip>.groundtruth.json`. All are 720x1280 H.264 — one format, so no test needs to know which
capture path a clip came from.

The range matters more than the count. Gait-event detection doubled below about 120 spm while
every synthetic test passed, and `female_overstride` at 102.8 is the only thing that caught it;
`test_corpus_spans_the_cadence_range_that_breaks_detection` fails if that end is ever lost.
`female_bounding` is deliberately not running — long flight and a low contact rate — and
`female_rear_view` is the only non-side view.

Two clips were shot in slow-motion mode and arrived as 30 fps containers holding four times the
frames. They were normalised to honest 120 fps containers on ingest, because the extractors read
the container rate and would otherwise produce metrics wrong by that factor:

```
ffmpeg -i slowmo.mov -an -vf "setpts=PTS/4,scale=720:1280" -r 120 \
    -c:v libx264 -crf 23 -preset slow -pix_fmt yuv420p clip.mp4
```

**Consent.** Every clip is committed under this repository's MIT license, indefinitely and
re-forkable, with the explicit consent of the person in it: `male_side` from the person in the
clip; the five `female_*` clips from the maintainer, given 2026-09-15. Record the same for any
clip you add — see "Before adding another clip".

**Method.** Every `cadence_spm` here is measured by pixel-count — see "How the cadence numbers
were measured" below. No record needs to repeat that.

## The ground-truth records

One `<clip>.groundtruth.json` per clip, holding assertions and nothing else:

```json
{
  "clip": "female_overstride.mp4",
  "view": "side-right",
  "subject": "zzzhushi",
  "duration_s": 9.675,
  "metrics": { "cadence_spm": 102.8 },
  "tolerance_pct": {},
  "xfail": { "some_metric": "why this clip's value for it is not asserted yet" }
}
```

`duration_s` is the clip's own real duration, not a gait metric — checked separately as
fixture integrity (a truncated or re-encoded fixture would drift from it), not against a
tolerance in `metrics`.

A `metrics` entry is either a value, compared within tolerance, or a bound:

| Entry | Asserts |
|---|---|
| `102.8` | within tolerance of 102.8 |
| `{"max": 10}` | at most 10 |
| `{"min": 20}` | at least 20 |

Use a bound when the truth is "small" rather than a measured number. A percentage tolerance
collapses to zero near zero, so it cannot express "no meaningful overstride".

Tolerances default per metric in the test module, because how precisely a metric can be known
is a property of the metric rather than of the clip. `tolerance_pct` overrides that for one
clip, and an override is itself a claim worth justifying — overstride read by eye off gridded
crops is good to about 25%, cadence to 2%.

`composites` holds findings that fire or do not, as booleans, rather than numbers.

`subject` indexes `subjects.json`, shared because the same anthropometrics set the pixel scale
for the measurement and the personalized bands in the engine.

What does **not** belong in these files: how the measurement was made (identical for every
clip, so it is written once, below), what the engine currently gets wrong (that is what issues
and the tests themselves are for), and capture notes. Those made an earlier version of one
record 20,000 characters, most of it stale within a month.

## How the cadence numbers were measured

Every `cadence_spm` here comes from counting steps in raw pixels, with no pose model and no
part of the engine involved, so it stays valid if the extractor is ever swapped:

```
python3 scripts/measure_cadence_groundtruth.py tests/data/<clip> --stature-m <height>
```

The head rises and falls once per step; apexes of that trace are counted and cadence is
intervals over elapsed time. Frequency analysis only cross-checks, because it cannot separate
a step rate from twice or half that rate. The script also verifies the timebase from free fall
at each flight apex, which catches a clip shot in slow-motion mode, where the container reports
a frame rate the clip was not captured at and every per-second figure is wrong by that factor.

Values were confirmed against a by-hand count of every clip.

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

Contact time and duty factor are not asserted by any clip. `LIFT_FRACTION` in
`gaitlab/core/events.py` estimates ground contact from a fraction of the ankle's vertical
range, and that model is not currently validated against pixel-measured truth — out of
scope for now; this section covers cadence only.

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
