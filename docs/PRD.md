# GaitLab — Product Requirements Document

**A local, free running gait analysis tool.** Feed in a video of yourself running
(side or rear view); it draws the moving skeleton over your footage, measures your
mechanics, finds left/right asymmetries, and gives coach-style feedback — all on your
own machine, with no account, no upload, and no API keys.

- **Status:** v1 implemented (this repo). The synthetic demo runs prove the full pipeline end-to-end.
- **Last updated:** 2026-06-26

---

## 1. Problem & motivation

Runners want to understand *how* they move, not just how far/fast. Professional gait
analysis (force plates, marker mocap, a coach with a high-speed camera) is expensive
and rarely repeatable. Wearables give a few numbers but no picture of the mechanics.

The owner wants to understand their own running "at a mechanical level": **see** the
limbs moving, **measure** the key parameters, learn **where the left/right
asymmetries are**, and get **specific, actionable feedback** like a running coach
would — repeatedly, for free, from ordinary phone videos.

## 2. Goals / non-goals

**Goals**
- Turn a normal phone video (side or rear) into a tracked, watchable skeleton overlay.
- Compute the metrics a real gait analysis covers (cadence, overstride, trunk lean,
  knee flexion, foot strike, ground contact, vertical oscillation, pelvic drop, crossover).
- Surface **left/right asymmetry** explicitly.
- Produce **coach-style, prioritized feedback** with a plain-language explanation, a
  cue, and a corrective drill for each finding.
- Track runs over time and compare them.
- Run **100% locally, $0, no API keys.**

**Non-goals (v1)**
- Clinical/diagnostic claims. This is a training aid, not a medical device.
- True 3-D kinematics or joint moments (single-camera 2-D only).
- Multi-runner scenes, live coaching, or mobile-native apps.
- Real-world absolute distances without optional calibration.

## 3. User & use cases

**Primary user:** a self-coaching runner (the owner), comfortable running a Python
script, who films on a treadmill (phone on a tripod) or occasionally outdoors.

- *Self-coaching:* "What should I work on in my form?"
- *Asymmetry:* "Is my left side doing something different from my right?"
- *Injury avoidance:* "Am I overstriding / dropping a hip in a way that risks injury?"
- *Progress:* "Has my cadence/symmetry improved over the last month?"

## 4. Constraints & principles

- **Local-only / private:** video never leaves the machine; everything is on `localhost`.
- **Free:** no paid services, no API keys. Pose by RTMPose (Apache-2.0); feedback is
  rule-based. (An optional local LLM could rephrase findings later — not required.)
- **Zero-friction to run the app:** the server, engine, UI, and tests use only the
  Python standard library. The single `pip install` is for the optional video extractor.
- **Swappable pose source:** the engine consumes a normalized landmark format; RTMPose,
  MediaPipe, or anything else can feed it.
- **Honest about uncertainty:** 2-D single-camera limits are stated, not hidden.

## 5. Functional requirements (by lens)

The owner asked for all four lenses as must-haves:

1. **Visual study tool** — skeleton overlay on the video (or skeleton-only when no video),
   slow-motion (0.25–1×), frame-by-frame scrubbing, gait-cycle phase ribbon, joint-angle
   arcs, COM/ground reference lines, motion trails, and a live per-frame metric readout.
2. **Performance & efficiency** — cadence, vertical oscillation, ground contact time,
   trunk lean, knee flexion, overstride.
3. **Left/right asymmetry** — per-side values and % difference for every bilateral metric,
   color-graded, plus a dedicated symmetry view.
4. **Injury-risk flags** — overstriding, heavy heel-strike-with-overstride, excessive
   pelvic drop, crossover gait, low cadence.

## 6. Analysis catalog (with targets & priority)

Targets are evidence-informed heuristics (see `gaitlab/targets.py`). Distances are
normalized by leg length ("% leg") so they need no calibration; angles need none either.

### P0 — implemented (MVP core)
| Metric | View | Target | Why |
|---|---|---|---|
| Cadence | both | 170–185 spm | low cadence ↔ overstriding & higher impact |
| Trunk lean | side | 5–12° forward | gentle lean from the ankles aids economy |
| Knee flexion (midstance) | side | 38–50° | shock absorption; stiff legs jar joints |
| Overstride | side | < 8% leg | foot landing ahead of hips = braking |
| Foot-strike pattern | side | informational | matters mainly in combination with overstride |
| Vertical oscillation | side | < 12% leg | vertical bounce is wasted energy |
| Pelvic drop | rear | < 6° | hip-stabilizer weakness; injury-linked |
| Ground contact time | side | < 250 ms | longer = less reactive (fps-limited) |
| Step width / crossover | rear | 2–14% leg | crossover narrows base, stresses ITB/knee |
| Lateral trunk sway | rear | < 8% leg | often follows hip drop / weak core |
| **L/R asymmetry** (all bilateral metrics) | both | < 5% | > 10% worth addressing |

