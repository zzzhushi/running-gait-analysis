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

Filming tips: one runner filling the frame, camera level and steady (a tripod is ideal).
Side view shows overstride / trunk lean / knee drive; rear view shows hip drop /
crossover. 120–240 fps slow-mo sharpens ground-contact timing.

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

v1 is implemented and the full pipeline is verified end-to-end on the synthetic runs.
It's a training aid, not a medical device. Single-camera 2-D: side-view metrics are
strong; rear-view (pelvic drop, crossover) is good but sensitive to camera tilt — keep
the camera level. Ground-contact timing is bounded by frame rate. See the PRD for details.
