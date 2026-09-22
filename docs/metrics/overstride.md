# Overstride

Engineering measurement contract: what this metric measures, how, and on what evidence. The
athlete-facing explanation of the same metric belongs in `docs/athlete-guide/`; this document is
its upstream source for the measurement and confidence sections.

**This document specifies the target, not current behaviour.** Where the two differ today:

| | Contract | Code today |
|---|---|---|
| Denominator | **undecided** — candidates and decision criterion below | `ctx.leg`, thigh + shank; unchanged until landmark validation settles it |
| Cross-side aggregation | reported separately | `worst_high`, the worse side |
| Scoring | informational | `scored=True`, `confidence="high"` |
| Uncertainty | reported with every value | not reported |

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
| Denominator | **standing** trochanter-to-floor length, tape-measured | thigh + shank, projected and per-frame; candidates under evaluation |
| Contact | force-plate onset (vertical GRF > 20 N) | heuristic ankle-y boundary, `LIFT_FRACTION` |

Calling the output `d_OH` would overstate what it is. It is a video proxy for that construct.

## What the code computes today

Documented so the contract cannot be read as a description of current behaviour, and so a change
can be shown to be a change.

```text
decoded frames + timestamps
        |
        v
pose hip / knee / ankle coordinates + confidence
        |                         |
        v                         v
tracked hip/knee/ankle       ankle-y event detector (LIFT_FRACTION)
        |                         |
        v                         v
projected-leg denominator    detected strike frame
with raw-point provenance         |
        |                         |
        +-----------+-------------+
                    v
       raw per-frame reach-curve artifact
                    |
                    v
       sample artifact at each strike frame
                         |
                         v
               per-side median values
                         |
                         v
        maximum side -> bands -> score / coaching
```

A correct subtraction still produces a wrong result if the wrong source frame, landmark, facing
direction, contact time or denominator entered it.

```text
reach_px(s)       = (ankle_x(s) - hip_x(s)) * facing
projected_leg_px  = median over ALL frames and BOTH sides of
                      distance(hip, knee) + distance(knee, ankle)
step_value(s)     = reach_px(s) / projected_leg_px * 100
side_value        = median(step_value(s) for that side)
headline          = max(left side_value, right side_value)
```

| Contract term | Current implementation | Evidence status |
|---|---|---|
| Proximal point | pose `l_hip` / `r_hip` | proxy; offset from an anatomical marker unmeasured |
| Distal point | pose `l_ankle` / `r_ankle` | proxy; offset from lateral malleolus unmeasured |
| Event | `ev.strikes[side]` | heuristic ankle-y boundary; never compared with a labelled contact |
| Denominator | median projected thigh + shank, px | software-defined; anatomical and projection validity unmeasured |
| Direction | `PoseSequence.facing_sign()` | one sign per clip, inferred from the left foot only |
| Per-step unit | displayed `%leg` | misleading: it is percent of **projected pose-leg length** |
| Within-side aggregation | median | product heuristic; no sample-size or spread rule |
| Cross-side aggregation | `worst_high` (max of side medians) | product heuristic; discards which distribution produced the headline |
| Bands | good ≤ 8, warn ≤ 15 | source not identified |
| Confidence / scoring | `high`, scored | contradicted by integration status `UNVALIDATED` |

Source: [`overstride.py`](../../gaitlab/metrics/definitions/overstride.py),
[`reach.py`](../../gaitlab/core/reach.py), [`ctx.py`](../../gaitlab/metrics/ctx.py),
[`events.py`](../../gaitlab/core/events.py),
[`clipcase.py`](../../tests/integration/clipcase.py).

### Denominator behaviour worth recording

`_leg_length` pools both anatomical sides and every frame into a single median and uses 2-D
projected segment distances that change with out-of-plane motion even though anatomical segment
length is constant. Structurally absent points (`confidence == 0`) are excluded so their `(0,0)`
sentinels cannot become geometry. No higher confidence threshold is applied: choosing and
validating one remains separate work. Every contributing sample retains its frame, timestamp,
side, raw hip/knee/ankle points and derived segment lengths; if no complete observation exists,
the denominator is unavailable rather than replaced with a plausible-looking fallback.

