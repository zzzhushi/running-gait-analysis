# Cadence

Cadence is the total number of left and right steps you take in one minute of running. It
is reported in **steps per minute (spm)**. A left step plus a right step counts as two.

## At a glance

| Field | Current GaitLab behavior |
|---|---|
| Supported views | Side or rear |
| Default reference band | 170–185 spm |
| Default caution band | 160–195 spm |
| Coaching view | Side only; a rear-view result is displayed but does not create a cadence finding |
| Personalization inputs | Leg length or height; treadmill speed additionally when stature is available |
| Product-validation status | **Internally checked** on a small development corpus; not held-out validated |

The displayed band is a **product coaching heuristic**, not a universal definition of good
running and not a proven optimum for an individual athlete. There is no requirement to run
at 180 spm. Preferred cadence varies with running speed and body dimensions, and experienced
runners often choose a cadence close to their own economical rate.

## How to read your result

Read cadence alongside speed and the rest of the side-view report.

- **Inside the displayed band:** GaitLab does not suggest changing cadence.
- **Below the band:** the app may suggest a small cadence experiment. First check whether
  the clip also shows a longer reaching step or another reason to investigate it.
- **Above the band:** a high number is not automatically a fault. The current app creates a
  high-cadence coaching finding only above the upper caution boundary, not for every value
  above the reference band.
- **Unavailable or implausible:** retake the clip rather than training from the number.

The current personalized band shifts with stature and the entered treadmill speed. Shorter
runners and faster running are shifted toward a higher band. The exact equation, clamps, and
band widths are GaitLab heuristics; the cited stature research supports the direction of the
relationship, not this formula or an individual optimum.

Do not compare cadence from an easy run with cadence from a sprint as though the difference
were a form change. Speed is usually the largest context variable to match.

## Why cadence may matter

At a fixed speed, increasing step rate shortens each step. Laboratory studies have found
that modest increases from a runner's preferred cadence can reduce some hip and knee loading
measures, braking impulse, and vertical excursion. That supports cadence as a useful gait-
retraining lever in selected situations.

It does **not** establish that a particular cadence prevents injury, that higher is always
better, or that GaitLab can measure running economy from video. A 2022 systematic review
found much stronger evidence for immediate biomechanical changes than for injury or
performance outcomes.

## If you want to experiment

For a **low-cadence** finding, treat the suggestion as an invitation to test, not an
instruction to chase 180 spm.

1. Keep treadmill speed unchanged.
2. Start about **5% above your usual cadence**, using a metronome if helpful.
3. Try four 30-second intervals with easy running between them.
4. Keep the steps relaxed and quiet; do not force a forefoot landing.
5. Note comfort and effort, then repeat a side-view capture at the same speed and setup.

The four-by-30-second dose is GaitLab's current conservative practice format, not a
clinically validated protocol for every runner.

A useful experiment should improve the movement you intended to change without making the
run feel substantially harder or causing pain. Stop the experiment if pain appears or your
symptoms worsen. GaitLab is not a medical assessment; persistent pain belongs with a
qualified clinician who works with runners.

For a **high-cadence** finding, first confirm the value at the same speed with a better or
longer capture. There is not enough evidence here for a generic instruction to lower
cadence; inspect step length, comfort, and the source video before changing anything.

## How GaitLab estimates cadence

GaitLab tracks the vertical motion of both ankles through the clip. It estimates each
foot's stride period from the repeating ankle signal, identifies one stable midstance point
per stride, and calculates elapsed time between alternating left and right events. When one
foot is fully hidden, it can estimate cadence from the visible foot's stride timing, though
two clearly tracked feet are preferable.

Real frame timestamps are used when available, including across irregular or dropped
frames. The event search is designed for approximately 60–240 spm. Cadence uses stable
midstance timing rather than the noisier estimate of the exact first-contact frame.

## Capture a usable clip

- Use a fixed, level camera and keep your whole body visible.
- Choose a clear side or rear view; side view is required for cadence coaching context.
- Fill roughly 60–80% of the frame height, with good light and fitted clothing.
- Record steady running after you have settled into the chosen speed.
- The current app warns below two seconds or when fewer than six foot strikes are found, and
  its retake guidance asks for about 4–6 seconds. For a comparison, prefer a longer steady
  segment with at least ten complete strides per side.
