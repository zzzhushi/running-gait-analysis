# Overstride debug artifacts

This tool answers a narrow but important question:

> Which decoded frame, pose points, event, denominator, and arithmetic produced this
> overstride value?

It does **not** establish that the pose points are anatomically correct, that initial contact
was detected at the right instant, or that the resulting value has clinical meaning. Those
require independent annotations and reference measurements.

## One source of truth

`debug-record.json` is written first. Every CSV and PNG is rendered from fields in that saved
record; rendering code does not import or repeat the overstride formula. PNG metadata carries
the same `record_id`, source-frame identifier, and `%leg` field used by the table. This makes a
displayed value traceable back to one frame record.

The record contains:

- every decoded frame for both sides, not only detected contacts;
- decoded frame index, timestamp, effective FPS, view, and facing sign;
- every pose landmark, plus the hip/ankle/heel/toe measurement subset and confidence;
- the heel/toe midpoint, explicitly labelled as a derived proxy;
- pixel and normalized reach for ankle, heel, toe, and midpoint;
- hip-to-ankle inclination from vertical;
- the projected-leg denominator and every hip/knee/ankle observation behind it;
- original detector contacts, optional user adjustments, and optional reference intervals or
  hand-placed landmarks as separate layers; and
- refusal/validity reasons instead of unexplained missing numbers.

`measurement.production_report.value` is the unrounded result of the registered formula and
aggregator. The report card rounds to three decimals when it serializes, so a record showing
`24.81505325125974` and a card showing `24.815` are the same measurement, not a disagreement.

## Generate a bundle

Install the development dependencies (Pillow renders deterministic PNGs) and ensure `ffmpeg`
is on `PATH` for video decoding:

```bash
pip install -r requirements-dev.txt
python scripts/export_overstride_debug.py \
  --pose tests/data/female_overstride.pose.rtmpose.json \
  --video tests/data/female_overstride.mp4 \
  --output /tmp/female-overstride-debug
```

The directory contains:

```text
debug-record.json        all frames and provenance; authoritative
strikes.csv              one row per detected contact
frames/*.png             annotated contacts or requested frames
traces/*.png             ±10-frame reach curve around each contact
contact-sheet.png        all detected contacts in one image
strips/*.png             ±3 annotated frames around each contact
manifest.json            paths and display-mode settings
```

The source bitmap is decoded by zero-based frame index from the beginning of the stream.
Rendering refuses to continue if its dimensions differ from the pose coordinate system; it
does not resize a mismatched frame and create a plausible-looking but misaligned overlay.

## Blinded annotation and arbitrary navigation

The detector must not anchor a person who is creating reference labels. A strip can therefore
be centered on **any** frame, extend beyond the default detector neighborhood, and hide the
detector layer:

```bash
python scripts/export_overstride_debug.py \
  --record /tmp/female-overstride-debug/debug-record.json \
  --video tests/data/female_overstride.mp4 \
  --output /tmp/female-overstride-blinded \
  --strip-center l:240 --strip-radius 12 --hide-detector
```

This is an artifact-generation interface, not the reference-annotation collection workflow
itself. It provides the non-anchoring primitives that workflow will need.

## Reference and adjustment input

An optional annotations file keeps reference data and user adjustments separate from canonical
detector output:

```json
{
  "references": [
    {
      "side": "l",
      "frame_index": 257,
      "contact_interval_frames": [255, 259],
      "landmarks": {"ankle": [443.7, 901.2]},
      "provenance": "annotator-a/session-1"
    }
  ],
  "adjustments": [
    {
      "side": "l",
      "original_frame_index": 261,
      "adjusted_frame_index": 257,
      "adjusted_timestamp_s": 2.143,
      "provenance": "user/session-1"
    }
  ]
}
```

Pose points are solid blue/orange; hand references are hollow pink. Original detector contacts
are red and adjusted contacts green. An adjustment never replaces or rewrites the original.

## Reading an annotated frame

- The white vertical is the plumb line through the same-side hip.
- The blue horizontal is the signed ankle-to-hip reach represented by the `%leg` label.
- The white diagonal is hip to ankle; its label is degrees from vertical.
- Ankle, heel, and big toe use distinct markers.
- The footer includes the stable record ID, exact source frame, timestamp, value, angle, and
  individual landmark confidences.

The angle provides a manual protractor check of arithmetic and overlay placement. When only pose
points are visible it remains a self-consistency check. A hand-placed reference layer is needed
before it says anything about pose localization.

## Deterministic checks

Tests lock the following horizontal slice:

1. The authored fixture becomes one full-frame record with raw inputs and provenance.
2. The production metric hook selects the forced contact and its record ID.
3. CSV, render plan, PNG text metadata, contact sheet, and report summary reference that same ID
   and numeric field.
4. An indexed diagnostic image source proves frame `n` supplies the background for record `n`.
5. Re-rendering the same record produces byte-identical PNG output.
6. Hiding the detector marker changes only that display layer.

These checks validate record-to-artifact alignment. They deliberately do not validate landmark
accuracy, contact accuracy, or the interpretation bands.

## Committed diagnostic sequence

[`assets/overstride-debug-sequence.png`](assets/overstride-debug-sequence.png) is a nine-frame
contact sheet from zero through positive forward reach; the adjacent
[`assets/overstride-debug-sequence.gif`](assets/overstride-debug-sequence.gif) is the animated
version. Its neutral frame names, undecorated `.source.gif`, and complete machine record live
beside it. Regenerate all four with:

```bash
python scripts/gen_overstride_debug_sequence.py
```

The zero and +20 `%leg` endpoints are taken directly from the canonical
`tests/fixtures/overstride_stage3.json` geometry. Intermediate frames change only the distal x
coordinates; the sequence tests decoding, time, orientation, record identity, and drawing—not
pose extraction, contact detection, or whether any value is good or bad.
