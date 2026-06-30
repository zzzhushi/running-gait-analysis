# GaitLab — running gait analysis

Understand your running **at a mechanical level**. Feed in a video of yourself running
(side or rear view) and GaitLab draws the moving skeleton over your footage, measures
your mechanics, finds **left/right asymmetries**, and gives **coach-style feedback** —
which to fix first, why, and a drill for it.

Runs **100% on your machine. Free. No account, no upload, no API keys.**

<!-- screens: Library · Player (skeleton overlay + angle arcs + gait timeline) · Report · Trends -->

## Quick start (zero installs)

The app — server, analysis engine, UI, and tests — uses only the Python standard
library, so there is nothing to install to try it:

```bash
python3 server.py          # opens http://localhost:8000 in your browser
```

It starts with three **synthetic demo runs** (a clean side run, an overstriding side
run, and a rear run with hip drop) so you can explore every screen immediately —
no filming required.

Run the engine tests:

```bash
python3 -m unittest discover -s tests
```

## Analyze your own video

Only this step needs third-party packages (RTMPose via `rtmlib`, CPU is fine):

```bash
pip install -r requirements.txt
python3 extractor/extract_pose.py myrun.mp4 --view side-left -o myrun.pose.json
```

Then in the app: **New analysis → choose the pose JSON** (optionally attach the video to
overlay onto) → **Analyze**. Your video never leaves your machine.

**Filming tips**

| | Side view | Rear view |
|---|---|---|
| **What it measures** | Trunk lean, overstride, knee drive, arm posture, vertical oscillation, foot-strike | Pelvic drop, crossover, lateral sway, pronation |
| **Camera height** | Level with mid-hip | Level with mid-hip |
| **Distance** | 3–5 m from treadmill | 3–5 m from treadmill |
| **Frame rate** | 60 fps minimum; 120/240 fps for sharper contact timing | 60 fps is fine (no timing metrics) |
| **Format** | `.mov` or `.mp4`; iPhone slow-mo works | same |

**General:**
- One runner filling most of the frame, contrasting background, steady camera (tripod).
- Keep the camera level — especially for rear view, where a tilted camera directly biases pelvic-drop readings.
- Avoid handheld rail gripping while filming side view — the wrist becomes stationary and the engine sees zero arm swing.

**Treadmill handrails (side view):**
Handrails sit at the same depth as the runner's hips in a 2-D side image. If a rail
overlaps a key joint, pose confidence drops and that keypoint is skipped for those frames.
The metrics most at risk are trunk lean (hip reference), overstride (hip reference), and
arm swing (wrist behind the rail). Two ways to avoid this:

- **Angle the camera 10–15° in front of or behind the treadmill** so the rail sits behind
  the runner in the image rather than crossing their body.
- **Lower or remove the rails** for the filming session if the treadmill allows it.

The engine handles partial occlusion gracefully (medians across strides absorb a few bad
frames) but consistent rail overlap on the hip or wrist will noticeably degrade those metrics.

**Validate the pipeline on a new clip** (quick sanity check before opening the browser):

```bash
# Minimal
python3 validate_run.py myrun.mp4 --view side-left

# With your profile (personalizes norms + unlocks extra metrics)
python3 validate_run.py myrun.mp4 --view side-left \
    --height 158 --leg 76 --speed 12.5 --sex female

# Keep the pose JSON to upload in the browser too
python3 validate_run.py myrun.mp4 --view side-left --keep-json
```

Prints keypoint confidence, strike counts, metric plausibility, asymmetry flags, and a
pass/fail verdict in ~30 seconds — before touching the browser.

**Optional extras**
- *MediaPipe instead of RTMPose* (swappable source): `pip install mediapipe opencv-python`
  then `python3 extractor/extract_pose_mediapipe.py myrun.mp4 --view side-left` — same output format.
- *Plain-English coach summary*: install [Ollama](https://ollama.com) and run `ollama run llama3.2`;
  a button on the report rephrases the findings via that local model. Fully optional — the
  rule-based feedback stays the source of truth and nothing leaves your machine.

## What it measures

Cadence · trunk lean · knee flexion · overstride · **hip extension** · **knee drive** ·
**arm posture/swing** · **duty factor** · foot-strike pattern · vertical oscillation ·
ground contact time (+ **L/R balance**) *(side)* — pelvic drop · **pronation estimate** ·
step width / crossover · lateral trunk sway · **arm crossover** *(rear)* — plus tracked
informationals (heel recovery, step/stride length, flight time, trunk–pelvis rotation) and
**left/right asymmetry** on every bilateral metric, with an overall score/grade. Add your
height and/or treadmill speed and it also reports **vertical oscillation in cm, vertical
ratio, and stride length**. Each finding comes with a plain-language explanation, a
one-line cue, and a corrective drill. See [`docs/PRD.md`](docs/PRD.md) for the full catalog.

**Personalized to you:** add your sex, leg length, height, and pace and the norms adapt —
e.g. a shorter runner gets a higher cadence target instead of the tall-runner-biased
"180" default. Every run also produces a **corrective-exercise plan** (with dosing and
progressions), runs **capture-quality checks** on your footage, and can be **compared
before/after** to see exactly what moved toward target. Filmed both angles? **Combine** a
side and a rear run into one merged report (sagittal + frontal in one place).

## How it works

```
video ─▶ extract_pose.py (RTMPose)   →   normalized pose JSON
                                              │
   POST /api/analyze  ─▶  gaitlab engine  ─▶  AnalysisResult  ─▶  SQLite (local)
                                              │
                          browser UI (Canvas overlay + charts)
```

| Part | Tech | Installs? |
|---|---|---|
| Pose extraction | RTMPose via `rtmlib` (Apache-2.0), CPU | `pip install -r requirements.txt` |
| Analysis engine (`gaitlab/`) | pure Python, stdlib only | none |
| Server (`server.py`) | stdlib `http.server` + `sqlite3` | none |
| UI (`web/`) | vanilla JS ES modules + Canvas + SVG | none (no build step) |

The pose source is **swappable**: anything that emits the normalized format
(`gaitlab/schema.py`) — RTMPose now, MediaPipe later — feeds the same engine.

## Layout

```
gaitlab/            pure-Python analysis engine (schema, events, metrics, asymmetry, feedback)
extractor/          RTMPose video → pose JSON (the one optional pip install)
server.py           local stdlib server: serves the UI + JSON API, SQLite storage
web/                browser UI (vanilla JS + Canvas), no build step
tests/              unittest suite for the engine
docs/PRD.md         product requirements + analysis catalog
```

## Status & limitations

All planned metrics (P0–P2) are implemented and the full pipeline is verified end-to-end
on synthetic runs. **Still needed: validation on a real video clip** (the extractor→engine
data path is unit-tested, but real-world skeleton tracking and angle agreement with a
hand-measured frame haven't been confirmed yet — use `validate_run.py` for that).

It's a training aid, not a medical device. Single-camera 2-D: side-view metrics are
strong; rear-view (pelvic drop, crossover) is good but sensitive to camera tilt — keep
the camera level. Ground-contact timing is bounded by frame rate. See [`docs/PRD.md`](docs/PRD.md)
and [`docs/references.md`](docs/references.md) for details and evidence sources.
