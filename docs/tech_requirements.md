# GaitLab — Technical Requirements (annotated reference)

This document distils an external clinical-grade "Gait Analysis Tool — Technical
Specification v1.0" (researched separately) into requirements **scoped to what GaitLab
actually is**: a local, $0, single-session, single-camera 2-D tool built on RTMPose + a
pure-Python stdlib engine.

It is meant to be a **complete reference for everything raised and considered** — including
ideas that are not currently feasible — with **explicit thresholds**, the **current code
status** of each item, and **language templates** the developer can copy. Where a number
appears here it is the real value from the engine (`gaitlab/targets.py`) unless marked
*proposed*.

It complements [`PRD.md`](PRD.md) (product scope) and [`references.md`](references.md)
(evidence sources + per-view capability tables) — read those for citations.

## Table of contents

- [1. Purpose and how to read this doc](#1-purpose-and-how-to-read-this-doc)
- [2. Scope and non-goals](#2-scope-and-non-goals)
- [3. Measurement-uncertainty discipline](#3-measurement-uncertainty-discipline)
- [4. Input and capture requirements](#4-input-and-capture-requirements)
- [5. Pose and keypoints](#5-pose-and-keypoints)
- [6. Gait-cycle phases](#6-gait-cycle-phases)
- [7. Metric catalogue with thresholds](#7-metric-catalogue-with-thresholds)
  - [7.1 Tier A high confidence](#71-tier-a-high-confidence)
  - [7.2 Tier B moderate confidence](#72-tier-b-moderate-confidence)
  - [7.3 Tier C confidence depends on magnitude](#73-tier-c-confidence-depends-on-magnitude)
  - [7.4 Tracking confirmation for specifically requested metrics](#74-tracking-confirmation-for-specifically-requested-metrics)
- [8. Anterior pelvic tilt and why it is hard](#8-anterior-pelvic-tilt-and-why-it-is-hard)
- [9. Pronation and foot mechanics second pass](#9-pronation-and-foot-mechanics-second-pass)
- [10. Rear-view rotations](#10-rear-view-rotations)
- [11. Speed and pace normalization](#11-speed-and-pace-normalization)
- [12. Personalization for sex and stature](#12-personalization-for-sex-and-stature)
- [13. Asymmetry requirements](#13-asymmetry-requirements)
- [14. Composite pattern flags with triggers](#14-composite-pattern-flags-with-triggers)
- [15. Causal mapping likely-cause hypotheses](#15-causal-mapping-likely-cause-hypotheses)
- [16. What it can and cannot suggest or diagnose](#16-what-it-can-and-cannot-suggest-or-diagnose)
- [17. Scoring formula and flag thresholds](#17-scoring-formula-and-flag-thresholds)
- [18. Output and language templates](#18-output-and-language-templates)
- [19. Rejected and deferred with rationale](#19-rejected-and-deferred-with-rationale)
- [20. Internal contradictions in the source spec](#20-internal-contradictions-in-the-source-spec)
- [21. Implementation gap summary](#21-implementation-gap-summary)

---

## 1. Purpose and how to read this doc

Every item carries three tags:

| Tag | Values | Meaning |
|---|---|---|
| **Verdict** | `ADOPT` | Sound and within reach of 2-D single-camera — make it a requirement. |
| | `DEMOTE` | Keep only as a **low-confidence informational** read — not scored, not in the headline. |
| | `REJECT` | Not reliably derivable from one 2-D camera (or needs hardware we don't have). |
| | `DEFER` | Reasonable, but a different / future product (longitudinal, multi-sensor, new UI). |
| **Confidence** | High / Moderate / Low | Realistic reliability from one 2-D view. May be **value-dependent** (see §3). |
| **Status** | Implemented / Partial / Not-yet | Against the current engine. |

Source files referenced throughout: `gaitlab/schema.py` (keypoints), `gaitlab/events.py`
(phases), `gaitlab/metrics.py` (metric maths), `gaitlab/targets.py` (thresholds +
personalization), `gaitlab/asymmetry.py` (L/R), `gaitlab/feedback.py` (findings + scoring),
`gaitlab/analyze.py` (report assembly), `gaitlab/quality.py` (capture checks).

---

## 2. Scope and non-goals

**In scope.** One clip, one camera, one view (`side-left`, `side-right`, `rear`; `front`
treated as rear-like), analysed locally, no account/upload/API key. Output is
**informational coaching**, not diagnosis.

**Non-goals (this product).** Clinical diagnosis of named conditions; force/kinetic estimates;
multi-camera / 3-D; wearable / training-load integration; longitudinal per-runner baselines.
Catalogued with rationale in [§19](#19-rejected-and-deferred-with-rationale) and
[§16](#16-what-it-can-and-cannot-suggest-or-diagnose).

---

## 3. Measurement-uncertainty discipline

`ADOPT` — the spine of the whole doc, applied **uniformly**.

Pose places the hip-joint centre with ~±2–3 cm error → ~±2–4° of angular error; off-axis
cameras add several more degrees. **Therefore:**

- **R3.1** Threshold bands must be **wider than the measurement error**. Three tiers separated
  by 3–5° on a ±2–5° signal is false precision and is forbidden.
- **R3.2** Every metric carries a **confidence level** (High/Moderate/Low) from contributing
  keypoint confidence + view suitability + frame rate, shown next to the value.
- **R3.3 (value-dependent confidence).** Confidence is **not fixed per metric** — it can scale
  with the value. A small reading near the noise floor is reported as a range or "within
  measurement uncertainty"; a large reading well above the floor can be a high-confidence flag.
  *Worked example — pelvic drop:* good band ≤ 6° (`targets.py`); a 2–3° reading is inside the
  ±2–4° error → **Low confidence, report as a range**; a > 6° reading clears the floor →
  **Moderate-to-High confidence, surface as a real flag**. This is exactly the user's point and
  replaces the earlier blanket "pelvic drop is Tier C" framing.
- **R3.4** A metric whose realistic error swamps its *entire* useful range (e.g. medial-arch
  collapse) stays informational-only or is rejected.

> This principle motivated the shipped asymmetry fix: `L 0° / R 3°` produced a spurious "high
> asymmetry" flag because percent-difference explodes near zero. `asymmetry.py` now suppresses
> the flag when **both** sides are individually inside their good band — R3.3 applied to L/R deltas.

**Status:** Partial. Per-keypoint confidence exists and `quality.py` averages it globally, but
metrics do **not** yet emit a per-metric confidence tag (R3.2), and bands are not yet explicitly
keyed to value-dependent confidence (R3.3).

---

## 4. Input and capture requirements

`ADOPT`. Source spec §2 / §16.

| Requirement | Spec asks | GaitLab requirement | Status |
|---|---|---|---|
| Frame rate | ≥ 60 fps | ≥ 60 fps; timing metrics (GCT, duty factor, flight, heel-rise) **flagged approximate < 120 fps** | Partial — `quality.py` info note < 120 fps |
| Resolution | ≥ 1080p | ≥ 1080p recommended | Not enforced |
| Duration / cycles | 20 s, ≥ 10 cycles | ≥ ~4–6 s; warn under ~3 cycles; *proposed:* call ≥ 10 cycles "reliable" | Partial — `quality.py` warns < 6 strikes |
| Framing | 40–70% frame height | ~60–80% frame height | Implemented — `quality.py` |
| Camera level | perpendicular, hip height | level; side-view ground-tilt detected | Partial — `quality.py._ground_slope` |
| Stationary camera | required | pan / overground flagged | Implemented — `quality.py` |
| View | side-L / side-R / rear | same three | Implemented — `schema.VIEWS` |

**Optional inputs that improve interpretation** (all optional; metrics degrade gracefully):

| Field | Effect | Status |
|---|---|---|
| Height and/or leg length | Personalizes cadence target; unlocks cm metrics (VO cm, vertical ratio, stride length) | Implemented (`metrics._calibration`, `targets.personalize`) |
| Treadmill speed (km/h) | Step/stride length; *proposed:* pace-zone normalization (§11) | Partial |
| Sex | Female widens pelvic-drop band (§12) | Implemented |
| **Footwear profile** (max-cushion / stability / neutral / minimal / barefoot + heel drop) | Context note + **confidence reduction** on pronation/foot/ankle metrics for max-cushion; informs strike interpretation (§9) | `ADOPT`, Not-yet |
| **Fatigue state** (fresh / mid-run / fatigued, or minutes-into-run) | Stored as run metadata for future fresh-vs-fatigued comparison (§19); **not** scored within a clip | `ADOPT` (input), Not-yet |

---

## 5. Pose and keypoints

`ADOPT`. Source spec §3.

- **R5.1** Map the spec's keypoints onto GaitLab's canonical set (`schema.KEYPOINTS`).
- **R5.2** Keep per-keypoint confidence, exclude low-confidence keypoints from a metric, and
  propagate the surviving minimum into that metric's confidence (feeds R3.2). **Not-yet.**
- **R5.3** Gait-cycle detection stays landmark-based and pose-source-agnostic (`events.py`).

**Mapping notes:** we use `nose` + a crown `head` keypoint (Halpe-26 idx 17), no ears;
`neck`/`mid_hip` are derived midpoints; RTMPose gives 6 foot points (`heel`, `big_toe`,
`small_toe` per side) — a strength over MediaPipe. We do **not** have ASIS/PSIS (see §8).

---

## 6. Gait-cycle phases

`ADOPT` — **confirmed available.** `events.py` already segments the cycle:

| Phase | How it is found | Field |
|---|---|---|
| Initial contact (strike) | local maxima of smoothed ankle-y per foot | `events.strikes[side]` |
| Toe-off | first frame after a strike where the foot lifts > 25% of its vertical range | `events.toeoffs[side]` |
| Stance | contact → toe-off interval | `events.stance[side]` |
| Mid-stance | midpoint of each stance interval | `events.midstance(side)` |
| Swing | toe-off → next strike (implicit) | derived |

The player already labels "stance · loading", "stance · push-off", and "swing"
(`web/js/screens/analyze.js`).

**Value (why measure phases):**
1. They are the anchors for every per-stride metric (knee angle *at contact*, hip extension
   *at toe-off*, knee flexion *at mid-stance*).
2. **Asymmetry** — left vs right **stance time** and **swing time** are among the most
   clinically meaningful asymmetries (§13); a runner subconsciously favouring a side shortens
   stance on it.
3. They enable the deferred **per-phase video snippets** feature (§19) — loop just stance or
   just swing.

---

## 7. Metric catalogue with thresholds

All thresholds below are the **actual** `targets.py` bands. Status of metric-level confidence
tagging is Not-yet across the board (R3.2). `%leg` = percent of leg length (calibration-free).

### 7.1 Tier A high confidence

ADOPT, score-bearing. Reliable from a single 2-D view.

| Metric | Key | Good | Warn (else BAD) | Status / notes |
|---|---|---|---|---|
| Cadence | `cadence` | 170–185 spm | 160–195 | Implemented; personalized (§12). Highest-confidence metric. |
| Trunk forward lean | `trunk_lean` | 5–12° | 0–16° | Implemented. Trunk vector `mid_hip → neck` vs vertical. |
| Knee flexion at mid-stance | `knee_flexion_midstance` | 38–50° | 28–58° | Implemented. |
| Knee flexion at contact | `knee_flexion_contact` | — (informational) | — | Implemented (per-side); flexion = 180 − interior angle. |
| Overstride (contact point) | `overstride` | ≤ 8 %leg | ≤ 15 | Implemented. `(ankle_x − hip_x)·facing / leg`. See §7.4. |
| Hip extension (peak) | `hip_extension` | ≥ 10° | ≥ 5° | Implemented. Thigh behind vertical, 3-frame window at toe-off. |
| Vertical oscillation | `vertical_oscillation` | ≤ 12 %leg | ≤ 18 | Implemented (%leg High; cm form Moderate, needs scale). |
| Ground contact time | `contact_time` | ≤ 250 ms | ≤ 300 | Implemented; **frame-rate bound** (R3.2). |
| Duty factor | `duty_factor` | ≤ 40% | ≤ 48 | Implemented; frame-rate bound. |
| Knee drive (peak) | `knee_drive` | ≥ 20° | ≥ 10° | Implemented. |
| Elbow angle | `elbow_angle` | 75–105° | 60–120 | Implemented. |
| Head bob (vertical) | `head_drop` | informational | — | Implemented (this session). See §7.4. |

Also implemented, informational: `heel_recovery` (%leg), `flight_time` (ms, fps-bound),
`step_length` / `stride_length` (m, needs speed), `lateral_trunk_sway` (rear, ≤ 8 %leg good).

### 7.2 Tier B moderate confidence

ADOPT as graded-or-informational.

| Spec | Metric | Key | Threshold | Status |
|---|---|---|---|---|
| S10 | Foot-strike pattern | `foot_strike_angle` | report, **don't fault** (heel > 12° is just classification) | Implemented (info card) |
| R3 | Step width | `step_width` | 2–14 %leg good, 0–22 warn | Implemented (rear) |
| R4 | Crossover | `crossover` (bool) | true if feet cross midline | Implemented |
| R9 | Arm crossing midline | `arm_crossover` (bool) | true if > 25% of frames cross | Implemented |
| S11 | Push-off / ankle plantarflexion | *(none)* | *proposed:* shank-vs-foot angle at toe-off | Not-yet |
| S12 | Heel-rise timing (% of stance) | *(none)* | *proposed:* % stance at heel-lift; ≥ 60 fps | Not-yet |
| — | Ankle dorsiflexion at mid-stance | *(none)* | *proposed:* shank-vs-foot angle at mid-stance | Not-yet (see §7.4) |
| — | Big-toe engagement at push-off | *(none)* | *proposed:* big-toe extension vs lesser-toe load | Not-yet (see §9) |

### 7.3 Tier C confidence depends on magnitude

These are **not blanket low-confidence** — per R3.3 their trustworthiness scales with the
value and the view. The rule: **never assign single-degree tiers, and keep small readings out
of the headline score.**

| Spec | Metric | Key | Treatment | Status |
|---|---|---|---|---|
| R1 | Pelvic drop | `pelvic_drop` | good ≤ 6°, warn ≤ 10° (female ≤ 7 / ≤ 11). **< ~4° → Low conf, range; > ~6° → Moderate-High, real flag.** | Implemented (promote per R3.3) |
| R6 | Pronation / heel eversion | `pronation` | good ≤ 8°, warn ≤ 12°. Low confidence; "check shoe wear, not a verdict." | Implemented (already low-conf) |
| R10 | Trunk–pelvis rotation | `trunk_pelvis_rotation` | peak-to-peak shoulder-vs-hip line; low confidence (§10) | Implemented (low-conf) |
| S7 | Anterior pelvic tilt | *(none)* | proxy only — see §8 | Not-yet / largely out of reach |
| S6 | Lumbar compensation | *(none)* | needs a lumbar landmark; inference only | Not-yet |
| R2 | Knee valgus | *(none)* | 2-D rear conflates valgus with femoral rotation | Not-yet |
| R5 | Foot progression angle | *(none)* | foot vector is depth-axis from behind (foreshortened) | Not-yet |
| R7 | Medial arch collapse | *(none)* | needs medial view + navicular landmark | `REJECT` |
| R11 | Pelvic rotation asymmetry | *(none)* | transverse cue below noise from rear 2-D | `REJECT` |

### 7.4 Tracking confirmation for specifically requested metrics

Direct answers to "confirm we track these and what the gaps are":

| Metric | Tracked now? | Where / gap |
|---|---|---|
| **Ankle dorsiflexion** | **No** | Keypoints exist (knee, ankle, big_toe) so it is *computable* — angle of `knee→ankle` vs `ankle→toe` — but no metric computes it. **Gap:** add `ankle_dorsiflexion` at mid-stance + a plantarflexion-at-toe-off read; Moderate confidence (foot keypoints noisy, fps-bound). |
| **Contact point relative to COM (overstride)** | **Yes** | `overstride` (`metrics._compute_side`). **Difference vs spec:** we reference the **hip** (`ankle_x − hip_x`), not a modelled COM projection. Equivalent intent; a true COM proxy (55–57% height) is *proposed* only. |
| **Trunk angle** | **Yes** | `trunk_lean`, good 5–12°. High confidence. |
| **Pelvic tilt** | **Split** | *Lateral* pelvic tilt = **pelvic drop** (`pelvic_drop`, rear) — **tracked**. *Anterior/sagittal* pelvic tilt — **not tracked**, and hard; see §8. |
| **Arm swing across midline** | **Yes** | `arm_crossover` (rear, boolean). Side amplitude via `arm_swing`. |
| **Head bob** | **Yes** | `head_drop` (vertical, side) and `head_lateral_sway` (rear), both %leg, informational — added this session using the `head` keypoint. |

---

## 8. Anterior pelvic tilt and why it is hard

**What ASIS/PSIS are.** The **A**nterior and **P**osterior **S**uperior **I**liac **S**pines are
bony bumps on the front and back of the pelvis that clinicians palpate. The angle of the line
**ASIS → PSIS** relative to horizontal *is* anterior/posterior pelvic tilt (APT). It is the
standard clinical definition.

**Why APT is not "just an angle" for us.** Our pose model outputs **hip-joint centres** — a
single point per side (≈ the hip socket), and in a side view the two hips nearly overlap into
one point. We have **no second point on the pelvis** in the sagittal plane. APT is the rotation
of the pelvis as a rigid body about its own left-right axis; measuring it needs two pelvis
points (ASIS + PSIS, or hip-centre + sacrum). We don't extract either. So there is no pelvis
*segment* to take an angle from.

**How it differs from trunk lean.** They are independent:
- **Trunk lean** = angle of `mid_hip → neck` (the torso) vs vertical. We measure this directly.
- **APT** = orientation of the *pelvis itself*. You can have a forward-tilted pelvis with an
  upright trunk (lordotic posture) or a neutral pelvis with a forward trunk lean. Trunk lean
  tells you nothing reliable about pelvis tilt.

**Verdict.** `DEMOTE`/largely `REJECT` as a *measured angle*; it can only be **inferred** as a
proxy (e.g. lordotic appearance, combined with low hip extension and forward contact). *Is APT
out of scope?* As a clean degree value, yes from one side camera. As a hedged contributing
signal inside a composite (§14) or causal hypothesis (§15), it can be mentioned with **Low
confidence** and a recommendation to confirm clinically (kneeling hip-flexor test).

---

## 9. Pronation and foot mechanics second pass

**Can we see the ankle rolling in / arch collapse with high accuracy? No.** Three hard limits:
the **heel is partly occluded** by the shoe heel-cup; eversion is a **small angle (5–15°) near
the ±2–4° floor**; and it is **rear-view only**. So pronation is inherently Low confidence.

**How to make it *more* accurate (not high, just better):** higher frame rate (≥ 120 fps for
rate/timing); tight or minimal footwear so the rear-foot is visible (a footwear-profile input,
§4, should lower confidence for max-cushion); ensure a true rear view; average over **more
strides** to beat down noise; require the heel keypoint confidence above threshold per frame
(R5.2) before including a stride.

Second pass over the requested pronation sub-metrics:

| Sub-metric | Verdict | Confidence | What it needs / status |
|---|---|---|---|
| Peak calcaneal eversion (flag > 10–12°) | `DEMOTE` | Low | We compute eversion **at contact** (`_pronation`), not the **peak through stance**. *Proposed:* track per-frame eversion across stance and take the peak. |
| Time to peak pronation (late pronation) | `DEMOTE` | Low | Needs per-frame eversion + ≥ 60 fps. Not-yet. |
| Rate of pronation (early collapse → MTSS) | `DEMOTE` | Low | Derivative of eversion; needs high fps. Not-yet. |
| Supination at toe-off (should re-invert) | `DEMOTE` | Low | Eversion at toe-off vs contact. *Proposed.* Not-yet. |
| Navicular drop proxy (arch height) | `REJECT` | — | No navicular/midfoot landmark; needs medial view. |
| Big-toe engagement at push-off | `DEMOTE` → *proposed* | Low-Moderate | We have `big_toe`; could check whether it extends/loads vs lesser toes at toe-off. Side view. Not-yet. |

**Medial arch collapse** specifically: `REJECT` for a real measurement (no landmark, wrong
view). The "too many toes" sign needs a toe-count we can't resolve. Surface arch only as a
hedged note if pronation is high *and* a foot metric corroborates.

---

## 10. Rear-view rotations

**What is accurate from the rear (frontal plane):** pelvic drop (value-dependent, §7.3), step
width, crossover, lateral trunk sway, arm-crossing-midline. These are real because they are
**in-plane** (left-right + up-down) motions the camera sees directly.

**What is not (transverse / rotational):** trunk rotation and pelvic rotation are rotations
about the **vertical axis** — largely **depth-axis** motion that a single rear camera sees only
as small apparent-width changes, below the noise floor. We expose `trunk_pelvis_rotation`
(shoulder-line vs hip-line peak-to-peak) but **labelled low confidence**; pelvic rotation
asymmetry (R11) is `REJECT`.

**Does rotation matter to running?** Yes in principle — excessive trunk-pelvis counter-rotation
wastes energy and signals core/hip-rotator control issues. But because the 2-D rear measurement
is unreliable, the requirement is: **flag only gross, consistent asymmetry**, always with Low
confidence and a "confirm visually" caveat — never a degree-tiered score.

---

## 11. Speed and pace normalization

`ADOPT`. Source spec §4.1.

- **R11.1** Speed-dependent norms (cadence, VO, contact point, trunk lean, hip extension, GCT)
  must adjust for running speed.
- **R11.2** Speed may be **provided** (treadmill km/h) or **estimated** (stride length × cadence);
  when estimated, dependent metrics carry a confidence penalty and the report says so.
- **R11.3** Prefer a **smooth/continuous** adjustment over hard zone edges so a small speed
  error near a boundary doesn't flip many flags (the source spec's 4-zone cliffs are brittle).

**Current behaviour (Partial).** `targets.personalize()` already centres the cadence band on
stature and nudges it with speed:
```
center = 188 − 0.615·(stature_cm − 157)        # ~157cm→188 spm, ~183cm→172 spm
center += 1.2·(speed_kmh − 10)                  # faster → higher
center = clamp(center, 160, 200)
good = (center−7, center+7);  warn = (center−14, center+14)
```
**Gaps:** no pace-zone/continuous normalization for the *other* speed-dependent metrics, and no
speed **estimation** when treadmill speed is absent. Closing R11.2/R11.3 is the main new work.

---

## 12. Personalization for sex and stature

`ADOPT`. Source spec §15. Current behaviour from `targets.personalize()`:

**Female-specific (Implemented).** Pelvic-drop band widens: good `≤ 6° → ≤ 7°`,
warn `≤ 10° → ≤ 11°`, with a note that female norms show a little more pelvic motion (wider
pelvis / larger Q-angle; Ferber 2003 in `references.md`).
*Proposed add:* a female context **note** on knee-valgus findings if/when valgus is added (the
source spec's §15.1 — note, not threshold change).

**Stature-specific (Implemented).** Height or leg length re-centres the **cadence** target (the
formula in §11) — shorter runners get a higher target than the tall-biased "180". Height/leg
also **unlock absolute metrics**: vertical oscillation in cm, vertical ratio, stride length
(`metrics._calibration`, leg length preferred as the px↔cm scale).

**Other optional modifiers** (status): footwear profile → §4/§9 (Not-yet); sex/height/leg/speed
all flow through `analyze(profile=…)` today.

---

## 13. Asymmetry requirements

`ADOPT`. Source spec §5. Computed in `asymmetry.py` over `ASYM_METRICS` as
`AI = |L−R| / mean(|L|,|R|) × 100%`, with universal bands **≤ 5% good, ≤ 10% warn, else bad**.

**Coverage vs the requested list:**

| Requested asymmetry | Tracked? | Key / gap |
|---|---|---|
| Stance / contact time | **Yes** | `contact_time_ms` per side. *Gap:* spec wants a tightened 5–8% trigger (R13.3 below). |
| Step length | **Yes** (calibrated) | `step_length` (needs speed). |
| Pelvic drop | **Yes** | `pelvic_drop`; honour value-dependent confidence (§3). |
| Foot strike | **Yes** | `foot_strike_angle`. |
| Hip extension | **Yes** | `hip_extension`. |
| Arm swing | **Yes** | `arm_swing`. |
| Knee valgus | **No** | valgus metric not computed (§7.3). **Gap.** |
| Vertical impulse | **No** | not derivable cleanly from 2-D (per-leg COM work). **Gap / likely DEFER.** |
| Knee flexion (contact + midstance), overstride, contact time, knee drive, heel recovery, pronation, stride length | **Yes** | already in `ASYM_METRICS`. |

**Requirements:**
- **R13.1** Always report **direction** ("right hip extends 5° more than left"). Implemented
  (`worse_side`).
- **R13.2** **Suppress near-zero false positives** (both sides individually good → no flag).
  Implemented.
- **R13.3** *Proposed:* **tightened absolute triggers** for high-signal metrics — e.g. flag
  stance-time asymmetry at > 5–8%, hip-extension gap at > 5°, pelvic-drop gap at > 3° — instead
  of the single percent band. Not-yet.

---

## 14. Composite pattern flags with triggers

`ADOPT` the concept (**informational patterns**, never named diagnoses — R9.4 / §16). These are
**proposed** (Not-yet; current `feedback.py` is per-metric). Triggers use existing keys + the
real `targets.py` thresholds so they are directly implementable. Each fires only when its
component metrics are at least Moderate confidence.

| Composite | Trigger (all conditions) | Likely cause (hedged) | Cue / drill |
|---|---|---|---|
| **Overstriding / reaching** | `overstride` > 8 %leg **AND** `hip_extension` < 10° **AND** `cadence` below personalized good band | tight hip flexors and/or under-active glutes | "Increase cadence 5–10%; land under your hips." |
| **Sinking at mid-stance** | `knee_flexion_midstance` > 50° **AND** `trunk_lean` > 16° | weak glute max / core control | "Run tall; don't sink into the stance leg." Bridges. |
| **Bouncing** | `vertical_oscillation` > 18 %leg **AND** `cadence` below good band | low cadence redirecting drive upward | "Drive forward, not up; keep the head on a level line." |
| **Stiff / jarring landing** | `knee_flexion_contact` near-straight **AND** `overstride` > 8 %leg **AND** foot-strike = heel | overstride + stiff landing (high loading rate) | "Soft, quiet landings; let the knee give." |
| **Lateral chain (rear)** | `pelvic_drop` > 6° **AND** knee valgus flagged (same side) | weak glute med / glute max | clamshells, hip hikes | `DEFER` — needs knee valgus (§7.3). |

Output rule: surface **at most 3** composites/findings, highest severity first; a composite
outranks its individual component findings.

---

## 15. Causal mapping likely-cause hypotheses

**Yes — we incorporate causal mapping, as coaching-level *hypotheses*, not diagnoses.** The
distinction (and the reason it's allowed): naming a *muscular tendency* tied to a visible
mechanical pattern is what coaches and PTs say out loud and is defensible at Moderate
confidence; naming a *medical condition* (ITBS, labral tear) is not (§16). Every hypothesis is
phrased with confidence-graduated language (§18) and paired with a **self-test** the runner can
do to confirm.

**Hip-flexor-tightness vs glute-max-weakness — the timing heuristic** (derivable from our stance
segmentation, §6):

| Where the fault peaks | Bias toward | GaitLab signals |
|---|---|---|
| **Toe-off / late stance** | tight **hip flexors** | low `hip_extension`, high `overstride`, lordotic/forward-contact appearance |
| **Mid-stance / loading** | weak **glute max** | high `knee_flexion_midstance`, high `trunk_lean`, `pelvic_drop` present |

**Causal lookup (proposed `feedback.py` extension):**

| Finding pattern | Likely tight | Likely weak / unstable | Confidence | Self-test |
|---|---|---|---|---|
| Low hip extension + overstride at toe-off | hip flexors (iliopsoas) | glute max | Moderate | kneeling hip-flexor test |
| Trunk pitch at mid-stance + knee sink + pelvic drop | — | glute max, core | Moderate | bridge test, single-leg squat |
| Pelvic drop > 6° + lateral sway + crossover | adductors / TFL | glute med | Moderate-High (drop > 6°) | single-leg squat, hip hike |
| Delayed/early heel rise + low ankle DF | gastroc / soleus | tibialis anterior | Low (needs ankle DF + heel-rise, Not-yet) | ankle dorsiflexion test |
| High / late pronation | calf | tibialis posterior, foot intrinsics | Low | single-leg balance, toe yoga |

---

## 16. What it can and cannot suggest or diagnose

**Can it diagnose tight hip flexors or weak glutes "with confidence"?** It can **suggest** them
as **likely contributors** (Moderate confidence) and recommend a self-test — it **cannot
confirm** them. Why: confirmation needs a clinical test (kneeling hip-flexor test, bridge test)
or EMG; gait shows the *consequence*, and several causes can produce a similar pattern. So the
output is a hedged hypothesis + a test, never a verdict.

**What separates "can suggest" from "cannot":** a cause is suggestible when (a) it has a
mechanical signature reliably visible in 2-D **and** (b) that signature is reasonably specific.
Muscle tightness/weakness meet this at coaching confidence; structural/joint/neurological
conditions need exam/imaging/EMG.

**Can suggest (coaching-level, hedged) — and current status:**

| Likely cause | Confidence | Status |
|---|---|---|
| Tight hip flexors | Moderate | Partial (hip-extension finding exists; timing logic Not-yet) |
| Weak glute max | Moderate | Partial |
| Weak glute med | Moderate-High (drop > 6°) | Partial (pelvic-drop finding exists) |
| Calf / ankle stiffness | Low | Not-yet (needs ankle DF + heel-rise) |
| Core instability | Low | Not-yet (best with fatigue data) |
| Foot / intrinsic weakness | Low | Partial (pronation, low confidence) |
| Overstriding / bouncing / crossover patterns | Moderate | Implemented (per-metric) / composites Not-yet |

**Cannot diagnose (REJECT — name the condition):** PFPS (runner's knee), IT band syndrome,
patellar tendinopathy, hip labral tear, FAI, SI-joint dysfunction, lumbar/discogenic pain,
hallux rigidus, Achilles tendinopathy, tibial stress fracture, MTSS (shin splints), foot drop,
Parkinsonian gait. For these we may note **mechanical risk factors** (e.g. "crossover + low
cadence increases IT-band strain") but must **not** name or imply the diagnosis, and should
recommend a clinician where a pattern is strong. Foot-drop / neurological signs in particular
are out of scope and warrant a prompt-referral message rather than analysis.

---

## 17. Scoring formula and flag thresholds

`ADOPT` the current simple model; **document it explicitly** so it can be referenced and
guarded.

**Metric-level score (0–100)** — `targets.Target.score()`:
- Inside the **good** band → **100**.
- Outside: `frac = (distance past the good edge) / (warn margin)`, clamped to `[0, 1.5]`;
  `score = 100 − 55·frac`. So the warn edge ≈ 45, and a deep BAD bottoms near ~17.
- Missing / NaN value → 50.

**Overall score (0–100)** — `feedback._score()`:
- `base = mean( Target.score(value) )` over the **view's key list**:
  - **Side:** cadence, trunk_lean, knee_flexion_midstance, overstride, vertical_oscillation,
    contact_time, hip_extension, knee_drive, elbow_angle, duty_factor.
  - **Rear:** cadence, pelvic_drop, step_width, lateral_trunk_sway, pronation.
- `penalty = clamp( mean(flagged L/R diffs) · 0.8, 0, 22 )`.
- `overall = clamp(base − penalty, 0, 100)`; bands A ≥ 85, B ≥ 72, C ≥ 58, D ≥ 42, else E
  (now shown as the **number**, not the letter, per the recent UI change).

**Requirements / guardrails:**
- **R17.1** The headline must **not be dominated by Tier-C noise** (R3.4). **Known gap:** the
  **rear** key list currently includes `pronation` (a Low-confidence metric) — it should be
  removed from the scored set (kept as an informational card). *Action item.*
- **R17.2** **Single-view runs score honestly partial** — a side-only clip can't score
  frontal-plane stability and must say so. Partial today (separate key lists; messaging light).
- **R17.3** `DEFER` the source spec's 4-domain weighted 100-point model: its weights are
  asserted and ~30% rode on Tier-C metrics — it would pump 2-D noise into the headline.

**Explicit per-finding flag triggers (current `feedback.py`)** for reference:

| Finding | Fires when |
|---|---|
| Low cadence | cadence status ≠ good (below personalized band) |
| Overstriding | overstride status warn/bad (> 8 / > 15 %leg) |
| Stiff landing | `knee_flexion_midstance` status bad (< 28 or > 58°) |
| Long ground contact | `contact_time` ≠ good (> 250 ms) |
| Limited hip extension | `hip_extension` ≠ good (< 10°) |
| Limited knee drive | `knee_drive` ≠ good (< 20°) |
| Straight arms | `elbow_angle` > 110° |
| Long duty factor | `duty_factor` bad (> 48%) |
| Bouncing | `vertical_oscillation` bad (> 18 %leg) |
| Heavy heel-strike + overstride | `foot_strike_angle` > 12° **and** `overstride` > 8 %leg |
| Hip drop | `pelvic_drop` ≠ good (> 6° / female > 7°) |
| Crossover | `crossover` true |
| Lateral sway | `lateral_trunk_sway` > 9 %leg |
| Overpronation (estimate) | `pronation` ≠ good (> 8°), low-confidence wording |
| Arm crossover | `arm_crossover` true |
| L/R imbalance | asymmetry status warn/bad (> 5% / > 10%) |

---

## 18. Output and language templates

`ADOPT`. Source spec §10/§11. Max ~3 priority findings; full metric table secondary.

**Confidence-graduated templates** (copy these):

- **High confidence (Tier A, clear band miss):**
  > "Your {metric} is {value}{unit}, {short reading}. {Mechanical consequence}."
  > e.g. "Your cadence is 162 spm, a little low. Low cadence usually pairs with overstriding,
  > which adds braking on every step."

- **Moderate confidence / likely-cause hypothesis (§15):**
  > "Your {pattern} suggests {likely cause} may be contributing. {One-line why}. To check:
  > {self-test}."
  > e.g. "Limited hip drive at push-off suggests tight hip flexors and/or under-active glutes
  > may be contributing. To check: the kneeling hip-flexor test."

- **Low confidence (Tier C / small value, R3.3):**
  > "This is a low-confidence 2-D estimate, so treat it as a prompt to look closer rather than
  > a measurement: {finding}. {What would confirm it}."
  > e.g. the existing pronation copy: "The rear-foot appears to roll inward ~{n}° at contact …
  > treat it as a prompt to check your shoe wear and ankle, not a verdict."

- **Mechanical risk factor (no diagnosis, §16):**
  > "{Pattern} increases load on {structure} with each step. This is informational, not a
  > diagnosis."

- **Refer (strong pattern / neurological sign):**
  > "This pattern is worth review by a clinician familiar with running. Gait video can't
  > assess it fully."

**Prohibited phrasing** (must never appear): "you have {condition}", "this is causing your
pain", "you should stop running", "{condition} diagnosed", or naming any condition in §16's
cannot-diagnose list as a conclusion. *Proposed:* a lightweight lint over generated copy.

**Scope statement (include verbatim or equivalent on every report):**
> "This analysis identifies movement patterns from video and offers informational coaching. It
> is not a medical assessment and does not diagnose injuries or conditions. Running mechanics
> are individual — a deviation from population norms may be fine for your anatomy. Use it as a
> starting point, not a conclusion."

---

## 19. Rejected and deferred with rationale

| Item | Verdict | Why |
|---|---|---|
| Named clinical diagnoses (§16 list) | `REJECT` | Not supportable from single-camera 2-D; crosses the informational boundary. |
| GRF / kinetic estimates from body weight | `REJECT` | Not derivable from 2-D video without a force plate. |
| Medial arch collapse, navicular drop, pelvic rotation asymmetry | `REJECT` | Need a medial/oblique view and landmarks we don't have. |
| Sub-degree pronation / valgus / foot-progression tiers | `REJECT` (as scored) → `DEMOTE` (informational) | Occluded / foreshortened landmarks → false precision. |
| Anterior pelvic tilt as a measured angle | `REJECT` (measured) → `DEMOTE` (inferred) | No ASIS/PSIS or pelvis segment (§8). |
| **Within-clip "fatigue resistance" scoring** | `REJECT` (scoring) | First-third vs last-third of a < 90 s clip is noise, not fatigue. |
| **Fatigue state as an input field** | `ADOPT` | Capture fresh / fatigued / minutes-into-run as run metadata for future comparison (does not affect this clip's score). |
| **Fresh-vs-fatigued longitudinal comparison** | `DEFER` | Needs the history/compare feature; storage (SQLite) and a compare screen already exist to build on. |
| **Per-phase video snippets** (loop just stance / just swing) | `DEFER` (feasible / low effort) | We already segment phases (§6) and the player labels them — add phase-loop / clip-export to `web/js/screens/analyze.js`. Genuinely useful for self-review. |
| Strava/Garmin + acute:chronic workload | `DEFER` | Different product; breaks local/no-account. |
| Longitudinal per-runner baselines, two-video protocols | `DEFER` | GaitLab is single-session by design. |
| Multi-camera / 3-D | `DEFER` | Tracked separately (3-D pose issue, see `PRD.md`). |
| 4-domain weighted 100-point score + composite penalties | `DEFER` | Asserted weights; routes Tier-C noise into the headline (§17). |

---

## 20. Internal contradictions in the source spec

Recorded so we don't reintroduce them:

1. **Precision vs error.** Single-degree tier boundaries (hip extension 5/10/15°, pelvic drop
   3/5/8°) while its own notes admit ±2–5° pose error. (Resolved by R3.1 / R3.3.)
2. **"Not diagnostic" vs §8.** §1.2 disclaims diagnosis; §8 then maps gait to named conditions.
   (Resolved by §16.)
3. **Longitudinal out-of-scope vs fatigue domain.** Lists longitudinal as out-of-scope, then
   scores fatigue from one short clip. (Resolved: input-only, §19.)
4. **Anti-single-number vs single number.** Argues a single score is "a design trap," then
   builds a 100-point composite. (We keep a simple score but guard it — R17.)

---

## 21. Implementation gap summary

| Area | Requirement | File(s) | Status |
|---|---|---|---|
| Uncertainty | Per-metric confidence tag + value-dependent bands (R3.2/R3.3) | `metrics.py`, `targets.py`, `analyze.py` | Not-yet |
| Uncertainty | Near-zero / both-good asymmetry suppression (R3.3/R13.2) | `asymmetry.py` | Implemented |
| Capture | ≥ 10-cycle "reliable" guidance; fps → confidence | `quality.py` | Partial |
| Pose | Confidence propagation into metrics (R5.2) | `metrics.py` | Not-yet |
| Phases | Contact / mid-stance / toe-off / swing | `events.py`, `analyze.js` | Implemented |
| Metrics A | Cadence, trunk lean, knee flexion, overstride, hip ext, VO, GCT, duty, knee drive, elbow, head bob | `metrics.py` | Implemented |
| Metrics B | Ankle dorsiflexion, push-off plantarflexion, heel-rise timing, big-toe engagement | `metrics.py` | Not-yet |
| Metrics C | Pronation peak/rate/timing (second pass, §9); keep low-confidence | `metrics.py` | Partial / Not-yet |
| APT | Inferred-only; never a measured angle (§8) | `feedback.py` | Not-yet (by design) |
| Pace | Pace normalization beyond cadence + speed estimation (R11) | `targets.py`, `metrics.py` | Partial |
| Personalization | Female + stature mods | `targets.py` | Implemented |
| Personalization | Footwear-profile input + confidence effect | input, `metrics.py`, `feedback.py` | Not-yet |
| Asymmetry | Coverage + tightened absolute triggers (R13.3); add knee-valgus when available | `asymmetry.py` | Partial |
| Composites | Informational patterns + triggers (§14) | `feedback.py` | Not-yet |
| Causal | Likely-cause hypotheses + timing heuristic (§15) | `feedback.py` | Partial |
| Scoring | Drop pronation from rear scored set (R17.1); single-view honesty (R17.2) | `feedback.py`, `analyze.py` | Partial |
| Output | Top-3 cap, language templates, prohibited-language lint (§18) | `feedback.py`, `web/` | Partial |
| Feature | Per-phase video snippets | `web/js/screens/analyze.js` | Not-yet (deferred) |
| Feature | Fatigue-state input + future longitudinal compare | input, `server.py`, compare screen | Not-yet (deferred) |
