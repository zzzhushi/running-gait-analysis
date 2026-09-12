# GaitLab technical requirements

## Architecture and sources of truth

```text
video -> pose extractor -> PoseSequence -> confidence filtering -> gait events
      -> registry metrics -> descriptive asymmetry/composites -> AnalysisResult -> UI
```

- Schema and missing-data behavior: `gaitlab/core/schema.py`
- Event algorithm: `gaitlab/core/events.py`
- Metric definitions/formulas: `gaitlab/metrics/definitions/`
- Context equations: `gaitlab/metrics/reference_models.py`
- Generated catalog: `docs/spec/` via `scripts/gen_spec.py`
- Evidence claims: `docs/references.md` and `docs/metric_evidence.md`
- Criterion test contract: `validation/` and `docs/validation_protocol.md`

## Pose sequence

Each frame has 22 canonical points `(x, y, confidence)`. A sequence may contain strictly
increasing timestamps; otherwise elapsed time is derived from fps. All time-domain algorithms
must use `PoseSequence.elapsed()` rather than subtracting frame indices directly.

Before analysis, landmarks below confidence 0.35 become missing. Only gaps bounded by valid
points and no longer than 50 ms are linearly interpolated. Longer/edge gaps remain missing.
Raw pose data is retained in the result for overlay and audit; filtered points feed metrics.

## Event detection

Initial-contact candidates are local maxima of a smoothed median ankle/heel/toe vertical
signal. Candidate events must satisfy minimum temporal spacing and left/right alternation.
Toe-off is emitted only after sustained observed lift; there is no cadence-based fallback.
Stance duration must be below 75% of its local stride. Each event result reports counts,
alternation, warnings, and confidence.

These are kinematic event estimates, not force-contact truth. Event-dependent metrics inherit
event confidence; contact/toe-off timing below 120 fps is low confidence.

## Metric registry

Every `MetricDef` declares formula callback, keypoints, view, event phase, measurement-
confidence tier, evidence tier, interpretation, references, and optional context model.
Definitions are descriptive by default: fixed bands are removed at registration and metrics
cannot contribute to a score or automatic finding.

Metric results should preserve raw values, units, per-side values, sample count, and a 95%
normal-approximation CI of the mean when at least three event/stride observations exist. The
CI describes repeat observations in that clip; it is not a criterion-validity interval.

## Confidence propagation

For relevant metric/event frames:

1. calculate mean landmark confidence and coverage;
2. combine with the definition's measurement tier;
3. add event confidence for event-dependent metrics;
4. apply protocol cap (moderate while unvalidated, low for sub-120-fps timing);
5. report the minimum tier and every component.

Never infer biomechanical confidence from aggregate pose confidence alone.

## Context and normalization

Calibration uses leg length or height only when supplied. Step/stride length requires speed.
Cross-stature outputs include percentage of leg length and dimensionless speed. The published
Malisoux 2023 regressions are implemented exactly and require the predictors for each model;
their result object must include source and “population estimate—not a target.” No missing sex
category may be guessed.

## Asymmetry

Primary output is `(left, right, left-right)` in native units. The optional normalized ratio
is omitted near zero and carries a denominator caveat. No global 5%/10% bands, “worse side,”
or score penalty is allowed. A flag requires a registered, validated, metric-specific MDC.

## Composite patterns

A rule may fire only if all conditions occur in the same side/stride observation, every
component meets the minimum confidence, and the minimum matching-stride count is reached.
Output language must say exploratory co-occurrence and avoid diagnosis, causal force claims,
or prescribed correction. Composite validation is independent of component validation.

## API and storage

The analysis schema retains nullable legacy score/grade columns for database compatibility,
but new results store null values. User context supports height, leg length, age, body mass,
speed, and sex where present. Schema upgrades are additive and non-destructive.

## Verification

```bash
pytest
python scripts/gen_spec.py --check
make test-web
python scripts/evaluate_validation.py validation/paired_measurements.example.csv
```

Tests must cover timestamp use, missing-point interpolation bounds, event non-fabrication,
event-frame confidence, corrected formulas, descriptive output, context equations,
same-stride composites, native-unit asymmetry, spec generation, API validation, and browser
parity. Synthetic data must never be described as criterion validation.
