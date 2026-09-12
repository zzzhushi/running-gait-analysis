# Criterion-validation protocol

GaitLab is currently **not criterion validated**. Synthetic clips verify formulas and
software invariants; they cannot establish biomechanical accuracy. This document defines
what is required before confidence can be promoted or scoring reconsidered.

## Reference capture

Record each trial synchronously with:

- the exact supported phone/camera protocols (side-left, side-right, rear; 60/120/240 fps;
  declared resolution and distance);
- 3-D marker-based motion capture with a documented segment model;
- instrumented treadmill or force plates for initial contact and toe-off;
- a common clock or recorded synchronization pulse;
- the exact released pose model/version and untouched source video.

Manual 2-D annotations by at least two blinded raters are useful for diagnostic comparison,
but are not a substitute for force/3-D criterion measurements.

## Sampling matrix

Recruit enough participants to estimate error within—not merely across—these strata:

- stature and leg length across short, middle, and tall ranges;
- women and men, recording anatomy/anthropometry directly rather than using sex as a body-
  shape proxy; include people outside binary categories without forcing an equation;
- a broad adult age and body-mass range;
- multiple self-selected speeds plus fixed matched speeds;
- rearfoot, midfoot, and forefoot contact patterns;
- different skin tones, clothing, footwear, hair/body shapes, and relevant assistive devices;
- treadmill and overground protocols if both are claimed.

Pre-register rules and report the achieved distribution. Do not call a fixture “diverse”
from a few handpicked demonstration clips.

## Manifest

Each trial uses `validation/manifest.schema.json`. Raw video/criterion files remain out of
git; a de-identified manifest records checksums, consent/use constraints, participant strata,
protocol, model version, and synchronized result paths. Split by participant so one person's
trials never occur in both development and test sets.

## Required analyses

For each metric and relevant stratum report:

- valid-observation and failure rates, including reasons for missing output;
- signed bias, MAE, RMSE, and Bland–Altman 95% limits of agreement;
- event timing error in milliseconds against force data;
- test–retest and inter-session reliability where repeat captures exist;
- error versus speed, stature/leg length, sex category, skin tone, clothing, footwear,
  frame rate, view error, and pose-confidence decile;
- calibration and test results separately, with bootstrap confidence intervals.

Do not use correlation alone as an accuracy measure. Publish paired errors or a usable
de-identified derivative wherever consent permits.

## Promotion gates

The registry's literature tier must not be presented as product validation. Before any metric
is labeled criterion validated, an acceptance threshold must be specified before viewing
held-out results. Thresholds must follow intended use and a meaningful change, not be
reverse-engineered from achieved error. An asymmetry flag additionally requires a
metric-specific repeatability/MDC. A composite needs its own prospective validation.

An overall score requires a stated construct, validated weighting, calibration,
discrimination, and external validation. No such score is currently enabled.

## Current status

- Schema and evaluator interface: included in `validation/`.
- Real synchronized recordings: **not included**.
- Published GaitLab criterion results: **none yet**.
- Maximum product confidence: **moderate**; event timing below 120 fps: **low**.