None of this makes the denominator unusable. It establishes that `%leg` is not yet comparable
with a published anthropometric normalization, and that the unit should be named **percent of
projected pose-leg length** until it is.

## Definition

At each initial contact, in the sagittal plane:

```
reach       = (ankle_x − hip_x) · facing          pixels, positive = ahead of the hip
value       = reach / denominator · 100           percent; denominator undecided, see below
inclination = atan2(reach, ankle_y − hip_y)       degrees from vertical
```

### Inspectable reach artifact

`Ctx.reach_curve(side)` exposes the quantity before contact detection samples it. It returns one
`ReachSample` for every source frame and identifies the side, frame index, timestamp, facing and
processing state (`raw`). Each sample contains:

- raw hip, ankle, heel and big-toe `(x, y, confidence)` points;
- the explicitly derived `foot_midpoint_proxy`;
- signed pixel and normalized-percent readings for ankle, heel, toe and midpoint;
- separate refusal reasons for unavailable pixel geometry and unavailable normalization;
- hip-to-ankle inclination and its refusal reason; and
- the exact `Denominator`, including method and every raw hip/knee/ankle observation that fed it.

The production metric samples `ankle_reach.pct` from this same curve at each detected strike; it
does not maintain a second copy of the formula. Isolation tests inject hand-computed geometry and
a sentinel curve, while the committed `female_overstride` fixture demonstrates the complete
inspection path on recorded pose data.

This artifact is raw: it contains no smoothing or interpolation. It makes pose localization,
denominator inputs and contact-frame selection inspectable; it does **not** validate their
accuracy, choose a confidence threshold above structural presence, or establish that sub-frame
interpolation is reliable.

| Term | Landmark | Status |
|---|---|---|
| Proximal | pose `l_hip` / `r_hip` | **Keypoint proxy.** Offset from the greater trochanter unmeasured. |
| Distal | pose `l_ankle` / `r_ankle` | **Keypoint proxy.** Offset from the lateral malleolus unmeasured. |
| Event | initial contact | Defined in the event contract. Overstride samples it; it does not define it. |
| Denominator | **undecided** | Candidates and decision criterion below. Currently `ctx.leg`. |
| Floor | median foot-point `y` across detected midstances | Only if a belt-line denominator is chosen. Depends on the uncalibrated midstance detector — a recorded dependency, not an independent measurement. |

### Coordinate frame and sign

Image coordinates: origin **top-left**, `+x` right, `+y` **down**. A point physically higher off
the ground has a *smaller* `y`. Any vertical denominator is written so that it is positive —
`floor_y − hip_y`, not the reverse.

`facing` is `+1` when the runner moves toward `+x`, `−1` toward `−x`, so `value` is positive when
the foot is ahead of the hip in the direction of travel, in either side view.

### The denominator is an open decision

**This contract does not select one.** An earlier draft chose hip height on the basis of lower
variation across the committed fixtures. That reasoning does not hold: low variation is
repeatability, and the question is which quantity the numerator should be divided by.

What is measured so far. Thigh+shank is anatomically constant, so its variation across a clip is
measurement error:

| Candidate | Own CoV | Relation to the published construct |
|---|---|---|
| thigh + shank (`ctx.leg`, current) | 5.1 – 6.6 % | neither the published normalization nor anything else published |
| hip → estimated belt line | 1.2 – 2.1 % | closest analogue, but dynamic and per-clip rather than standing |
| none (report inclination) | — | no published hip→ankle association |

A projected limb foreshortens as the leg swings through depth; the belt line does not move. That
explains the variance difference and says nothing about which is correct.

