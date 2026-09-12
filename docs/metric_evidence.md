# Metric evidence and interpretation

## Source of truth

The executable registry in `gaitlab/metrics/definitions/` is the source of truth for what
the product emits. `scripts/gen_spec.py` renders it into `docs/spec/metrics.yaml` and
`docs/spec/metrics_table.md`; CI checks that the render is current. `docs/references.md`
defines the evidence IDs. The validation dataset and results described in
`docs/validation_protocol.md` will become the source of truth for numerical error once real
synchronized recordings are available.

This resolves the apparent conflict between different research lists:

- a **biomechanics catalog** lists scientifically meaningful constructs;
- a **pose-map catalog** lists geometrically computable proxies;
- a **validated product catalog** contains only constructs shown to meet an error and
  repeatability requirement for this exact model and capture protocol.

Those catalogs are not interchangeable. GaitLab currently reports descriptive pose-map
measurements and labels provisional confidence for each exact implemented proxy. It does not
claim clinical validity.

Evidence tiers are deliberately narrower than the word “validated”: `supported` means a
closely related 2-D construct has relevant literature and the formula has a defensible
definition; `screening` means projection/model error is expected to be material; and
`experimental` means the custom proxy lacks close criterion evidence. None of these labels
means this implementation has passed GaitLab's own criterion-validation protocol.

## Plausibility bounds are not evidence claims

`gaitlab/metrics/plausibility.py` carries a low/high bound for every registered metric.
These are deliberately not the `good`/`warn` target bands this release retired, and they
make no normative claim. A target band judges the runner; a plausibility bound judges the
measurement — a value outside it means the pipeline produced something a running human
cannot have done, so the number is wrong rather than the gait.

Three bases, in descending order of how arguable they are: `definitional` (a duty factor
at or above 50% means the subject is walking), `anatomical` (joint range of motion), and
`literature` (wide ranges from running-biomechanics texts). The literature tier is
sensitivity, not specificity, and is loose on purpose — a cadence of 90 spm says
something is broken, a cadence of 165 says nothing at all.

They exist because a wrong number is otherwise indistinguishable from a real one: the
gait-event anchoring regression this release fixed reported a 67 ms contact time and a
10.5% duty factor at high event confidence with no warning. Out-of-range values annotate
the metric card and raise a single quality warning naming them.

The `literature` tier is grounded in standard running-biomechanics ranges rather than
traced per row to `references.md`. Treat those rows as engineering sanity bounds, not as
registered evidence, until each carries a citation.

## Confidence has four independent parts

| Part | Question |
|---|---|
| Measurement | Is this exact 2-D construct supported by relevant validity literature? |
| Tracking | Were all required landmarks at the relevant event frames visible? |
| Events | Were alternating contacts and observed toe-offs detected consistently? |
| Protocol | Is the view suitable, and is frame rate adequate for timing? |

Card confidence is the lowest available part. “High pose confidence” alone cannot promote
a low-validity frontal/transverse proxy. Until GaitLab has criterion data, protocol caps
final confidence at **moderate**. Contact/toe-off timing is capped **low below 120 fps**.

## What the current 22-point map reports

| Family | Current outputs | Interpretation |
|---|---|---|
| Events and time | contact frames, observed toe-off frames, stance intervals, cadence, step/stride/contact/flight/swing time, duty factor, cadence/contact-time CV | Descriptive. High-speed video is preferred for short intervals. |
| Sagittal joint/segment kinematics | trunk lean; knee flexion at contact/midstance/peak and stance excursion; thigh flexion and extension relative to trunk; shank angle at contact; signed ankle-angle proxies | The strongest 2-D family, but model/protocol specific. “Thigh flexion relative to trunk” replaces mislabeled `knee_drive`; hip extension is no longer thigh angle relative to image vertical. |
| Sagittal foot/placement | foot-strike angle/class, forward ankle placement relative to hip, heel recovery relative to pelvis | Descriptive proxies. `overstride` is not center-of-mass position or braking force. Foot strike is not inherently good/bad. |
| Normalized/spatial | vertical oscillation relative to leg length; calibrated cm oscillation; vertical ratio; step/stride length; step-length/leg-length; dimensionless speed | Calibration and speed dependent. Dimensionless normalization is preferred for stature comparisons. |
| Frontal image-plane | signed swing-side pelvic drop, actual foot-placement width/crossover, lateral trunk/head sway relative to pelvis, shoulder–pelvis frontal obliquity, rearfoot alignment | Screening only. Rearfoot alignment is not dynamic pronation; shoulder–pelvis obliquity is not axial rotation. |
| Upper body | elbow angle, sagittal wrist excursion, rear-view arm crossover | Descriptive; occlusion is common. |

## Constructs not defensible from this map alone

- Ground-reaction force, loading rate, joint moments/power, stiffness, braking impulse, or
  center of mass without an independently validated model and calibration.
- True 3-D hip adduction/internal rotation, knee valgus, transverse pelvic/trunk rotation,
  or foot progression angle from one projection.
- Anterior pelvic tilt without ASIS/PSIS or an equivalent pelvis segment.
- Medial arch/navicular motion without the landmark and appropriate view.
- Muscle weakness/tightness, tissue diagnosis, pain source, injury probability, or a
  corrective exercise inferred from pose alone.

## Sex, stature, and anatomy

Sex-stratified studies show group differences for some variables, but within-group overlap,
speed, and protocol effects prevent universal women/men target bands. The product therefore:

- uses sex only for a published equation that explicitly contains that variable;
- stores height, leg length, age, mass, and speed separately, avoiding sex as a proxy for
  body size or bone geometry;
- exposes Malisoux et al. estimates as **context, not targets**;
- prefers dimensionless or leg-length-normalized values for stature comparisons;
- never changes a “healthy” band based solely on sex.

The Malisoux equations used binary sex categories in the source cohort. The UI must say when
an equation cannot be applied; it must not guess a category for a person.

## Composite patterns

The four retained rules are **exploratory co-occurrence patterns**. They require all
components on the same side and same stride, at least two matching strides, and sufficient
component confidence. Old identifiers remain for saved-run/API compatibility, but labels do
not claim impact, weakness, force, or injury mechanism. They are not scored.

## Range policy

GaitLab has no universal green/yellow/red ranges. A range may be added only when its
provenance records population, task, speed, view, protocol, uncertainty, and intended use.
A clinical decision threshold additionally needs external validation and declared costs of
false positives/negatives. Population equations are labeled “population estimate—not a
target.”