- Use a clip that plays at real speed. A phone's slowed-down export can make a per-minute
  result reflect playback time instead of the athlete's real running time.

If the app reports poor tracking, too few events, or a visibly doubled/halved cadence, do not
interpret the band. Improve the capture and try again.

## Confidence and limitations

| Layer | Current assessment |
|---|---|
| Capture adequacy | Best with a fixed camera, steady speed, two visible ankles, and enough strides |
| Measurement confidence | GaitLab's strongest timing metric, but evidence is limited to a small internal corpus |
| Interpretation confidence | Moderate at best; speed and stature matter, and the current band/personalization formula is heuristic |
| Action confidence | A modest increase can change mechanics at fixed speed; individual symptom, injury, and performance outcomes remain uncertain |

Known gaps include outdoor or panning footage, substantial occlusion, slow-motion timebases,
very short clips, abrupt speed changes, and athletes outside the limited development sample.
GaitLab has not yet published test–retest noise, device-specific performance, subgroup
performance, a failure rate, or the smallest change it can reliably distinguish between two
captures.

## Current product validation

As of engine revision `aa3f7d7`, cadence regression tests cover six real clips from two
people, including side and rear views and a bounding drill. Reference values span
**102.58–205.13 spm**, with clips lasting **9.68–14.26 seconds**. Each clip is evaluated with
RTMPose and BlazePose pose fixtures.

The reference tool counts discrete vertical body events from raw video pixels and checks the
video timebase and other periodic signals; it does not use GaitLab's pose-derived cadence.
Results on these six selected development clips are:

| Pose source | Mean absolute error | Mean absolute percentage error | Largest absolute error |
|---|---:|---:|---:|
| RTMPose | 0.76 spm | 0.50% | 1.33 spm |
| BlazePose | 1.95 spm | 1.27% | 3.16 spm |

The automated suite allows 2% relative difference for RTMPose and 4% for BlazePose. Those
are regression allowances chosen for the tests, **not** demonstrated error bounds for
athletes. All 12 clip/extractor fixture pairs produced results, but the corpus consists of
selected usable clips and therefore cannot establish a real-world failure rate.

This corpus was used during development, is not a participant-held-out evaluation, and is
far too small to establish general accuracy. A publishable validation should add more
athletes and capture conditions, predeclare acceptance limits, report absolute error, bias,
limits of agreement and rejection rate, and measure repeatability at matched speeds.

## Related observations

- **Overstride/reaching:** cadence can help interpret foot placement, but neither number
  proves the other caused it.
- **Vertical oscillation:** a lower cadence and greater vertical movement can form a useful
  pattern to inspect, once both measurements are validated.
- **Contact time and duty factor:** they share gait-event timing but require more precise
  contact boundaries and should not inherit cadence's confidence.
- **Speed and step length:** together with cadence, these explain more than cadence alone.

## Research used for interpretation

- [Heiderscheit et al. (2011), effects of ±5% and ±10% step-rate changes on joint mechanics](https://pubmed.ncbi.nlm.nih.gov/20581720/)
- [Anderson et al. (2022), systematic review and meta-analysis of injury, performance, and biomechanical outcomes](https://pubmed.ncbi.nlm.nih.gov/36057913/)
- [Luedke et al. (2021), stature, leg length, experience, and self-selected step rate in high-school cross-country runners](https://pubmed.ncbi.nlm.nih.gov/30335714/)
- [Van Oeveren et al. (2019), individual preferred and estimated optimal step frequency during outdoor running](https://pubmed.ncbi.nlm.nih.gov/31284825/)
- [Van Hooren et al. (2024), running biomechanics and running economy systematic review](https://pubmed.ncbi.nlm.nih.gov/38446400/)

These studies inform interpretation and possible experiments. They do not validate
GaitLab's camera-based measurement or its exact reference bands.

**Last content review:** 2026-09-18
**Implementation reviewed against:** `gaitlab/metrics/definitions/cadence.py` and
`gaitlab/core/events.py` at `4b96d2b`