Against hip→belt-line specifically: Lieberman measured a **standing** anthropometric length with
a tape. A per-frame projected distance is affected by posture, camera tilt, projection, pose
localization and floor estimation, and the floor estimate currently depends on the uncalibrated
midstance detector.

**What would settle it.** Landmark validation
evaluates each candidate against hand-placed landmark references and a measured subject. The
decision criterion is agreement with a reference length, not variance across fixtures. Until
then the metric keeps `ctx.leg` and the value stays `Provisional`.

**Scope note.** `ctx.leg` is the denominator for every other `%leg` metric. Changing it globally
is a separate migration and is not in scope here.

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
| Formula | `reach / denominator` | `Referenced` construct, `Provisional` implementation |
| Denominator choice | undecided | criterion recorded under Open decisions |
| `good` upper bound | 8 %leg | `Heuristic` |
| `warn` upper bound | 15 %leg | `Heuristic` |
| Aggregation | median per side | `Heuristic` |

## Open decisions

Each is a separate choice; "overstride" is not a complete definition until all are specified.
Options are recorded rather than argued so a later decision has a baseline.

| Decision | Options | Status |
|---|---|---|
| Proximal point | same-side pose hip / mid-hip / manually marked trochanter | same-side pose hip is the implementation candidate; mid-hip would hide side-specific tracking error |
| Distal point | ankle / heel / heel-toe midpoint / toe | ankle is the candidate; heel and toe change meaning between strike patterns, so they are debug comparisons |
| Contact event | ankle-y boundary / human-labelled video / force plate or pressure insole | labelled video is the first reference; a criterion signal is the only route to accuracy |
| Denominator | projected thigh+shank / hip-to-belt-line / external standing length / none (inclination) | **open** — see above |
| Sign and coordinates | — | settled; convention recorded above |
| Aggregation | median per side; minimum contacts and spread tolerance | statistic settled; the thresholds must come from validation data, not be written here first |

**Selection principle.** None of these may be chosen using the output of the detector being
evaluated. Picking a distal point because it makes the current strike frames look better would
launder a detector bias into the definition.

## Aggregation

Per side, the **median** across that side's contacts. The two sides are **reported separately and
not collapsed**.

Left and right are measurements of different limbs. A single headline over both describes
neither, and `worst_high` (maximum of the two side medians) is biased upward by construction and
changes which limb it reports between clips of the same runner.

## Known error sources

Measured on the committed fixtures. Listed largest first.

1. **Contact-frame timing dominates.** On `female_overstride` (120 fps), shifting the sampled
   frame ±100 ms moves the value from 38.8 to 8.9 %.
2. **Per-step spread exceeds the good band.** One clip, one extractor: L spread 13.5, R spread
   15.7, against a band 8 wide. This mixes real gait variability with measurement error; the two
   must be reported as different quantities.
3. **Extractor disagreement.** RTMPose and BlazePose differ by a mean of 2.8 on identical
   footage, up to 6.5 on `male_side`.
4. **Landmark proxies.** Neither pose `hip` nor pose `ankle` has been shown to coincide with the
   marker it stands in for. Systematic, unmeasured, and common to every variant of this metric.
5. **A belt-line denominator, if chosen, assumes a fixed camera and a level belt**, and
   inherits the midstance detector's error.

### The reference itself has a floor

Damsted et al. 2015 report 95% limits of agreement of **5 to 12 frames** for identifying the
initial-contact video frame, with footstrike-pattern kappa 0.83–0.88 intra-rater but 0.50–0.63
inter-rater. On `female_overstride` at 120 fps that disagreement alone is worth:

| LoA width | ms | resulting spread |
|---|---|---|
| 5 frames | 42 | 9.1 % |
| 12 frames | 100 | 17.3 % |

Both exceed the 8-wide good band. **Visual annotation cannot validate this metric to band
precision**, at any frame rate — a higher rate samples more finely without making contact
unambiguous to a human. Labels must therefore be intervals rather than frames, and no threshold
claim can rest on visual annotation alone.

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
| frame rate below the supported floor | summary downgraded |
| per-step spread above tolerance | aggregate marked unreliable; steps retained |
| value implausible in sign or magnitude | step flagged; never reported as a good result |

