# Overstride stage 1: frame and timebase evidence (issue #81)

The [manifest](assets/overstride-timebase-manifest.json) names all six committed RTMPose
fixtures and fixes visual sample frames at 120 and 30 fps. The indices are independent of
the contact detector. The [report](assets/overstride-timebase-report.json) is regenerated
from the committed pose JSON and MP4 files. For every clip it records input SHA-256 hashes,
frame counts, first/last times, PTS span, median frame interval, effective and container
frame rates, container duration, coded and display dimensions, rotation, and explicit
checks. It also lists intervals more than 1.5 times the median frame interval;
these are timing discontinuities, **not** proof of a decoder drop.

The committed, reviewer-visible anchors are:

- [120 fps female_high_cadence frame 1408](assets/overstride-timebase-female_high_cadence-frame-1408.png)
- [female_high_cadence frames 1401–1415, with frame 1408 highlighted](assets/overstride-timebase-female_high_cadence-context.png)
- [120 fps female_overstride frame 262](assets/overstride-timebase-female_overstride-frame-262.png)
- [30 fps male_side frame 120](assets/overstride-timebase-male_side-frame-120.png)
- [male_side frames 116–130, with frame 120 highlighted](assets/overstride-timebase-male_side-context.png)

Each is decoded by zero-based frame index and overlaid with that index's pose points.
The footer burns in the index, pose time, current container PTS, frame count, rate, and
validation limit. PNG metadata carries the same identifiers and the video/pose hashes.
None of these frames claims to be a validated contact or a correct landmark placement.
The selected frames are fixed samples for checking index, time, and overlay alignment.
The `female_overstride` anchor deliberately reuses frame 262, which was discussed as a
possible contact frame during the earlier contact-timing investigation on #74/#75. Reusing
that already-inspected index makes the timebase overlay easy to compare with that discussion;
it does not confirm the candidate as contact, and this report contains no reference contact
label. The `male_side` anchor is frame 120, a fixed sample at 4 seconds. In that sequence,
the forward shoe appears above the treadmill at frame 120 and approaches the belt over the
next frames. That observation is also not a contact label.

## Review together

Each context image shows neighboring frames' zero-based indices, stored pose times,
and video PTS. The selected frame has a yellow border. A human reviewer can check whether the
overlaid ankles, heels, and toes follow the shoes and whether the video order matches
the displayed times. Frames 125–130 include the detector's smoothed left-ankle-height
peak at frame 126; that peak is a stance landmark, not the initial-contact label.
For contact annotation, the reviewer should separately mark a
plausible **interval** around the first visible ground contact, note which foot is in
question, and flag occlusion or motion blur. Keep that label separate from this report
so the timebase check cannot be mistaken for detector validation.

The `female_high_cadence` context uses a fixed late-clip window, about 11.68–11.80 s,
where the feet cross and one shoe is partly occluded. Frame 1408 has a yellow border.
This is a visual stress sample for pose/video alignment near the end of the clip; it
does not establish that cadence rises within this window or that the overlaid
landmarks are anatomically correct. Inspect the visible shoe outlines and leg
identity across neighboring frames, and record any suspected pose errors separately
rather than treating this image as a reference landmark label.

## Regenerate and verify

Install development dependencies and `ffmpeg`/`ffprobe`, then run:

```bash
python scripts/gen_overstride_timebase_evidence.py
python scripts/gen_overstride_timebase_evidence.py --check
pytest tests/test_overstride_timebase_evidence.py
```

The test suite regenerates the report and images into a temporary directory. It compares
report bytes and PNG metadata exactly, then allows only small visual differences between
decoder/font versions (at most 1 mean channel level and 0.5% strongly changed pixels).
The CLI `--check` compares pixels exactly on the current host. CI installs `ffmpeg`
explicitly; the test skips only on a local machine without the video tools.

The generator evaluates each check before writing the report. If any check fails, it raises
an error and stops; a failed check is not written as `false` in the committed report. The
report therefore contains passing checks only, while the command output identifies failures.

## When the pose extractor changes

The evidence generator reads saved pose JSON. It does **not** run RTMPose, and it does not
notice a change to extractor code by itself. To check a pose-logic change:

1. Change the extractor or model settings.
2. Re-extract the validation video to a temporary pose file, using the same view and model
   settings as the committed fixture. For example:

   ```bash
   python3 extractor/extract_pose.py tests/data/female_high_cadence.mp4 \
     --view side-right -o /tmp/female_high_cadence.pose.rtmpose.json
   ```

3. Compare the new pose points with the actual video frames, especially the landmarks the
   change is meant to improve. For the arm-angle concern, inspect shoulder, elbow, and wrist
   through the context frames. The overlay only draws the saved model output; it does not
   know whether a point is anatomically correct or whether an arm is hidden by the body.
4. After reviewing the new extraction, put the accepted pose JSON at the fixture path in
   `tests/data/`. Then regenerate the report and images with the command above. The report
   and PNG metadata include hashes of both the video and pose file, so accepted input changes
   are visible in the artifacts.
5. Run `--check` and the evidence test, review the generated diff, and commit the pose fixture
   and evidence together.

