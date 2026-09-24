# Overstride stage 2: side-view landmark review (issue #82)

This first slice makes the same decoded source frame inspectable beside its RTMPose and
Python BlazePose estimates. These side-by-side sheets are **diagnostic only**: a person
placing independent reference labels must not see model dots beside the source frame.
Separate, unaltered source-frame exports support that task. There are **no labels yet**,
and neither pose estimate is ground truth.

Late `female_high_cadence` examples, chosen independently of the contact detector:

- [Frame 1401](assets/female_high_cadence-landmarks-frame-1401.png)
- [Frame 1408](assets/female_high_cadence-landmarks-frame-1408.png)
- [Frame 1415](assets/female_high_cadence-landmarks-frame-1415.png)

This clip is now an exploratory review sample, **not** an untouched held-out clip for
later accuracy claims. Reserve a different held-out clip before tuning an extractor.

For model-hidden annotation, open only the separate raw frames:

- [Raw frame 1401](assets/female_high_cadence-source-frame-1401.png)
- [Raw frame 1408](assets/female_high_cadence-source-frame-1408.png)
- [Raw frame 1415](assets/female_high_cadence-source-frame-1415.png)

The script draws hip, knee, ankle, heel and big-toe estimates for each side. Blue is the
pose model's left side; orange is its right side. That is **not** a human-confirmed
near/far-to-left/right mapping. Each PNG records the decoded frame index, container PTS,
video hash and pose-file hashes. A pose file with a missing frame, mismatched timestamp,
different display dimensions or rear/front view is refused, rather than silently drawn
on a plausible-looking but incorrect frame. The test regenerates these three PNGs
from the committed inputs and checks their provenance and pixels. Matching the
current video's timestamp grid does **not** retroactively prove which video bytes
the older pose fixtures were originally extracted from.

## Regenerate the example

Install `requirements-dev.txt` and `ffmpeg`/`ffprobe`, then run from the repository root:

```bash
python scripts/review_pose_landmarks.py \
  --video tests/data/female_high_cadence.mp4 \
  --rtmpose tests/data/female_high_cadence.pose.rtmpose.json \
  --blazepose tests/data/female_high_cadence.pose.blazepose.json \
  --frame 1401 --frame 1408 --frame 1415 \
  --output docs/validation/assets
python scripts/review_pose_landmarks.py \
  --video tests/data/female_high_cadence.mp4 \
  --frame 1401 --frame 1408 --frame 1415 \
  --source-only --output docs/validation/assets
pytest tests/test_landmark_review.py
```

The browser extractor is a third, distinct decode-and-inference path. If a full browser
pose export is available, pass `--browser path/to/export.json` to add a fourth panel.
It must pass the same one-to-one PTS check. The three committed PNGs above have **no**
browser column, so they make no claim about browser landmark placement. The browser
extraction tests can save a full JSON run using `GAITLAB_BROWSER_ARTIFACTS`; those runs
need a working browser and the pinned model assets. Browser inference can vary across
runs, so a captured export needs its own provenance before becoming a committed fixture.

In one local Chrome/CPU extraction of `female_high_cadence` on 2026-09-23, the browser
returned all 1,424 frames and its existing cadence test passed, but its timestamps were
about **16.667 ms (two nominal frames) later** than the video's presentation PTS at
every index (range 16.633–16.700 ms after browser rounding). At index 1408, browser
pose time was 11.7583 s versus presentation PTS 11.741667 s. The viewer correctly
refuses this unadjusted browser export.

The offset is explained by this MP4's edit list, not two missing/extra decoded images.
`ffprobe -v trace` reports a video edit-list media start of 256 ticks; the track time
base is 1/15360 s, so the presentation shift is exactly 256/15360 = 1/60 s. Probing
with `-ignore_editlist 1` gives raw frame timestamps 0.016667 s at index 0 and
11.758333 s at index 1408, matching the browser export to its four-decimal rounding.
The browser WebCodecs path constructs each chunk timestamp from MP4Box's raw sample
`cts` and does not apply the track edit list. FFmpeg's default probe applies it.
Both probes and the browser decode reported 1,424 frames. A separate Chrome WebCodecs
pixel check at indices 0, 1, 1401, 1408 and 1415 matched each image best to the
**same-index** FFmpeg image, not its neighbors. This supports an offset in the clock
labels, not a two-frame shift of the image sequence, for this clip and browser run.

For a one-off, non-committed diagnostic comparison, the captured browser timestamps
were checked against every raw timestamp before converting them to presentation PTS;
then its landmarks were drawn at the same indices as the other two estimates. This
did not change production extraction or the committed review artifacts. At frame 1408,
the browser and Python BlazePose estimates differ by 28.5 px at the left heel and
14.8 px at the right heel. This is **model disagreement, not measured error**: browser
MediaPipe Tasks Pose Landmarker heavy and Python's legacy `mp.solutions.pose` are
different inference paths, and no independent human landmark labels exist yet. A
general browser timestamp fix must handle MP4 edit lists rather than subtracting a
hard-coded two frames; until then, the viewer should continue rejecting uncorrected
browser exports.

## Reference-label format, before labels are collected

`gaitlab/debug/landmark_references.py` validates a video-only record. It stores the
source video identity and PTS, not a pose-model hash, so changing an extractor cannot
change the human reference. Each observation records the visual track (`near_leg` or
`far_leg`), anatomical side when known (otherwise `null`), landmark, pixel position,
uncertainty radius, and what was actually seen. A hidden hip centre is an **inference**;
heel and toe points on a shoe are **visible shoe proxies**, not visible bones. Occluded
points can be `unlabelable` with a reason. The record claims `model_layers_visible: false`;
it also records whether the annotator had previously seen a pose overlay. The validator
can check those claims are present, but cannot prove how the annotator worked. Do not
call a previously exposed annotator's points blinded.

For example, one observation in a record may be:

```json
{
  "frame_index": 1408,
  "video_pts_s": 11.741667,
  "track": "near_leg",
  "side": null,
  "landmark": "heel",
  "basis": "visible_shoe",
  "xy": [320.0, 1120.0],
  "uncertainty_radius_px": 4.0
}
```

Those coordinates are an **illustration of the format, not a measured label**. The next
slice is to place actual labels from source-only frames, repeat a blinded sample, and
compute per-landmark offsets, missingness, and side swaps by gait phase and near/far
limb. Do not choose labels by adjusting them to either model's overlay.

## Scope boundary

Overstride is a side-view hip-to-ankle measurement. A rear-view clip cannot validate
that horizontal sagittal distance, so full rear-view landmark accuracy belongs with
rear-view metrics, not this issue. The metric is already registered for side views
only, and this reviewer also refuses rear/front pose inputs. This slice does **not** validate anatomical landmark
locations, the projected-leg denominator, contact timing, overstride values, or any
threshold. Even after labels exist, visual agreement is not criterion accuracy for
anatomy hidden under clothing or shoes.
