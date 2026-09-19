# [Metric name]

[One sentence in athlete language: what is counted or estimated, when in the stride it is
measured, and the unit. Define left/right or sign conventions here if relevant.]

## At a glance

| Field | Current GaitLab behavior |
|---|---|
| Supported views | [Side / rear / front; near side or both sides] |
| Unit | [Unit and rounding shown to athlete] |
| Reference/decision band | [Values, population, and whether norm / research reference / product heuristic] |
| Coaching eligibility | [When it can produce a finding; when it is display-only] |
| Personalization inputs | [Speed, height, leg length, sex, age, none] |
| Product-validation status | [Not evaluated / software checked / internally checked / held-out validated / independently replicated] |

## How to read your result

[Explain good/expected, low, high, unavailable, and borderline states. Include a legitimate
“no change” outcome. Do not make a diagnosis from a threshold.]

### Context that changes this value

- **Speed:** [effect or unknown]
- **Body dimensions:** [effect or unknown]
- **Surface/incline:** [effect or unknown]
- **Footwear:** [effect or unknown]
- **Fatigue/training task:** [effect or unknown]
- **Other:** [metric-specific context]

[Explain exactly how GaitLab personalizes or normalizes the result. Label unsourced constants
and exact equations as product heuristics.]

## Why it may matter

[Summarize the strongest supported biomechanical relationship first. Then say what has not
been shown: injury prediction, diagnosis, economy, performance, or causation as applicable.]

## If you want to experiment

[Only include this section when an action has appropriate evidence and eligibility.]

1. **Setup:** [matched speed/view/context]
2. **Cue:** [one change, neutral wording]
3. **Dose:** [source-backed dose or explicitly labeled expert/product judgment]
4. **Check:** [observable movement plus comfort/effort outcome]
5. **Stop or regress if:** [pain, loss of control, worsening symptoms, excessive effort]

[State when no change is the better option and when a clinician or coach is more appropriate.]

## How GaitLab estimates it

- **Inputs/landmarks:** [keypoints, scale/calibration, timestamps]
- **Stride phase:** [initial contact / midstance / toe-off / whole stride]
- **Coordinate convention:** [image plane, ground-relative, body-relative, sign]
- **Aggregation:** [per frame -> per stride -> per side -> headline value]
- **Missing-data behavior:** [when unavailable; whether one side can substitute]
- **Displayed precision:** [rounding; do not imply more precision than validation supports]

## Capture a usable clip

- **View and camera placement:** [instructions]
- **Required visibility:** [landmarks/body region]
- **Timing:** [minimum FPS, steady duration, valid strides/events]
- **Scale/calibration:** [height, leg length, treadmill speed, reference object]
- **Common failure modes:** [occlusion, camera tilt/pan, loose clothing, mirror, slow motion]
- **Retake instruction:** [specific action the athlete can take]

## Confidence and limitations

| Layer | Current assessment |
|---|---|
| Capture adequacy | [eligibility and current automated checks] |
| Measurement confidence | [criterion accuracy, repeatability, failures—not a registry label alone] |
| Interpretation confidence | [population/reference fit and threshold provenance] |
| Action confidence | [intervention and outcome evidence] |

### Known limitations

- [Unsupported views, speeds, surfaces, populations, devices, or tasks]
- [Important 2-D or pose-estimation ambiguity]
- [Expected confounders]
- [What GaitLab cannot conclude]

## Current product validation

- **Status:** [controlled label]
- **Engine/model version:** [revision and pose model]
- **Corpus:** [athletes, clips, valid/attempted captures, demographic/context coverage]
- **Reference method:** [manual count, synchronized 2-D/3-D, force plate, wearable, etc.]
- **Range tested:** [values, speeds, views, FPS, devices]
- **Predeclared acceptance limit:** [or “none; exploratory”]
- **Results:** [MAE, bias, limits of agreement, percentiles, classification metrics]
- **Repeatability:** [within-session and between-session, matched conditions]
- **Failure/rejection rate:** [including unusable clips]
- **Known validation gaps:** [held-out subjects, subgroups, edge cases]

Do not describe a test tolerance as measured accuracy. Link the protocol, annotations, and
reproduction command when available.

## Fair comparisons over time

[List the fields that must match: athlete, speed, view, incline, surface, shoes, fatigue,
capture setup, model/engine version. State the smallest detectable change only if measured.]

## Related observations and patterns

- **[Related metric/pattern]:** [what it adds; avoid causal shorthand]
- **[Related metric/pattern]:** [what it adds]

## Research used for interpretation

- [Primary study or systematic review: population, method, result relevant to this page](URL)
- [Reference values: eligible population and measurement method](URL)
- [Intervention evidence, if an action is suggested](URL)

[One sentence stating that external research does not validate GaitLab's implementation.]

**Owner:** [name/team]
**Last content review:** [YYYY-MM-DD]
**Next review trigger:** [implementation change / new validation / scheduled date]
**Implementation reviewed against:** [files and revision]