If the change is to a metric formula (for example, the elbow-angle calculation) rather than
the pose extractor, this generator is not the test for that change. Keep the same pose
input, run the metric tests, and compare the computed metric with an independently checked
reference measurement.

## When adding a video

The generator does not scan `tests/data/` for new videos. It processes only clips explicitly
listed in `overstride-timebase-manifest.json`. For a new validation clip:

1. Add `tests/data/<id>.mp4` and its extracted
   `tests/data/<id>.pose.rtmpose.json` fixture. `<id>` is the video filename without `.mp4`.
2. Add an entry to the manifest, choosing a fixed `anchor_frame` for the visible overlay.
   Use `null` if the clip should appear in the per-clip report without an anchor. To also
   render neighboring frames, set `context_radius`; `context_after` can override the number
   of frames shown after the anchor.
3. Update the evidence test's explicit expectations in
   `tests/test_overstride_timebase_evidence.py` for any new anchor or context. The test pins
   the current sample indices, so it cannot silently accept an accidental change to them.
   New pose files may record a timestamp provider; make the provenance assertion match the
   new file instead of labeling it as a legacy fixture.
4. Run the generator, inspect the report and PNGs, then run `--check` and the evidence test.
   The generator will stop if frame counts, timestamp agreement, duration, or display
   dimensions fail. Investigate a failed comparison before changing its tolerance.

These checks detect changed contents for clips already in the manifest because their hashes
and generated outputs change. They do not detect an unlisted video, or a changed extractor
that has not been run again to produce new pose JSON. CI runs the evidence test on pull
requests, so it checks that the committed report and images still match the listed inputs.

## What the checks establish

All six pose sequences have the same number of frames as the current video probe and
container declaration. Every stored timestamp is strictly increasing and matches the
corresponding current video PTS within **0.000051 s** (the legacy JSON is rounded to four
decimal places). The video duration agrees with PTS span plus a median frame interval
within one median interval and rounding allowance. Pose display dimensions agree with
the rotation-adjusted video dimensions; the fixed-index PNGs additionally require an
exact-size decoded frame before overlay. This avoids silently resizing a mismatched video.

The old fixture files do **not** record which timestamp provider their original extractor
used. Matching current ffprobe PTS is strong agreement with the present video, but cannot
retroactively prove the extractor used ffprobe or that the pose was produced from these
particular video bytes. New extracts can record provider provenance; these legacy fixtures
must remain labeled “provider unrecorded.” The PNGs support visual alignment review, but
automated pixel equality only guards against renderer drift. A reviewer still needs to
inspect whether the skeleton is plausibly aligned.

## Which pose paths this validates

This report and its PNGs use only the six committed RTMPose pose files named by the
manifest. The generator reads `tests/data/<id>.pose.rtmpose.json`; it does not run RTMPose
again, read the committed BlazePose files, or run the browser extractor. Its automated
checks establish frame-count, timestamp, and dimension agreement for those saved RTMPose
outputs. They do not establish that a landmark is anatomically correct, that left/right
identity stays correct, or that contact and overstride are correct.

There are separate tests for other paths. The real-clip engine tests load committed pose
fixtures when present, including BlazePose fixtures, and compare the tested metric outputs
with each clip's independent ground-truth record. The [browser extraction test](../../tests/browser/test_browser_extraction.py)
runs the browser extractor on `female_high_cadence` and checks frame coverage, cadence,
and every exported timestamp against FFprobe's edit-list-aware presentation PTS.
Its no-edit-list control verifies that the browser does not apply an invented offset;
[a separate pixel test](../../tests/browser/test_editlist_frame_identity.py) pairs
sampled WebCodecs images with the same-index FFmpeg images, independent of their
timestamp labels. The WebCodecs path supports a single normal-rate MP4 media edit,
optionally after a leading empty edit; it explicitly rejects trims and more complex
edit lists until sample selection can preserve frame identity. These checks do not
establish anatomical landmark accuracy or contact timing. The browser has a separate
video decoding path, so passing a Python BlazePose test does not establish browser
frame alignment.

All six clips currently listed in this report have zero rotation metadata, so their report
rows do not exercise the report generator's rotated-dimension branch. Rotation behavior is
already covered separately using the real `rotated_male_side.mp4` derivative: Python tests
check the transformed overlay and OpenCV/FFmpeg frame agreement in
`tests/test_overstride_debug.py`, while `tests/browser/test_rotation.py` checks browser
orientation and transform direction. This PR keeps the report focused on the six canonical
RTMPose fixtures instead of adding a second representation of `male_side`; if a per-clip
rotated report is needed later, add a rotated RTMPose pose fixture and manifest entry.

The next useful validation slice is a side-by-side review of the same source frames from
RTMPose, Python BlazePose, and browser extraction, with visible reference landmarks placed
independently. Compare missing points, left/right swaps, and landmark offsets. Agreement
between pose systems is useful evidence, but is not ground truth by itself. For a new clip
intended to expand metric validation, add its independent measured reference record along
with the video and pose fixtures; the timebase generator alone does not consume that record.

This stage does **not** validate anatomical landmarks, initial-contact timing, the
leg-length denominator, the overstride value, or a clinical threshold. Those belong to
later stages of the [overstride validation plan](../metrics/overstride.md).