### P1 — next
Ground-contact balance L/R at high fps · hip extension at toe-off · pronation/eversion
estimate from the foot keypoints · vertical oscillation in cm + vertical ratio (needs
height calibration).

### P2 — later
Arm/elbow swing & symmetry · knee drive + heel recovery height · stride/step length
(needs speed) · trunk–pelvis counter-rotation · duty factor · flight time.

### P3 — research
Leg/vertical stiffness · braking-force proxy · 3-D (RTMPose3D / multi-view) · optional
LLM-phrased coaching narrative.

## 7. UX / screens

Implemented as a single-page app served at `localhost`.

1. **Library** — grid of saved runs (each a skeleton thumbnail, view, cadence, grade
   badge, top finding) + an overall-score trend sparkline. Entry point to a new analysis.
2. **New analysis** — drop a pose `.json` (and optionally the video) → choose view + label
   → analyze. Inline instructions for generating the pose file; footage best-practices.
3. **Player** (centerpiece) — video with skeleton overlay; play / slow-mo / frame-step /
   scrub; gait-cycle phase ribbon (stance bands + strike ticks) you can click to seek;
   overlay toggles (skeleton / angles / reference lines / trails); a live readout rail
   (time, phase, and view-appropriate angles).
4. **Report** — overall grade + score; metric cards vs target (green/amber/red, with L/R
   values); a mirrored-bar asymmetry panel; prioritized coach findings (explanation +
   cue + drill), each deep-linking to the illustrating frame in the player.
5. **Trends** — per-metric line charts across sessions with target bands; pick two runs
   to compare side-by-side in a delta table.

## 8. Architecture & data model

```
video ──▶ extract_pose.py (RTMPose / rtmlib)
              │  normalized pose JSON
              ▼
   POST /api/analyze ──▶ gaitlab engine ──▶ AnalysisResult (JSON)
              │                                   │
        SQLite (local)  ◀───────────────────────┘
              │
        browser UI (vanilla JS + Canvas) ◀── GET /api/runs[/id]
```

- **Pose extractor** (`extractor/extract_pose.py`): RTMPose body+feet (Halpe26) or
  whole-body (133) via `rtmlib`/ONNX on CPU → the normalized format. The only component
  that needs `pip install`.
- **Normalized pose format** (`gaitlab/schema.py`): `{fps,width,height,view,keypoint_names,
  frames:[[[x,y,score],…]]}`, 21 canonical keypoints incl. heel/toe. The swappable seam.
- **Analysis engine** (`gaitlab/`, pure Python, stdlib only): gait-event detection →
  per-stride metrics → asymmetry → target scoring → rule-based feedback. Unit-tested.
- **Server** (`server.py`, stdlib `http.server` + `sqlite3`): serves the UI + JSON API,
  stores runs locally, seeds synthetic demos when empty.
- **UI** (`web/`, no build step): ES-module vanilla JS + Canvas overlay + SVG charts.

## 9. Accuracy, calibration & known limitations

- Single-camera **2-D**: sagittal (side) metrics are strong; frontal (pelvic drop,
  crossover) are decent but **sensitive to camera tilt/height** — keep the camera level.
- **Transverse-plane** rotation and fine **pronation** are low-reliability in 2-D.
- **Ground-contact time** resolution is bounded by frame rate — use 120/240 fps slow-mo
  for it; 30/60 fps is fine for angles and cadence.
- Absolute distances (stride length, VO in cm) need **calibration** (enter height; or
  treadmill speed for stride) — deferred to P1; v1 uses calibration-free %-of-leg and angles.
- Best results: one runner filling the frame, contrasting background, steady camera.

## 10. Privacy

Everything is local. The server binds to `127.0.0.1`. No video is uploaded; in v1 the
video stays in the browser tab for overlay, and only landmarks + computed results are
persisted to a local SQLite file.

## 11. Success metrics

- The owner can go from a filmed clip to an annotated report in a couple of minutes.
- Engine numbers agree with hand-measured angles within ~5° and cadence within a step
  or two of a manual count (see `tests/`).
- Findings are specific enough to act on, and re-filming after a few weeks shows whether
  a flagged issue (e.g. cadence, asymmetry) moved.

## 12. Roadmap

- **M0–M4 (done):** PRD, RTMPose extractor, analysis engine + tests, server + storage,
  the full UI (library / player / report / trends), synthetic demo seeding.
- **M5 (next):** P1 metrics (GCT balance, pronation, hip extension) + height/speed
  calibration; optional MediaPipe extractor behind the same format; optional local-LLM
  phrasing of findings.

## 13. Open questions

- Worth persisting the video to disk (local media folder) for re-viewing past runs?
- Add a guided capture checklist / auto-quality check (camera level, runner in frame)?
- Multi-view fusion (side + rear of the same session) into a single report?
