# Athlete metric guide

This folder defines the long-form help shown when an athlete asks, “What does this
number mean?” It complements the short metric card; it does not replace the metric
registry in `gaitlab/metrics/definitions/`.

The first completed example is [Cadence](cadence.md). Use
[the metric template](metric-template.md) for a single measurement and
[the pattern template](pattern-template.md) for a finding made from several measurements.

## What every page should answer

An athlete should be able to answer these questions without reading implementation
details:

1. What was observed, in plain language?
2. Is this result usable, and what could have distorted it?
3. Does the value need attention, or is “no change” a reasonable choice?
4. If I try something, what is the smallest safe experiment?
5. How can I make a fair comparison next time?
6. What has GaitLab actually validated, and what is still unknown?

## Recommended fields

| Field | Athlete-facing purpose | Required? |
|---|---|---:|
| Name and one-line definition | Identifies the observation without jargon | Yes |
| Value and unit | Explains exactly what the number counts | Yes |
| Supported views | Prevents interpretation from the wrong camera angle | Yes |
| Why it may matter | Connects the observation to mechanics without diagnosing | Yes |
| Result interpretation | Explains low, expected, high, unavailable, and “no action” states | Yes |
| Context that changes it | Names speed, stature, incline, surface, fatigue, footwear, or other relevant inputs | Yes |
| Reference or decision band | States the current band and whether it is a norm, heuristic, or individualized comparison | When used |
| How GaitLab estimates it | Gives a short, inspectable measurement description | Yes |
| Capture requirements | Gives metric-specific instructions and a useful retake path | Yes |
| Confidence breakdown | Separates capture, measurement, interpretation, and action confidence | Yes |
| Known limitations | Names likely failure modes and unsupported populations or conditions | Yes |
| Related measurements/patterns | Prevents one number from carrying an entire coaching conclusion | Yes |
| Suggested experiment | Gives a conservative cue, dose, and success check; permits no change | When justified |
| Stop/escalation guidance | Routes pain or worsening symptoms away from automated coaching | When advice is shown |
| Fair-comparison protocol | Defines what must be matched across sessions | Yes |
| Product validation record | States corpus, reference method, results, failure rate, and gaps | Yes |
| Research summary and sources | Distinguishes external evidence from this product's accuracy | Yes |
| Implementation link | Points at the source file(s) on `main`, not a pinned revision | Yes |

## Page structure: main body vs. appendix

Keep the body athlete-facing; push measurement mechanism and validation detail to an
appendix.

**Main body:** everything in "What every page should answer" above — result
interpretation, why it may matter, experiments, capture guidance, and a short plain-language
trust summary (e.g. "this number is well-measured, but the reference band is a heuristic").
Translate lab terminology as it's introduced rather than assuming the reader knows it.

**Appendix** (a `## Appendix` section at the end): the measurement mechanism ("How GaitLab
estimates it" / "When the pattern is shown"), the full confidence-by-layer table, and the
detailed product-validation record. Link to it from the body wherever the plain-language
trust summary needs to back up a claim, rather than inlining the table.

This keeps a page answerable by a non-technical athlete in one read, while keeping the
rigor available to a reviewer, coach, or clinician one click down. See
[Cadence](cadence.md) for a worked example.

## Confidence is not one field

Do not collapse confidence into a single “high / moderate / low” badge. A metric can be
easy for the app to calculate but weak as a reason to change training.

| Layer | Question | Examples of evidence |
|---|---|---|
| Capture adequacy | Was this clip suitable for this metric? | Correct view, visible landmarks, steady segment, enough valid events |
| Measurement confidence | Did GaitLab estimate the number accurately? | Criterion comparison, held-out error, failure rate, repeatability |
| Interpretation confidence | Do we know what this value means for this athlete? | Population match, speed-matched reference data, sourced thresholds |
| Action confidence | Is the suggested change likely to help the stated outcome? | Intervention evidence, eligibility, adverse-response checks |

Use one of these product-validation labels:

- **Not evaluated:** implemented, but no real-video comparison exists.
- **Software checked:** formulas and synthetic cases are tested; real-world accuracy is unknown.
- **Internally checked:** compared with an independent observation on a development corpus.
- **Held-out validated:** evaluated against a predeclared criterion on athletes and clips not used to tune it.
- **Independently replicated:** a separate team or dataset reproduced the result.

Always state the sample size, population, range, reference method, error summary, and
failure/rejection rate beside a validation label. A regression-test tolerance is not a
measurement-error bound.

## Authoring rules

- Describe movement; do not diagnose a condition, pain source, weak muscle, or injury risk
  from video alone.
- Do not call a reference band “normal,” “safe,” or “optimal” unless the cited evidence and
  product validation support that exact claim for the stated population and context.
- Prefer the athlete's matched baseline over a universal target when repeatability supports
  doing so.
- Separate research performed with laboratory instruments from GaitLab's phone-video
  estimate of a related quantity.
- Say when no change is warranted. An informational page should not manufacture a problem.
- State whether a recommendation is research-derived, expert judgment, or a product
  heuristic.
- Treat pain, sudden loss of function, or neurological symptoms as out of scope for
  automated gait coaching.

## Keeping pages in sync

Implementation facts such as the label, unit, bands, supported views, trigger behavior,
and personalization inputs currently live in each metric definition. Until this guide is
generated from a shared content schema, review those fields against the implementation in
the same change. Narrative evidence, limitations, and athlete guidance should remain
human-reviewed rather than generated from a threshold table.

Link implementation references at `main` (`.../blob/main/gaitlab/...`), not a pinned commit
hash — a hash is a claim about what was true when it was written and silently goes stale the
next time that file changes. A number pulled from running the code (like a validation MAE)
is unavoidably a snapshot; say so in the surrounding sentence instead of pretending a link
keeps it current.