A single-contact clip must still return a traceable per-step measurement.

The sign case is not hypothetical. The good band is open below (`good=(None, 8)`), so a foot
landing far *behind* the hip scores 100. Every real fixture measures between +11.6 and +29.3;
the synthetic demo runs measure −24 and −17 and are reported as good. A value whose sign is
physically implausible indicates a facing or landmark error, not excellent form, and the band
alone cannot distinguish the two.

## Interpretation

**Overstride is informational. It does not score and does not raise a prescriptive finding.**

Baker et al. 2024: "there is currently no consensus on what qualifies as excessive overstrid[ing]",
and "recent systematic reviews show a lack of consensus on the relationship between braking force
and injury." Until that changes, the feature answers only *what reach was measured*.

Removing the unevidenced scoring and coaching is tracked separately from this contract.

## When this becomes a final contract

| Field | Required evidence |
|---|---|
| Proximal and distal points | named points plus measured offsets against independent references |
| Contact | operational definition, reference method, uncertainty interval, and measured detector error |
| Denominator and unit | chosen option with agreement evidence, not fixture variance |
| Per-step output | machine-readable trace back to frame, time and points |
| Aggregation | minimum observations, statistic, spread tolerance, refusal behaviour — from data |
| Supported capture | view, frame rate, camera constraints, and rejection behaviour |
| Interpretation | informational unless a population-appropriate threshold is supported |
| Actionability | no coaching claim without intervention evidence |

A criterion signal — force plate, pressure insole, or marker-based capture — is the only route
to an accuracy claim. Everything reachable from the committed fixtures is *agreement*.

**The overall score needs its own contract.** Nothing here establishes a general rule for when a
metric becomes eligible to affect a score; that is a product-level decision with its own evidence
requirements.

## References

| Source | Contributes |
|---|---|
| [Lieberman et al. 2015, *J Exp Biol* 218:3406](https://journals.biologists.com/jeb/article/218/21/3406/14416/Effects-of-stride-frequency-and-foot-position-at) | 14 experienced runners at 3.0 m/s, 500 Hz motion capture, 1000 Hz force plates; markers at greater trochanters, malleoli, calcaneus, metatarsal heads. Defines `d_OH`: foot-to-hip AP distance at contact ÷ standing trochanter-to-floor length, contact from force-plate onset. Associates it with braking impulse (β=0.89, P=0.0005). The knee-referenced `d_OK` loses significance once `d_OH` is controlled. |
| [Baker et al. 2024, *Sci Rep* 14:6347](https://pmc.ncbi.nlm.nih.gov/articles/PMC10942980/) | Ten recreational runners. Same construct (trochanter → lateral malleolus ÷ leg length). Models thigh, shank and foot segment angles separately; marginal R² 55.7–86.4 %, conditional 94.7–99.4 %. States there is no consensus on excessive overstriding, and that reviews lack consensus on braking force and injury. Shares an author with Lieberman 2015, so the two are not independent. |
| [Damsted et al. 2015](https://pubmed.ncbi.nlm.nih.gov/25920964/) | Reliability of video-based identification of footstrike pattern and of the video time frame at initial contact. Establishes that visual initial-contact frame selection carries nontrivial rater disagreement. *Specific limits-of-agreement figures not independently verified here.* |
| [Normative 2D running kinematics, adolescent runners](https://pmc.ncbi.nlm.nih.gov/articles/PMC11299315/) | Tibia inclination at contact 8.5° ± 3.2°, n=53, 120 fps. A different segment; listed to prevent conflation. |
| [Crowell & Davis 2011](https://pubmed.ncbi.nlm.nih.gov/20889020/) | Shank-angle retraining. Frequently cited for overstride but measures a **different variable**; see `d_OK` above. |
