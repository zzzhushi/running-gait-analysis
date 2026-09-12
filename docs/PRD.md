# GaitLab product requirements

## Purpose

GaitLab turns a single side or rear running video into transparent, descriptive 2-D
measurements. It is designed to avoid tall/male-biased defaults: body size is represented
directly, sex-stratified research is used only in the context where it was derived, and no
universal “ideal gait” score is presented.

This is a research and self-observation tool, not a medical device, diagnostic system,
injury predictor, or substitute for a clinician.

## Product principles

1. Show the measured geometry and its units before any interpretation.
2. Separate landmark confidence, event confidence, protocol suitability, and published
   measurement validity.
3. Never turn population averages into universal good/bad thresholds.
4. Compare like with like: same speed, view, frame rate, and preferably the same runner.
5. Record height, leg length, age, mass, speed, and a voluntary sex field separately.
6. Use native-unit left/right differences; do not apply a universal asymmetry cutoff.
7. Label unvalidated composites exploratory and require same-side, same-stride evidence.
8. Preserve missingness. Do not fabricate toe-off events or calculate through long
   low-confidence gaps.

## Primary user outcomes

- Inspect pose tracking on the original frames.
- Review gait-event timing and per-metric sample counts.
- See sagittal and frontal image-plane metrics with confidence and evidence labels.
- Compare left and right raw values and signed differences.
- Compare repeated runs under matched conditions without an “improved/regressed” verdict.
- Optionally view a published population estimate when all required context is supplied,
  always labeled as context rather than a target.

## Inputs

Required: pose frames, timestamps or frame rate, image dimensions, and view. Recommended:
stationary camera, level and perpendicular to motion, runner fully visible, at least several
complete strides. Contact timing should use 120 fps or higher.

Optional context: height, leg length, speed, age, body mass, sex and gender as recorded. The
analysis must still function without these fields and must state which contextual outputs
could not be computed.

## Output contract

- `summary.analysis_mode = descriptive_research`
- `summary.overall_score = null` and `summary.grade = null`
- every metric card has `status = info`, evidence level, final confidence, confidence
  components, and sample statistics when available;
- population references are separate objects and say “not a target”;
- asymmetry reports left, right, signed native-unit difference, optional ratio, confidence,
  and metric-specific MDC only when one has been validated;
- events include strikes, observed toe-offs, stance pairs, temporal summaries, counts,
  alternation ratio, warnings, and confidence;
- exploratory composite observations include matching side/stride count and confidence.

## Supported measurement families

The generated catalog at `docs/spec/metrics_table.md` is authoritative. Broadly, the product
supports temporal events, sagittal segment/joint angles, sagittal foot placement, normalized
spatial measures, limited frontal image-plane proxies, and upper-body motion. Detailed
definitions and exclusions are in `docs/metric_evidence.md`.

## Explicit non-goals

- forces, moments, powers, loading rates, stiffness, tissue load, or modeled COM;
- diagnosis, injury probability, causal explanations, or exercise prescription;
- true transverse-plane rotation or 3-D joint angles from one projection;
- sex-specific “healthy” bands or a universal 180-spm recommendation;
- overall quality scores until a defined construct and external validation exist.

## Validation requirement

Synthetic tests establish software behavior only. Claims of accuracy require the synchronized
force/3-D protocol, diverse participant matrix, held-out participant split, failure analysis,
and error reporting in `docs/validation_protocol.md`. Until then, final confidence is capped
at moderate and timing below 120 fps at low.

## Acceptance criteria

- Generated specifications match the registry in CI.
- Low-confidence landmark gaps are excluded; only bounded short gaps are interpolated.
- Timestamped input uses timestamps rather than assuming fixed frame spacing.
- No toe-off-dependent metric is emitted from a fabricated event.
- No product surface presents universal status colors, target bands, score, grade, injury
  claim, or deterministic coaching prescription.
- Same-stride composite and confidence-gating tests pass.
- Python and browser outputs remain fixture-parity compatible.
