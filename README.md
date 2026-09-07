# GaitLab — descriptive 2-D running gait analysis

GaitLab overlays a pose skeleton on a running video and reports transparent 2-D gait
measurements, per-side values, event timing, and confidence. It runs locally or entirely in
the browser; video does not need to leave the device.

**[Try the live demo](https://zzzhushi.github.io/running-gait-analysis/)**

> GaitLab is a research and self-observation tool, not a medical device. It does not diagnose
> injuries, estimate tissue forces, prescribe treatment, or rate a person's gait as good/bad.

## Why the output is descriptive

There is no single authoritative list of universally valid metrics or ideal ranges for an
arbitrary 2-D pose map. What can be recovered depends on the pose model, camera plane, event
algorithm, frame rate, calibration, and population. Reviews of running video analysis report
heterogeneous methods and mostly low-to-moderate criterion validity for many angles.

Accordingly, GaitLab:

- reports values and uncertainty without an overall score or grade;
- does not use universal green/yellow/red target bands;
- separates measurement evidence, pose tracking, gait-event, and protocol confidence;
- excludes low-confidence points and interpolates only bounded gaps up to 50 ms;
- never fabricates a toe-off event;
- presents published population equations as context, explicitly **not a target**;
- reports native-unit left/right differences without a universal asymmetry threshold;
- labels retained composite rules as exploratory same-stride co-occurrences.

See [metric evidence](docs/metric_evidence.md), the [evidence register](docs/references.md),
and the [criterion-validation protocol](docs/validation_protocol.md).

## What it measures

Side view includes cadence; step, stride, contact, flight and swing time; duty factor and
variability; trunk lean; knee flexion at contact, midstance and peak; knee stance excursion;
thigh flexion/extension relative to the trunk; ankle and shank image-plane proxies; forward
foot placement; foot-strike angle; vertical oscillation; heel recovery; and upper-body angles.

Rear/front view includes signed pelvic drop, foot-placement width/crossover, lateral trunk
and head sway relative to the pelvis, rearfoot alignment, shoulder–pelvis frontal obliquity,
and arm crossover. These frontal/transverse-adjacent outputs are screening-level proxies.

Optional height, leg length, speed, age, mass, and a voluntarily provided sex field add
context. Calibrated length, leg-length normalization, dimensionless speed, and published
Malisoux population estimates appear only when their required inputs exist. Sex is never used
as a substitute for stature or bone geometry and does not alter a “healthy” band.

The generated [metric catalog](docs/spec/metrics_table.md) is the exact list emitted by the
registry. It includes evidence tier, measurement confidence, view, phase, and references.

## Capture guidance

| | Side view | Rear view |
|---|---|---|
| Camera | Level with mid-hip, perpendicular to travel | Level with mid-hip, centered behind runner |
| Distance | 3–5 m; runner fills most of frame | 3–5 m; both feet and shoulders visible |
| Frame rate | 60 fps minimum; 120/240 fps for contact timing | 60 fps minimum; faster helps event timing |
| Setup | Fixed camera, level horizon, minimal occlusion | Fixed camera, level horizon, avoid rotation |

Use several complete strides at a steady speed. Rails, loose clothing, occlusion, camera
tilt, and off-axis views reduce confidence. A high pose confidence does not by itself establish
biomechanical validity.

## Run locally

```bash
python3 server.py
```

Open `http://localhost:8000`. The local server includes synthetic demo runs for UI testing;
those demos are not validation data. Results are stored in local SQLite.

For local video extraction with RTMPose:

```bash
pip install -r requirements.txt
python3 extractor/extract_pose.py /path/to/run.mp4 --view side-left -o run.pose.json
```

The browser build uses MediaPipe and runs the Python analysis engine under Pyodide. Pose
sources are swappable as long as they emit the normalized schema in
`gaitlab/core/schema.py`.

## Architecture

```text
video -> 22-point pose sequence -> confidence filtering -> gait events
      -> metric registry -> descriptive asymmetry/composites -> report
```

| Part | Technology |
|---|---|
| Browser pose | MediaPipe Tasks Vision |
| Local pose | RTMPose via `rtmlib` |
| Analysis | Pure Python, standard library at runtime |
| Local server | `http.server` + SQLite |
| UI | Vanilla JavaScript + Canvas/SVG |

## Development and validation

```bash
pytest
python scripts/gen_spec.py --check
make test-web
python scripts/evaluate_validation.py validation/paired_measurements.example.csv
```

Synthetic and golden fixtures test deterministic software behavior and browser parity. They
do **not** establish accuracy. Real accuracy claims require synchronized force/3-D data and
held-out participant evaluation under [the validation protocol](docs/validation_protocol.md).

## Repository map

- `gaitlab/` — schema, events, metric registry, confidence, asymmetry, report assembly
- `extractor/` — optional video-to-pose tools
- `web/` — browser UI
- `tests/` — software tests and deterministic fixtures
- `validation/` — criterion-data contract and example evaluator input
- `docs/` — product contract, technical requirements, evidence, generated metric catalog

## License

MIT © 2026 zzzhushi. Third-party pose/runtime components retain their own licenses: Pyodide
(MPL-2.0), MediaPipe and RTMPose/rtmlib (Apache-2.0).
