# Initial-contact annotation rule

Rule version: `initial-contact-v1`

This rule governs how a person marks initial contact on a running clip so that two passes,
by the same annotator or different ones, can be compared. It produces **reference
annotations**: agreement with a written procedure. It does not produce accuracy. A criterion
measurement of contact needs a force plate, a pressure insole, or marker-based capture, and
nothing labelled under this rule may be described as ground truth.

## What counts as initial contact

**The first frame in which any part of the shoe touches the ground.**

This is initial contact as clinical video analysis defines it — "the first frame when the foot
hits the ground" — and it is a different event from loading response, "the first frame in
which the runner's weight is being transferred onto the lead leg", marked by shoe deformation.
Loading response comes after contact. This rule labels contact only. (Souza, "An
Evidence-Based Videotaped Running Biomechanics Analysis", *Physical Medicine and
Rehabilitation Clinics of North America*, https://pmc.ncbi.nlm.nih.gov/articles/PMC4714754/.)

The foot keeps moving downward for a few frames after touchdown as the shoe compresses and the
limb takes load. Continued descent therefore does not mean contact has not happened, and the
frame where descent stops is later than contact, not a confirmation of it.

Because a single frame cannot be resolved reliably, the annotator records the **interval** of
frames over which contact plausibly occurred, and nominates one frame within it for
reporting. The interval is the uncertainty. Any figure derived from it must carry that
uncertainty forward rather than treating the nominated frame as exact.

### Specific cases

| Situation | Rule |
|---|---|
| Shadow under the foot | Shadow is not contact. Widen the interval instead of choosing a frame from shadow alone. |
| Foot still descending after the sole reaches the ground | Contact has happened; the descent is loading. Do not move the label to where descent stops. |
| Shoe visibly compressing | Loading response, which follows contact. The contact frame is earlier. |
| Rocker or heavily curved sole | Contact is the first ground touch of any part of the sole, not the heel specifically. |
| Motion blur across several frames | Every blurred candidate frame belongs inside the interval. |
| Partial occlusion of the foot | Label if the ground line and any part of the shoe are both visible; otherwise unlabelable. |
| Foot leaves frame before contact | Unlabelable. |
| Far limb hidden behind the near limb | Unlabelable for that track. |

**Declining to label is a valid outcome.** An annotator who cannot see contact records the
event as unlabelable with a reason. Forcing a frame produces a label indistinguishable from a
confident one, which is worse than recording the ambiguity.

### Lowest foot and descent reversal are not the definition

The lowest point of the heel or ankle, and the frame where their descent stops or their
vertical velocity reverses, are convenient signals and poor rules. All of them fall at or after
loading, so they bound contact from above rather than locating it. Sampling a corpus at
lowest-heel produces values behind the hip at contact, which is not plausible for running. Use
them as late brackets when scanning, never as the label.

## Tracks, not sides

A single side-on camera does not always show which leg is which. Annotators label
`near_foot` and `far_foot` — what the camera can actually distinguish. Mapping a track to a
body side is a separate claim, supplied explicitly wherever labels are adapted for a consumer
that works in sides, and recorded where it is made. Nothing derives it silently.

## Procedure

1. **Reserve the held-out clip first.** Choose it before any development decision consults it,
   and do not open it while building or tuning anything.
2. **Sweep the whole clip.** Coverage comes from windows that tile every frame, never from
   windows centred on detector output: a detector that misses a contact entirely produces no
   window there, so the omission is invisible and the labels agree with the detector on
   coverage by construction.
3. **Keep the detector hidden.** The detector layer stays off for the first pass. The detector
   has a known, consistent direction of error, so an annotator who can see it is anchored
   toward confirming it.
4. **Record per event**: track, contact interval, nominated frame, the instants those frames
   resolve to, visibility (`clear` / `uncertain` / `occluded`), and an unlabelable reason
   where applicable. Timestamps travel with the frames so a label cannot be audited against
   the wrong clock without the record showing it.
5. **Repeat blind.** A second pass, separated in time or by a different annotator, with event
   order randomised so the sequence itself carries no information from the first pass. A
   record is `draft` until two passes exist that were both blinded **and** run with the
   detector hidden, and the repeat was presented in randomised order; only a `complete`
   record may be read as agreement evidence. A pass shown the detector is not blinded, and a
   record claiming both is refused. A complete record names its exact first/repeat pair and
   records how it is independent: distinct annotators, or the same annotator with timestamped
   sessions at least 24 hours apart.
6. **Collect toe-off opportunistically.** It is nearly free once the clip is open and unblocks
   contact time and duty factor, but overstride needs initial contact only, so it never blocks
   this work.

## What an annotator is told

Nothing about what the detector produced, what the metric currently reports, or which
direction an error is suspected to lie. A pass carrying any of that is recorded as not
blinded, and cannot be used to measure detector bias.

## Why intervals, and how wide

Published reliability for identifying the initial-contact video frame spans **5 to 12 frames
at 95% limits of agreement**, from two blinded raters evaluating each video twice across 31
recreational runners: Damsted et al. 2015, *Gait & Posture* 42(1):32-5,
https://pubmed.ncbi.nlm.nih.gov/25920964/.

A higher frame rate gives finer sampling but does not make contact unambiguous to a human:
image quality, contact definition, footwear, occlusion and rater interpretation all remain.
An interval narrower than a few frames on ordinary footage should be treated as suspicious
rather than precise.

## Record format

Labels are stored as `<clip>.contacts.json`, a sibling of the existing ground-truth records.
Each record names the clip, the source video hash, this rule version, and how coverage was
obtained, then carries one entry per pass. `gaitlab/debug/contacts.py` validates the shape and
refuses records that contradict themselves — a nominated frame outside its own interval, or an
unlabelable event that still carries frames.

A pass records its annotator, blinded/detector-hidden state, presentation order and a
timezone-aware completion time. A completed record also carries an `agreement_pair` naming the
first pass, randomized repeat pass, and whether their independence comes from different
annotators or at least 24 hours between sessions. This makes the repeat-pass claim inspectable
rather than inferred from arbitrary pass order.

These fields record what was claimed about a pass; they cannot verify it. A fabricated
completion time, or one person annotating under two names, satisfies every check. The
separation is a heuristic aimed at a repeat being re-read rather than recalled, not a
guarantee of independence, and a record is only as good as the procedure actually followed.

Interval width is derived from the interval, never stored beside it, so the two cannot drift
apart.

## The annotation bundle

`--sweep` writes the view a first pass is done against: source pixels tiling the whole clip,
frames named by index, and a manifest recording the rule version, coverage and source-video
hash. It contains no detector record, contact sheet, reach trace or detector-named file, and
the frames carry no pose, measurement or metric layer. A directory whose filenames were chosen
by the detector announces its predictions without drawing one, which is why hiding the marker
alone is not blinding.
