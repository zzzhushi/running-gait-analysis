# [Pattern name]

[One sentence describing the visible movement combination. Use “pattern,” “observation,” or
“combination”—not a diagnosis or an implied tissue/muscle cause.]

## At a glance

| Field | Current GaitLab behavior |
|---|---|
| Supported view | [Side / rear / front] |
| Component observations | [Metric A + metric B + ...] |
| Trigger | [Exact boolean rule in readable language] |
| Minimum component confidence | [Eligibility rule] |
| Priority/severity | [What the product label means; not medical severity] |
| Supersedes | [Individual findings hidden when this clearer pattern is shown] |
| Product-validation status | [Controlled label] |

## What GaitLab observed

[Explain each component result and why the combination is more useful than either result
alone. Include values and units in the rendered version.]

This pattern means: [narrow movement statement].
This pattern does **not** mean: [diagnosis, injury prediction, pain source, weakness/tightness,
or other unsupported inference].

## When the pattern is shown

| Component | Required condition | Why it is included | What can invalidate it |
|---|---|---|---|
| [Metric A] | [threshold/direction] | [role] | [capture/confounder] |
| [Metric B] | [threshold/direction] | [role] | [capture/confounder] |

Additional eligibility:

- [Required view, valid-stride count, tracking confidence, speed/context]
- [Suppression rule for contradictory or missing evidence]
- [Whether personalized component bands are used]

## Other explanations to consider

[List plausible movement or capture explanations without asserting which one is the cause.
Include camera/view artifacts where relevant.]

- [Alternative explanation]
- [Alternative explanation]
- [Reason to retake or inspect the source frames]

## Why it may matter

[Summarize evidence for the combination, or explicitly say when evidence exists only for its
individual components. Do not transfer an association with a lab measurement directly to
GaitLab's 2-D proxy.]

## A small experiment

1. **Setup:** [match speed/view/context]
2. **Cue:** [one simple change]
3. **Dose:** [source or explicit product/expert judgment]
4. **Check:** [which component values/frames and self-reported outcomes to reassess]
5. **Stop or regress if:** [pain, worsening symptoms, excessive effort, loss of control]

[State when no change, a retake, or professional review is the correct next step.]

## Confidence and limitations

Report the weakest relevant layer; do not average confidence badges from the components.

| Layer | Current assessment |
|---|---|
| Capture adequacy | [Are all component metrics eligible in the same clip?] |
| Component measurement confidence | [Per metric, including repeatability] |
| Pattern-rule confidence | [Has this exact combination been evaluated?] |
| Interpretation confidence | [Does evidence support the claimed meaning?] |
| Action confidence | [Does an intervention change the intended outcome?] |

## Current product validation

- **Rule version:** [identifier/revision]
- **Corpus:** [athletes/clips/cases and controls]
- **Reference labels:** [who labeled the pattern, blinding, agreement]
- **Performance:** [sensitivity, specificity, precision, false positives/negatives]
- **Repeatability:** [does the same pattern recur under matched capture?]
- **Outcome validation:** [did the suggested experiment affect the intended outcome?]
- **Gaps:** [populations, severities, views, confounders]

Passing validation for each component metric does not validate the composite rule. Validate
the exact trigger and athlete-facing claim separately.

## Related observations

- **[Metric/pattern]:** [relationship]
- **[Metric/pattern]:** [relationship]

## Research used for interpretation

- [Evidence for component or combination](URL)
- [Intervention evidence, if action is shown](URL)

**Owner:** [name/team]
**Last content review:** [YYYY-MM-DD]
**Next review trigger:** [rule / component / evidence / validation change]
**Implementation reviewed against:** [composite definition files and revision]
