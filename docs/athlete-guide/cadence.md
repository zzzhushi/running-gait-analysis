# Cadence

Cadence is how many steps you take per minute while running — left and right combined.
GaitLab reports it in **steps per minute (spm)**.

## At a glance

| | |
|---|---|
| Works from | Side or rear-view video |
| Typical efficient range | 170–185 spm |
| GaitLab only flags cadence outside | 160–195 spm |
| Coaching notes appear for | Side-view clips only (rear view shows the number but won't suggest a change) |
| Personalized using | Your leg length or height, plus treadmill speed if you entered it |
| How well-tested is this | Checked against a handful of real running videos so far, not an independent study yet — details in the [appendix](#appendix) |

The displayed range is a coaching guideline, not a rule. There's no requirement to run at
180 spm — your best cadence depends on your speed and body, and experienced runners often
already run near their own efficient rate.

## How to read your result

Read your cadence together with your speed and the rest of your side-view report.

- **Inside the typical range:** GaitLab won't suggest changing anything.
- **Below the range:** the app may suggest trying a small cadence experiment. First check
  whether the clip also shows a longer, reaching step — that's often the more useful thing
  to work on.
- **Above the range:** a high number isn't automatically a problem. GaitLab only flags high
  cadence once you're past 195 spm (or your personalized version of it), not for every value
  above the typical range.
- **Missing or doesn't look right:** retake the clip rather than trusting the number.

Your personal range shifts a bit based on your height/leg length and treadmill speed —
shorter runners and faster running both shift it higher. That shift follows the *direction*
research supports, but the exact numbers are GaitLab's own heuristic, not a proven formula.

Don't compare cadence from an easy run to cadence from a sprint and read the difference as a
change in form — speed is usually what's actually different.

## Why cadence may matter

At a given speed, taking quicker steps means each step is shorter. Studies have found that a
modest increase in cadence can reduce how hard your joints get loaded, how hard you brake
into each step, and how much you bounce — which is why cadence is a common tool for changing
how someone runs.

What this **doesn't** mean: that one "correct" cadence exists, that higher is always better,
or that GaitLab can measure your running efficiency from video. A 2022 review of the
research found solid evidence that cadence changes affect mechanics right away, but much
weaker evidence that it prevents injury or improves performance.

## If you want to experiment

If GaitLab suggested a **low-cadence** experiment, treat it as something to try, not a
target to hit exactly.

1. Keep your treadmill speed the same.
2. Aim about **5% above your usual cadence** — a metronome app helps.
3. Run four 30-second intervals at that pace, jogging easy in between.
4. Keep your steps light and quiet; don't force yourself onto your forefoot.
5. Notice how it felt, then film another side-view clip at the same speed and setup to
   compare.

Stop if it causes pain, or if the run feels meaningfully harder than it should. GaitLab
isn't a medical assessment — ongoing pain is worth taking to a clinician who works with
runners.

If GaitLab flagged **high cadence**, first double check it with a longer or clearer clip at
the same speed. There isn't good evidence for a blanket "run slower steps" fix — look at
your step length and how you actually feel before changing anything.

## Capture a usable clip

- Use a fixed, level camera and keep your whole body in frame.
- Film from the side (needed for coaching) or from behind.
- Fill about 60–80% of the frame with your body; good light and fitted clothing help
  tracking.
- Film steady running, after you've settled into your pace — not the first few strides.
- Record at least 4–6 seconds, ideally ten or more full strides per side; shorter clips or
  too few detected steps will trigger a warning.
- Make sure the clip plays back at real speed. A slowed-down export from your phone can make
  GaitLab's per-minute count reflect playback speed instead of how fast you actually ran.

If GaitLab reports poor tracking, too few strides, or a cadence that looks doubled or
halved, don't trust the number — re-film instead.

## How much can you trust this number

Cadence is GaitLab's best-measured timing metric — in our own comparisons against real
running video, it's typically been accurate to within a step or two per minute, though it
can be off by a few more in some cases (full numbers in the [appendix](#appendix)).

What's less certain is everything built on top of the raw number: the "typical range" is a
coaching heuristic, the personalized shift is directionally supported but not a validated
formula, and GaitLab hasn't yet been tested broadly enough to know how it performs across
different runners, cameras, or conditions. Treat the cadence value itself as reliable; treat
the coaching band around it as a reasonable starting point, not a verdict.

## Related observations

- **Overstride or reaching:** if your cadence is low, you're reaching out in front on
  landing, and hip extension is limited, GaitLab combines these into one "Overstriding —
  quicken your cadence" finding instead of listing them separately, because raising cadence
  usually resolves the others too.
- **Vertical oscillation (how much you bounce):** if cadence is low and vertical oscillation
  is high, GaitLab combines these into one "Bouncing — drive forward, not up" finding, since
  the fix for both is the same.
- **Contact time:** comes from the same underlying step-timing data as cadence, but GaitLab
  doesn't currently combine them into a joint finding — worth comparing yourself, with less
  confidence in contact time than in cadence.
- **Speed and step length:** GaitLab doesn't combine these with cadence into a joint finding
  either, but looking at them side by side generally tells you more than cadence alone.

## Further reading

These studies inform how GaitLab talks about cadence — they don't validate GaitLab's own
measurement or its exact reference bands.

- [Heiderscheit et al. (2011) — effects of ±5% and ±10% step-rate changes on joint mechanics](https://pubmed.ncbi.nlm.nih.gov/20581720/)
- [Anderson et al. (2022) — systematic review of injury, performance, and biomechanical outcomes](https://pubmed.ncbi.nlm.nih.gov/36057913/)
- [Luedke et al. (2021) — stature, leg length, and self-selected step rate in high-school runners](https://pubmed.ncbi.nlm.nih.gov/30335714/)
- [Van Oeveren et al. (2019) — preferred vs. estimated optimal step frequency outdoors](https://pubmed.ncbi.nlm.nih.gov/31284825/)
- [Van Hooren et al. (2024) — running biomechanics and running economy, a systematic review](https://pubmed.ncbi.nlm.nih.gov/38446400/)

---

## Appendix

This section is for readers who want the measurement mechanism and the validation numbers
behind the summary above — coaches, clinicians, or anyone who wants to check GaitLab's work.

### How GaitLab estimates cadence

GaitLab tracks the vertical motion of both ankles through the clip. It estimates each foot's
stride period from the repeating ankle signal, finds one stable midstance point per stride,
and measures elapsed time between alternating left and right events. If one foot is fully
hidden, it can estimate cadence from the visible foot alone, though tracking both is
preferable.

Real frame timestamps are used when available, including across irregular or dropped
frames. The event search is designed for roughly 60–240 spm. Cadence uses stable midstance
timing rather than the noisier exact first-contact frame.

Current implementation:
[`gaitlab/metrics/definitions/cadence.py`](https://github.com/zzzhushi/running-gait-analysis/blob/main/gaitlab/metrics/definitions/cadence.py),
[`gaitlab/core/events.py`](https://github.com/zzzhushi/running-gait-analysis/blob/main/gaitlab/core/events.py).

### Confidence, by layer

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

### Current product validation

Cadence regression tests cover six real clips from two people — side and rear views and a
bounding drill; see
[`tests/data/README.md`](https://github.com/zzzhushi/running-gait-analysis/blob/main/tests/data/README.md)
for the corpus. Reference values span **102.58–205.13 spm**, with clips lasting
**9.68–14.26 seconds**. Each clip is evaluated with RTMPose and BlazePose pose fixtures.

The reference tool counts discrete vertical body events from raw video pixels and checks the
video timebase and other periodic signals; it does not use GaitLab's pose-derived cadence.
Results on these six selected development clips, against the current cadence implementation
linked above, are:

| Pose source | Mean absolute error | Mean absolute percentage error | Largest absolute error |
|---|---:|---:|---:|
| RTMPose | 0.76 spm | 0.50% | 1.33 spm |
| BlazePose | 1.77 spm | 1.10% | 3.16 spm |

The automated suite allows 2% relative difference for RTMPose and 4% for BlazePose. Those
are regression allowances chosen for the tests, **not** demonstrated error bounds for
athletes. All 12 clip/extractor fixture pairs produced results, but the corpus consists of
selected usable clips and therefore cannot establish a real-world failure rate.

These specific error numbers are a snapshot re-measured against `main` as of this page's
last edit, not a live figure — a later change to event detection could shift them again
without this page noticing.

This corpus was used during development, is not a participant-held-out evaluation, and is
far too small to establish general accuracy. A publishable validation should add more
athletes and capture conditions, predeclare acceptance limits, report absolute error, bias,
limits of agreement and rejection rate, and measure repeatability at matched speeds.
