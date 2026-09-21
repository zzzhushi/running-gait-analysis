# Overstride measurement contract analysis

Status: **analysis for issue
[#70](https://github.com/zzzhushi/running-gait-analysis/issues/70), not a validated contract**.

This document records what GaitLab computes today, what the cited research actually defines,
which substitutions exist between the two, and what evidence is needed before choosing a target
measurement contract. It deliberately does not select a new denominator or change runtime
behavior. Repeatability on the existing pose fixtures is not enough to establish accuracy.

## Completion rule for this analysis

- **Inspectable artifact:** the tables below trace a reported value from pose landmarks and
  detected events through normalization, aggregation, and interpretation.
- **Deterministic check:** every statement about current behavior names the source location that
  implements it, so it can be checked against `main`.
- **Does not validate yet:** source-frame identity, landmark accuracy, contact timing, denominator
  accuracy, thresholds, scoring, and coaching remain unvalidated.

## The user question

The intended question is:

> At initial contact, how far ahead of a hip reference is the landing foot in the direction of
> travel?

That question contains several independent choices. “Overstride” is not a complete measurement
definition until the proximal point, distal point, contact event, denominator, sign, aggregation,
and interpretation are each specified.

## Current dependency path

```text
decoded frames + timestamps
        |
        v
pose hip / knee / ankle coordinates + confidence
        |                                  |
        |                                  v
        |                         ankle-y event detector
        |                                  |
        v                                  v
facing direction + projected leg      detected strike frame
        |                                  |
        +----------------+-----------------+
                         v
          per-strike signed normalized reach
                         |
                         v
               per-side median values
                         |
                         v
        maximum side -> bands -> score/coaching
```

The output therefore depends on more than the one-line reach formula. A correct subtraction can
still produce a wrong result because the wrong source frame, landmark, facing direction, contact
time, or denominator entered it.

## What the code computes today

For each detected strike `s` on each side:

```text
reach_px(s) = (ankle_x(s) - hip_x(s)) * facing

projected_leg_px = median over all frames and both sides of:
                   distance(hip, knee) + distance(knee, ankle)

step_value(s) = reach_px(s) / projected_leg_px * 100
side_value    = median(step_value(s) for that side)
headline      = max(left side_value, right side_value)
```

| Contract term | Current implementation | Current evidence status |
|---|---|---|
| Proximal point | Pose-model `l_hip` / `r_hip` keypoint | Proxy; offset from an anatomical marker unmeasured |
| Distal point | Pose-model `l_ankle` / `r_ankle` keypoint | Proxy; offset from lateral malleolus unmeasured |
| Event | `ev.strikes[side]` | Heuristic ankle-y boundary; not compared with labelled contact |
| Denominator | Median projected thigh + shank length in pixels | Software-defined; anatomical and projection validity unmeasured |
| Direction | `PoseSequence.facing_sign()` | Software-checked in other contexts; overstride mirror behavior not isolated |
| Per-step unit | Percent of projected pose-leg length | Displayed as `%leg`, which does not describe the projection/proxy |
| Within-side aggregation | Median | Product heuristic; no documented sample-size or spread rule |
| Cross-side aggregation | Maximum of side medians (`worst_high`) | Product heuristic that discards which distribution produced the headline |
| Bands | Good through 8; warning through 15 | Source not identified |
| Confidence/scoring | `high`, scored | Contradicted by integration status `UNVALIDATED` |

Source locations:

- Formula and aggregation declaration:
  [`gaitlab/metrics/definitions/overstride.py`](../../gaitlab/metrics/definitions/overstride.py)
- Projected leg denominator:
  [`gaitlab/metrics/ctx.py`](../../gaitlab/metrics/ctx.py)
- Contact-event heuristic:
  [`gaitlab/core/events.py`](../../gaitlab/core/events.py)
- Real-clip validation status and tolerance:
  [`tests/integration/clipcase.py`](../../tests/integration/clipcase.py)

### Important denominator behavior

`_leg_length` currently:

- pools both anatomical sides and every frame into one median;
- uses 2-D projected segment distances, which change with pose-estimation error and out-of-plane
  motion even when anatomical segment lengths are constant;
- does not gate each contributing hip, knee, and ankle on keypoint confidence;
- uses `median(lens) or 1.0`, which does not replace a `NaN` median because `NaN` is truthy.

These facts do not establish that the denominator is unusable. They establish that `%leg` is not
yet directly comparable with a published anthropometric normalization.

### Important event behavior

The event detector finds ankle-y stance peaks and walks outward until the ankle has lifted 15% of
its vertical range. The code describes `LIFT_FRACTION = 0.15` as an uncalibrated heuristic. A
detected strike is therefore an estimated contact boundary, not an observed force-plate onset.

## What the cited studies support

### Lieberman et al. 2015

Lieberman et al. measured running at 3.0 m/s in 14 fit, experienced runners using 500 Hz 3-D
motion capture and 1000 Hz treadmill force plates. The study:

- placed markers at the greater trochanters, malleoli, calcaneus, and metatarsal heads;
- defined foot contact as the first instance of vertical ground-reaction force;
- normalized foot position relative to hip and knee by standing lower-extremity length measured
  from greater trochanter to floor; and
- reported an association between dimensionless hip-relative landing position and braking
  impulse in that controlled experiment.

This supports the relevance of a continuous hip-relative landing-position construct. It does not
provide an 8% or 15% cutoff, validate GaitLab's pose keypoints or event detector, establish injury
causation, or establish an intervention rule.

### Baker et al. 2024

Baker et al. defined overstriding as horizontal distance from a greater-trochanter marker to a
lateral-malleolus marker at foot contact, normalized by leg length. The paper evaluated ten
recreational runners and modeled thigh, shank, and foot segment angles separately.

The high 94.7–99.4% values reported for several models are conditional R-squared values that
include participant-specific random effects. Fixed-effect marginal R-squared values were lower:
55.7–61.8% for IMU-derived angles and 83.0–86.4% for motion-capture-derived angles. The paper also
states that there is no consensus on what qualifies as excessive overstriding and notes a lack of
consensus on the relationship between braking force and injury.

This supports segment angles as related measurements. It does not validate one global
hip-to-ankle angle as an equivalent replacement for normalized horizontal distance.

## Evidence must be tracked on separate axes

| Evidence question | Current status | What would advance it |
|---|---|---|
| Construct provenance: is the intended quantity described in research? | Referenced | Already supported as a continuous hip-relative landing-position construct |
| Implementation validity: does this pipeline estimate that quantity? | Provisional | Frame, landmark, event, denominator, and end-to-end comparisons |
| Interpretation: does a value or band distinguish a meaningful state? | Unsupported | Population-appropriate threshold/outcome evidence |
| Actionability: does changing it improve an outcome? | Unsupported | Intervention evidence with benefits and harms |

These axes must not collapse into one confidence label. A cited construct does not validate its
implementation. A population distribution is not automatically a cutoff. A validated cutoff is
not automatically evidence for coaching.

This analysis does not propose a general rule that some subset of these axes automatically makes
a metric eligible for the overall score. The score's meaning and evidence requirements need a
separate product-level contract.

## Contract decisions and available options

### 1. Proximal point

| Option | Benefit | Limitation | Status now |
|---|---|---|---|
| Same-side pose hip | Available and matches current code | Model keypoint is not a validated greater-trochanter marker | Current proxy |
| Mid-hip | Less sensitive to one hip track | Changes the construct and can hide side-specific tracking error | Not evaluated |
| Manually marked greater trochanter | Closer to laboratory definition | Not scalable; landmark may not be visually identifiable without a marker | Reference candidate |

Recommendation for validation: retain same-side pose hip as the implementation candidate and
compare it with independently placed reference points before calling it anatomically equivalent.

### 2. Distal point

| Option | Benefit | Limitation | Status now |
|---|---|---|---|
| Pose ankle | Stable and strike-pattern independent; closest current proxy to malleolus | Not the shoe-ground contact point; model offset unmeasured | Current headline candidate |
| Heel | Visually meaningful for rearfoot contact | Changes meaning for mid/forefoot contacts | Debug comparison only |
| Heel-to-toe midpoint | Inspectable summary of foot position | Varies with foot angle and is not an anatomical midfoot measurement | Debug comparison only |
| Toe | Useful for forefoot contact | Changes meaning across strike patterns | Debug comparison only |

Recommendation for validation: keep ankle as the candidate measurement point and emit heel, toe,
and a clearly named foot-landmark midpoint proxy for comparison. Do not select among them using
the same detector output being evaluated.

### 3. Contact event

| Option | Benefit | Limitation | Status now |
|---|---|---|---|
| Current ankle-y boundary | Already available | Uncalibrated and frame-rate sensitive | Current estimate |
| Human-labelled video contact | Inspectable on existing clips | Rater uncertainty; reference agreement, not criterion accuracy | First validation reference |
| Force plate / pressure insole | Direct criterion signal | Requires new synchronized capture | Criterion reference |

Recommendation for validation: define a visual annotation rule and uncertainty interval before
labelling. Report agreement with those reference annotations without calling them ground truth.

### 4. Denominator

| Option | Benefit | Limitation | What current fixtures can establish |
|---|---|---|---|
| Projected thigh + shank (`ctx.leg`) | Available; scale-free; current behavior | Projection and keypoint error; excludes ankle-to-floor; pools frames/sides | Software repeatability only |
| Dynamic hip-to-estimated-floor pixels | Inspectable; closer in words to trochanter-to-floor | Posture, floor, camera, pose, and event dependencies; not standing anthropometry | Software repeatability only |
| External standing leg length | Matches Lieberman's denominator conceptually | Pixel numerator also needs a validated image scale in the runner's motion plane | Requires capture/calibration protocol |
| No denominator; global inclination | Simple and scale-free | Different construct; affected by instantaneous projected limb configuration | Arithmetic/rendering cross-check only |

No option is currently validated as the target. In particular, lower coefficient of variation on
the committed pose fixtures would establish better repeatability under those fixtures, not greater
accuracy or closer agreement with the published denominator.

Recommendation: do not change the denominator in issue #70. First compare candidate denominators
with independently marked frames and a declared reference protocol. Until then, describe the
current unit precisely as **percent of projected pose-leg length**.

### 5. Sign and coordinates

The current intended convention is coherent:

- image origin at top left;
- positive image x points right;
- `facing` maps image direction to direction of travel; and
- positive reach means ankle ahead of hip in the travel direction.

Required check: reflect the image horizontally and reverse `facing` while retaining anatomical
side labels. Per-side values should remain unchanged. A separate left/right-label swap should swap
per-side results rather than being combined with image reflection.

### 6. Per-step and summary outputs

Per-step values are the primary auditable measurements. They should remain available even when a
summary is unavailable. A useful debug record includes source frame/time, side or track, all
landmark coordinates and confidences, facing, denominator, raw reach, normalized reach, and any
reference contact interval.

The current per-side median is a reasonable robust candidate but remains a product choice. The
current maximum across side medians is not required by the measurement construct and hides the
two distributions. The number of contacts needed for a runner-level summary and the spread that
makes it unreliable should be chosen from validation data, not written into the contract first.

### 7. Bands, score, and coaching

No source has been identified for the current 8% and 15% bands. The cited studies do not establish
a universal “excessive” threshold. Therefore the analysis supports only an informational,
continuous measurement while interpretation evidence is absent.

Removing unsupported scoring and coaching is tracked separately in
[#77](https://github.com/zzzhushi/running-gait-analysis/issues/77). This analysis does not change
runtime behavior.

## Validation decomposition

For each reference contact, preserve three values:

| Value | Landmarks | Contact | What comparison isolates |
|---|---|---|---|
| A: reference | Independently placed | Reference interval/time | Reference measurement |
| B: pose at reference contact | Pose model | Reference interval/time | `B - A`: landmark + denominator disagreement |
| C: production | Pose model | Detected event | `C - B`: contact-timing contribution |

`C - A` is the observed end-to-end disagreement. Keeping all three prevents a timing error from
being mistaken for a landmark/denominator error or vice versa.

Frame-rate experiments must also sweep sampling phase. For a 120-to-30 fps decimation, all four
offsets (`0,4,8,...` through `3,7,11,...`) are valid 30 fps realizations. A result from one offset
is not “the 30 fps error.” Downsampled pose data and downsampled/re-extracted video answer
different questions and should be reported separately.

## Proposed contract boundary after validation

Issue #70 can become a final contract when the project can fill these fields with evidence:

| Field | Required decision/evidence |
|---|---|
| Proximal and distal points | Named points plus measured agreement/offsets |
| Contact | Operational definition, reference method, uncertainty, and detector error |
| Denominator and unit | Chosen option, capture assumptions, and agreement evidence |
| Per-step output | Machine-readable trace back to frame/time/points |
| Aggregation | Minimum observations, statistic, spread, and refusal behavior |
| Supported capture | View, FPS, camera constraints, and rejection behavior |
| Interpretation | Informational unless a population-appropriate threshold is supported |
| Actionability | No coaching claim without intervention evidence |

The completion format should retain three explicit statements:

- **Inspectable artifact:** a human can reproduce one reported value from an exported frame and
  debug record.
- **Deterministic check:** a hand-computed fixture verifies formula/sign/invariance, and labelled
  clips verify each pipeline boundary.
- **Does not validate yet:** any unsupported populations, captures, thresholds, or actions are
  named rather than hidden behind a general confidence label.

## Findings in existing documentation

This analysis identifies, but intentionally does not bundle, these follow-up corrections:

- `docs/tech_requirements.md` presents the hip reference as a deviation from a COM specification;
  the cited construct is hip-relative, while GaitLab's reproduction remains unvalidated.
- `docs/references.md` describes Crowell and Davis 2011 as reducing “overstride,” but that work's
  shank-angle intervention is not evidence for GaitLab's hip-to-ankle normalized bands.
- `docs/spec/metrics.yaml`, generated metric tables, tests, and coaching still encode the unsourced
  8/15 bands and high-confidence scoring behavior; runtime correction belongs to #77.

Keeping those changes separate makes reviewable which statements come from the issue analysis and
which changes alter product documentation or behavior.

## References

- Lieberman, D. E. et al. (2015). *Effects of stride frequency and foot position at landing on
  braking force, hip torque, impact peak force and the metabolic cost of running in humans.*
  https://journals.biologists.com/jeb/article/218/21/3406/14416/Effects-of-stride-frequency-and-foot-position-at
- Baker, L. M. et al. (2024). *Predicting overstriding with wearable IMUs during treadmill and
  overground running.* https://pmc.ncbi.nlm.nih.gov/articles/PMC10942980/
- Damsted, C. et al. (2015). *Reliability of video-based identification of footstrike pattern and
  video time frame at initial contact in recreational runners.*
  https://pubmed.ncbi.nlm.nih.gov/25920964/

External research defines constructs and reports study-specific relationships. It does not, by
itself, validate GaitLab's implementation.
