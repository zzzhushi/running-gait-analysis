# Overstride

> Measurement contract. Tracked by [#70](https://github.com/zzzhushi/running-gait-analysis/issues/70);
> the epic is [#69](https://github.com/zzzhushi/running-gait-analysis/issues/69).

**This document specifies the target, not current behaviour.** Where the two differ today:

| | Contract | Code today |
|---|---|---|
| Denominator | hip height above the belt line | `ctx.leg`, thigh + shank ([#71](https://github.com/zzzhushi/running-gait-analysis/issues/71)) |
| Cross-side aggregation | reported separately | `worst_high`, the worse side |
| Scoring | informational | `scored=True`, `confidence="high"` ([#77](https://github.com/zzzhushi/running-gait-analysis/issues/77)) |
| Uncertainty | reported with every value | not reported ([#76](https://github.com/zzzhushi/running-gait-analysis/issues/76), [#78](https://github.com/zzzhushi/running-gait-analysis/issues/78)) |

## The question this answers

How far ahead of the hip does the foot land at initial contact?

It does **not** answer whether that distance is too large. Measurement and interpretation are
separate contracts with separate evidence requirements; see [Evidence](#evidence).

## Relationship to the published construct

This metric is **modeled after** Lieberman et al. 2015's `d_OH`, not a reproduction of it. Three
substitutions stand between the two, none of them yet validated:

| | Published | Here |
|---|---|---|
| Proximal point | greater-trochanter marker | pose `hip` keypoint |
| Distal point | lateral-malleolus marker | pose `ankle` keypoint |
| Denominator | **standing** trochanter-to-floor length, tape-measured | hip height above an estimated belt line, per clip |
| Contact | force-plate onset (vertical GRF > 20 N) | heuristic ankle-y boundary, `LIFT_FRACTION` |

Calling the output `d_OH` would overstate what it is. It is a video proxy for that construct.

## Definition

At each initial contact, in the sagittal plane:

```
reach       = (ankle_x − hip_x) · facing          pixels, positive = ahead of the hip
value       = reach / (floor_y − hip_y) · 100     percent of hip height above the ground
inclination = atan2(reach, ankle_y − hip_y)       degrees from vertical
```

| Term | Landmark | Status |
|---|---|---|
| Proximal | pose `l_hip` / `r_hip` | **Keypoint proxy.** Offset from the greater trochanter unmeasured. |
| Distal | pose `l_ankle` / `r_ankle` | **Keypoint proxy.** Offset from the lateral malleolus unmeasured. |
| Event | initial contact | Defined in the event contract. Overstride samples it; it does not define it. |
| Denominator | `floor_y − hip_y` at contact | **Provisional.** See below. |
| Floor | median foot-point `y` across detected midstances | **Provisional.** Depends on the uncalibrated midstance detector — a recorded dependency, not an independent measurement. |

### Coordinate frame and sign

Image coordinates: origin **top-left**, `+x` right, `+y` **down**. A point physically higher off
the ground has a *smaller* `y`. The denominator is written `floor_y − hip_y` and is positive
because the floor is below the hip.

`facing` is `+1` when the runner moves toward `+x`, `−1` toward `−x`, so `value` is positive when
the foot is ahead of the hip in the direction of travel, in either side view.

### Why hip height, not limb length

Thigh+shank is anatomically constant, so its variation across a clip is measurement error:

| Denominator | Own CoV | Published construct |
|---|---|---|
| thigh + shank | 5.1 – 6.6 % | none |
| hip → floor | 1.2 – 2.1 % | closest analogue to Lieberman's normalization |
| none (inclination) | — | none for hip→ankle |

A projected limb foreshortens as the leg swings through depth; the belt line does not move.

**This demonstrates repeatability, not accuracy.** A dynamic, per-clip hip-to-floor distance is
not the standing anthropometric length Lieberman measured, and posture, camera tilt, projection,
pose localization and floor estimation all affect it. It stays `Provisional` until measured
against a reference.

**Scope note.** `ctx.leg` remains the denominator for every other `%leg` metric. Changing it
globally is a separate migration and is not in scope here.

## Evidence

Four kinds, tracked separately. A published definition does not prove this code reproduces it,
and a published distribution is not a threshold.

| Question | Status | Basis |
|---|---|---|
| **Construct provenance** — where the definition came from | `Referenced` | Lieberman et al. 2015; Baker et al. 2024 |
| **Implementation validity** — whether this code reproduces it | `Provisional` | landmarks, denominator and contact all unvalidated |
| **Threshold evidence** — whether a cutoff is supported | `Heuristic` | no published cutoff found; Baker 2024 states there is no consensus |
| **Actionability** — whether acting on it improves an outcome | `Unsupported` | Baker 2024 notes systematic reviews lack consensus on braking force and injury |

Scoring requires the first three. Coaching requires all four. Overstride currently has one.

| Constant | Value | Level |
|---|---|---|
| Formula | `reach / hip height` | `Referenced` construct, `Provisional` implementation |
| Floor estimator | median foot `y` at midstance | `Provisional` |
| `good` upper bound | 8 %leg | `Heuristic` |
| `warn` upper bound | 15 %leg | `Heuristic` |
| Aggregation | median per side | `Heuristic` |

## Aggregation

Per side, the **median** across that side's contacts. The two sides are **reported separately and
not collapsed**.

Left and right are measurements of different limbs. A single headline over both describes
neither, and `worst_high` (maximum of the two side medians) is biased upward by construction and
changes which limb it reports between clips of the same runner.

## Known error sources

Measured on the committed fixtures. Listed largest first.

1. **Contact-frame timing dominates.** On `female_overstride` (120 fps), shifting the sampled
   frame ±100 ms moves the value from 38.8 to 8.9 %. Decomposed in
   [#75](https://github.com/zzzhushi/running-gait-analysis/issues/75).
2. **Per-step spread exceeds the good band.** One clip, one extractor: L spread 13.5, R spread
   15.7, against a band 8 wide. This mixes real gait variability with measurement error; the two
   must be reported as different quantities.
3. **Extractor disagreement.** RTMPose and BlazePose differ by a mean of 2.8 on identical
   footage, up to 6.5 on `male_side`.
4. **Landmark proxies.** Neither pose `hip` nor pose `ankle` has been shown to coincide with the
   marker it stands in for. Systematic, unmeasured, and common to every variant of this metric.
5. **Floor estimate assumes a fixed camera and a level belt**, and inherits the midstance
   detector's error.

## Verification channel

The **inclination** form uses two landmarks at one frame and needs no denominator, no leg
measurement and no pixel calibration, so it can be checked with a protractor on an exported
still, independently of the pose model.

It verifies arithmetic and rendering. It is **not** an equivalent expression of overstride, and
must be labelled *hip-to-ankle inclination at initial contact* — never "degrees of overstriding":

- It varies with instantaneous projected hip-to-ankle length, which changes with knee flexion.
- Baker et al. 2024 modeled **thigh, shank and foot segment angles separately**, not a single
  global hip-to-ankle angle.
- Their headline R² figures are **conditional** (94.7–99.4 %), which include participant random
  effects. The **marginal** values — fixed effects only, which is what a general proxy would get
  — are 55.7–61.8 % for IMU-derived angles and 83.0–86.4 % for motion-capture-derived angles.

| Clip | Inclination (rtm / blaze) |
|---|---|
| female_overstride | 15.3° / 16.3° |
| female_side_view | 16.6° / 17.0° |
| female_high_cadence | 6.7° / 6.6° |
| male_side | 13.6° / 9.0° |

## Refusal

Refusal applies to the **runner-level summary**, not to per-step diagnostics. A suppressed
aggregate must never erase the underlying measurements — a refusal that cannot be inspected
cannot be diagnosed.

| Condition | Effect |
|---|---|
| fewer than 4 contacts on a side | no side summary; per-step values remain |
| hip or ankle confidence below threshold at contact | that step marked invalid with a reason; step retained |
| not a side view | no value |
| frame rate below the supported floor | summary downgraded ([#76](https://github.com/zzzhushi/running-gait-analysis/issues/76)) |
| per-step spread above tolerance | aggregate marked unreliable; steps retained |

A single-contact clip must still return a traceable per-step measurement.

## Interpretation

**Overstride is informational. It does not score and does not raise a prescriptive finding.**

Baker et al. 2024: "there is currently no consensus on what qualifies as excessive overstrid[ing]",
and "recent systematic reviews show a lack of consensus on the relationship between braking force
and injury." Until that changes, the feature answers only *what reach was measured*.

Tracked in [#77](https://github.com/zzzhushi/running-gait-analysis/issues/77).

## What would change this contract

- Reference annotations for contact ([#74](https://github.com/zzzhushi/running-gait-analysis/issues/74)) → a measured timing disagreement, on a development clip and a held-out clip.
- Hand-placed landmark references → the keypoint-proxy offsets become measured.
- A criterion signal (force plate, pressure insole, marker-based capture) → the first true accuracy claim. Visual annotation gives *agreement*, not accuracy.
- Evidence for a threshold → overstride could score.

## References

| Source | Contributes |
|---|---|
| [Lieberman et al. 2015, *J Exp Biol* 218:3406](https://journals.biologists.com/jeb/article/218/21/3406/14416/Effects-of-stride-frequency-and-foot-position-at) | Defines `d_OH`: foot-to-hip AP distance at contact ÷ standing trochanter-to-floor length, contact from force-plate onset. Associates it with braking impulse (β=0.89, P=0.0005). The knee-referenced `d_OK` loses significance once `d_OH` is controlled. |
| [Baker et al. 2024, *Sci Rep* 14:6347](https://pmc.ncbi.nlm.nih.gov/articles/PMC10942980/) | Same construct (trochanter → lateral malleolus ÷ leg length). Models thigh, shank and foot segment angles separately; marginal R² 55.7–86.4 %, conditional 94.7–99.4 %. States there is no consensus on excessive overstriding, and that reviews lack consensus on braking force and injury. Shares an author with Lieberman 2015, so the two are not independent. |
| [Damsted et al. 2015](https://pubmed.ncbi.nlm.nih.gov/25920964/) | Reliability of video-based identification of footstrike pattern and of the video time frame at initial contact. Establishes that visual initial-contact frame selection carries nontrivial rater disagreement. *Specific limits-of-agreement figures not independently verified here.* |
| [Normative 2D running kinematics, adolescent runners](https://pmc.ncbi.nlm.nih.gov/articles/PMC11299315/) | Tibia inclination at contact 8.5° ± 3.2°, n=53, 120 fps. A different segment; listed to prevent conflation. |
| [Crowell & Davis 2011](https://pubmed.ncbi.nlm.nih.gov/20889020/) | Shank-angle retraining. Frequently cited for overstride but measures a **different variable**; see `d_OK` above. |
