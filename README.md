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

## What it measures

Cadence · trunk lean · knee flexion (contact & midstance) · foot-strike pattern ·
overstride · vertical oscillation · ground contact time *(side)* — pelvic drop · step
width / crossover · lateral trunk sway *(rear)* — plus **left/right asymmetry** on every
bilateral metric and an overall score/grade. Each finding comes with a plain-language
explanation, a one-line cue, and a corrective drill. See
[`docs/PRD.md`](docs/PRD.md) for the full catalog, targets, and roadmap.

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
