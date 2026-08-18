# GaitLab — see your running form

Film yourself running, and GaitLab draws the moving skeleton over your footage, measures
your mechanics, finds **left/right asymmetries**, and gives **coach-style feedback** —
what to fix first, why, and a drill for it.

**[▶ Try the live demo](https://zzzhushi.github.io/running-gait-analysis/)** — runs entirely
in your browser. Free, no account, no upload, no API keys. **Your video never leaves your device.**

<!-- TODO(#23): hero image — skeleton + angle arcs over real footage. Deferred: needs a
     clip that's cleared for publishing (the available clip shows bystanders). -->

## What you get

- **A skeleton over your own footage**, with joint-angle arcs and a gait timeline you can
  scrub frame by frame.
- **Mechanics measured, not eyeballed** — cadence, overstride, hip extension, pelvic drop
  and ~20 more, each against a target band personalized to your height, leg length, sex and pace.
- **Left/right asymmetry** on every bilateral metric, so you can see which side is doing less.
- **A ranked fix list** — at most three findings, worst first, each with a plain-language
  explanation, a one-line cue, and a corrective drill with dosing.

<!-- TODO(#23): report screenshot. Blocked on the per-stride sway fix (rear-view lateral
     sway currently reads ~10x high), so a rear report would show a known-wrong number. -->

## Try it

### In your browser (nothing to install)

**[zzzhushi.github.io/running-gait-analysis](https://zzzhushi.github.io/running-gait-analysis/)**

Pick a clip, choose the view, hit **Extract & Analyze**. Pose estimation (MediaPipe) and the
analysis engine (Python, compiled to WebAssembly) both run client-side — nothing is uploaded.

> Bring your own clip: the browser build has no demo runs preloaded, and results live in
> memory only, so a page refresh clears them. For demo data and saved history, use the local
> server below.

### Locally (demo runs + history)

The server, analysis engine, UI, and tests use only the Python standard library, so there is
nothing to install to try it:

```bash
python3 server.py          # opens http://localhost:8000
```

It starts with three **synthetic demo runs** (a clean side run, an overstriding side run, and
a rear run with hip drop) so you can explore every screen immediately — no filming required.
Runs are saved to a local SQLite file, so history, trends, and before/after comparison work.

## Film a good clip

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

<!-- TODO(#23): camera-placement diagram (hand-drawn SVG, no blocker). -->

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

## What it measures

Cadence · trunk lean · knee flexion · overstride · **hip extension** · **knee drive** ·
**arm posture/swing** · **duty factor** · foot-strike pattern · vertical oscillation ·
ground contact time (+ **L/R balance**) *(side)* — pelvic drop · **pronation estimate** ·
step width / crossover · lateral trunk sway · **arm crossover** *(rear)* — plus tracked
informationals (heel recovery, step/stride length, flight time, trunk–pelvis rotation) and
**left/right asymmetry** on every bilateral metric, with an overall score/grade. Add your
height and/or treadmill speed and it also reports **vertical oscillation in cm, vertical
ratio, and stride length**. Each finding comes with a plain-language explanation, a
one-line cue, and a corrective drill.

See [`docs/spec/metrics_table.md`](docs/spec/metrics_table.md) for every metric with its
target bands and confidence, or [`docs/PRD.md`](docs/PRD.md) for the full catalog.

**Personalized to you:** add your sex, leg length, height, and pace and the norms adapt —
e.g. a shorter runner gets a higher cadence target instead of the tall-runner-biased
"180" default. Every run also produces a **corrective-exercise plan** (with dosing and
progressions), runs **capture-quality checks** on your footage, and can be **compared
before/after** to see exactly what moved toward target. Filmed both angles? **Combine** a
side and a rear run into one merged report (sagittal + frontal in one place).

## How it works

```
your video
      │
      ▼  pose estimation  (MediaPipe in-browser, or RTMPose locally)
   pose JSON  (22 canonical keypoints per frame)
      │
      ▼  gaitlab engine  (pure-Python: events → metrics → asymmetry → feedback)
   AnalysisResult
      │
      ▼  browser UI (Canvas overlay + charts)
```

| Part | Tech | Installs? |
|---|---|---|
| Pose (browser) | MediaPipe Tasks Vision, WebAssembly | none |
| Pose (local) | RTMPose via `rtmlib` (Apache-2.0), CPU | `pip install -r requirements.txt` |
| Analysis engine (`gaitlab/`) | pure Python, stdlib only | none |
| Server (`server.py`) | stdlib `http.server` + `sqlite3` | none |
| UI (`web/`) | vanilla JS ES modules + Canvas + SVG | none (no build step) |

**The same Python engine runs both server-side and in the browser** — in the browser it runs
unmodified under Pyodide (WebAssembly). CI runs both against identical fixtures and **fails if
any number disagrees by more than `1e-6`** ([`web/tests/parity.mjs`](web/tests/parity.mjs)), so
the browser build can't silently drift from the local one.

The pose source is **swappable**: anything that emits the normalized format
([`gaitlab/core/schema.py`](gaitlab/core/schema.py)) feeds the same engine.

## Analyze your own video locally

1. Drop your video file into `data/video/` (`.mov`, `.mp4`, etc.)
2. Start the server: `python3 server.py`
3. Click **New analysis**
4. Enter a **label**, pick the **video**, and choose the **view** (`side-left`, `rear`, etc.)
5. Click **Extract & Analyze** — the server runs RTMPose and opens the report automatically

The first run extracts the pose (30s–5min depending on length); repeat analyses of the same
video reuse the cached pose file instantly. Check "Force re-extract" to regenerate it.

> **Requires RTMPose:** first-time extraction needs `pip install -r requirements.txt`
> (only for the extractor — the server and engine run on bare Python).

**Via the CLI (advanced / headless)**

```bash
pip install -r requirements.txt

# Simple: video in data/video/, output goes to data/pose/ automatically
python3 extractor/extract_pose.py sample_run --view rear

# Explicit paths
python3 extractor/extract_pose.py /path/to/myrun.mp4 --view side-left -o myrun.pose.json
```

**Validate a clip before opening the browser:**

```bash
python3 validate_run.py sample_run --view side-left \
    --height 158 --leg 76 --speed 12.5 --sex female
```

Prints keypoint confidence, strike counts, metric plausibility, asymmetry flags, and a
pass/fail verdict in ~30 seconds.

**Optional extras**
- *MediaPipe instead of RTMPose* (swappable source): `pip install mediapipe opencv-python`
  then `python3 extractor/extract_pose_mediapipe.py sample_run --view side-left` — same output
  format, same `data/pose/` output.
- *Plain-English coach summary*: install [Ollama](https://ollama.com) and run `ollama run llama3.2`;
  a button on the report rephrases the findings via that local model. Fully optional — the
  rule-based feedback stays the source of truth and nothing leaves your machine.

## Accuracy & limitations

It's a **training aid, not a medical device**, and it does not diagnose injuries.

Single-camera 2-D has a hard constraint worth understanding: **sagittal (side-view) measures
are the trustworthy ones.** Frontal-plane readings — pelvic drop, pronation, hip adduction —
are directionally useful but sensitive to camera tilt, so the engine deliberately reports
several of them as low-confidence estimates rather than scoring them. Keep the camera level.
Ground-contact timing is bounded by frame rate (flagged approximate below 120 fps).

**Known issues:** rear-view lateral trunk sway and head sway currently measure whole-clip
drift rather than per-stride motion, so they read far too high on treadmill clips.

See [`docs/tech_requirements.md`](docs/tech_requirements.md) for the per-metric confidence
rationale and [`docs/references.md`](docs/references.md) for evidence sources.

## Development

```bash
pytest                     # engine test suite
make test-web              # web unit tests + browser/server parity check
make serve-static          # build and serve the static (browser) build locally
```

```
gaitlab/            pure-Python analysis engine (schema, events, metrics, asymmetry, feedback)
extractor/          RTMPose video → pose JSON (the one optional pip install)
server.py           local stdlib server: serves the UI + JSON API, SQLite storage
web/                browser UI (vanilla JS + Canvas), no build step
tests/              pytest suite for the engine
docs/               PRD, technical requirements, evidence references, generated metric spec
```

## License

GaitLab is released under the [MIT License](LICENSE) — © 2026 zzzhushi.

The browser build loads three third-party components at runtime, credited in-app under
**About & licenses** in the footer:

| Component | License |
|---|---|
| [Pyodide](https://github.com/pyodide/pyodide) — runs the Python engine in the browser | MPL-2.0 |
| [MediaPipe Tasks Vision](https://github.com/google-ai-edge/mediapipe) — landmark detection | Apache-2.0 |
| [BlazePose GHUM pose landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker) — the pose model, © Google | Apache-2.0 |

The local extractor additionally uses [rtmlib / RTMPose](https://github.com/Tau-J/rtmlib)
(Apache-2.0), which is never shipped to the browser.
