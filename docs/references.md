# GaitLab — Reference Links

Categorized reading list backing the design decisions and target values in this project.
Add URLs as you find them; the categories below match the metric/feature areas.

---

## Pose estimation & tooling

| What | URL | Notes |
|---|---|---|
| rtmlib (RTMPose wrapper used here) | https://github.com/Tau-J/rtmlib | Apache-2.0; Halpe26 body+feet, CPU inference |
| RTMPose paper (ECCV 2023) | https://arxiv.org/abs/2303.07399 | Accuracy benchmarks vs MediaPipe / OpenPose |
| MMPose docs (RTMPose model zoo) | https://mmpose.readthedocs.io/en/latest/model_zoo/body_2d_keypoint.html | All pretrained checkpoints, AP scores per model size |
| RTMPose3D (future 3-D upgrade path) | https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose3d | Same ecosystem; no extra training |
| MediaPipe Pose Landmarker | https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker | Alternative extractor already wired in |
| Halpe-26 keypoint layout | https://github.com/Fang-Haoshu/Halpe-FullBody | Diagram of the 26-kpt body+feet indices — **the definitive map for which index = which joint** |
| Kinovea (free gait video tool) | https://www.kinovea.org | Useful for manual angle verification / ground-truth |

### RTMPose Halpe26 keypoint index map (quick reference)

```
Index  Name            Used?  Notes
  0    nose            yes
  1    left_eye        no     face detail, not useful for gait
  2    right_eye       no
  3    left_ear        no
  4    right_ear       no
  5    left_shoulder   yes
  6    right_shoulder  yes
  7    left_elbow      yes
  8    right_elbow     yes
  9    left_wrist      yes
 10    right_wrist     yes
 11    left_hip        yes
 12    right_hip       yes
 13    left_knee       yes
 14    right_knee      yes
 15    left_ankle      yes
 16    right_ankle     yes
 17    head (crown)    NO     worth adding — enables head bobbing / forward head posture
 18    neck            yes    derived mid-point in wholebody mode
 19    mid_hip         yes    derived mid-point
 20    left_big_toe    yes
 21    right_big_toe   yes
 22    left_small_toe  yes
 23    right_small_toe yes
 24    left_heel       yes
 25    right_heel      yes
```

**Head (crown, index 17) — recommended addition:**
- Side view: head vertical oscillation (some runners bob head more than hips), forward head posture (crown-ahead-of-shoulders), head-hip vertical alignment
- Rear view: lateral head sway, compensatory head tilt (runners with heavy hip drop often tilt head opposite direction)
- Requires adding `"head": 17` to `HALPE26` in `extractor/extract_pose.py` and `"head"` to `KEYPOINTS` in `gaitlab/schema.py`

---

## Running biomechanics — overview

| What | URL | Notes |
|---|---|---|
| Novacheck 1998 — biomechanics of running | https://www.sciencedirect.com/science/article/pii/S0966636298000847 | Classic reference for joint angles + timing norms |
| Napier et al. 2018 — running gait retraining review | https://bjsm.bmj.com/content/52/19/1227 | Evidence on which cues actually change mechanics |
| Heiderscheit et al. 2011 — cadence & overstriding | https://journals.lww.com/acsm-msse/fulltext/2011/07000/effects_of_step_rate_manipulation_on_joint.14.aspx | Increasing cadence 5–10% reduces impact load |

---

## Cadence

| What | URL | Notes |
|---|---|---|
| Dallam et al. 2005 — 180 spm myth origin | https://pubmed.ncbi.nlm.nih.gov/15793090/ | Daniels observed elites at 180+; not a universal target |
| Luedke et al. 2016 — cadence prescription by height | https://pubmed.ncbi.nlm.nih.gov/26778467/ | Shorter runners run higher cadence; basis of our height-adjusted target |
| Willy et al. 2016 — real-time cadence feedback | https://journals.sagepub.com/doi/10.1177/0363546515621495 | Metronome cues reduce patellofemoral load |

---

## Ground contact time & duty factor

| What | URL | Notes |
|---|---|---|
| Morin et al. 2011 — duty factor and performance | https://pubmed.ncbi.nlm.nih.gov/21526067/ | Faster runners have lower duty factor; spring-mass model |
| Folland et al. 2017 — GCT economy link | https://pubmed.ncbi.nlm.nih.gov/28891591/ | GCT < 250 ms associated with better running economy |

---

## Vertical oscillation & vertical ratio

| What | URL | Notes |
|---|---|---|
| Anderson 1996 — VO and economy | https://pubmed.ncbi.nlm.nih.gov/8784759/ | VO > 10 cm associated with worse economy |
| Garmin / Stryd vertical ratio norms | — | 6–8% typical for recreational runners; add link if found |

---

## Pelvic drop & hip mechanics

| What | URL | Notes |
|---|---|---|
| Noehren et al. 2007 — hip drop and ITBS | https://pubmed.ncbi.nlm.nih.gov/17159699/ | Excessive pelvic drop prospectively predicts IT band syndrome |
| Ferber et al. 2003 — sex differences in hip kinematics | https://pubmed.ncbi.nlm.nih.gov/14665733/ | Females show greater hip adduction → basis for wider female band |
| Phinyomark et al. 2015 — pelvic drop in recreational runners | https://pubmed.ncbi.nlm.nih.gov/25607280/ | Community norms: ~4–7° drop typical |

---

## Overstride & foot strike

| What | URL | Notes |
|---|---|---|
| Lieberman et al. 2010 — foot strike and impact (Nature) | https://www.nature.com/articles/nature08723 | Heel-strike with overstride = higher collision force |
| Altman & Davis 2012 — foot strike classification | https://pubmed.ncbi.nlm.nih.gov/22236580/ | Defines heel / midfoot / forefoot by contact angle |
| Crowell & Davis 2011 — shank angle retraining | https://pubmed.ncbi.nlm.nih.gov/20889020/ | Reducing overstride cuts peak tibial acceleration 20% |

---

## Knee drive & hip extension

| What | URL | Notes |
|---|---|---|
| Dorn et al. 2012 — hip flexors vs ankle plantar-flexors | https://royalsocietypublishing.org/doi/10.1098/rsif.2012.0174 | At faster speeds hip flexion becomes dominant propulsive driver |
| Schache et al. 2011 — hip extension during sprinting | https://pubmed.ncbi.nlm.nih.gov/20972344/ | Peak hip extension ~20–25° at comfortable running pace |

---

## Arm mechanics

| What | URL | Notes |
|---|---|---|
| Pontzer et al. 2009 — arm swing and rotational balance | https://pubmed.ncbi.nlm.nih.gov/19487494/ | Arms reduce torso rotation; removing them increases O₂ cost |
| Arellano & Kram 2014 — energetics of arm swing | https://pubmed.ncbi.nlm.nih.gov/24285837/ | ~3% O₂ cost penalty when arms are restricted |
| Tseh et al. 2008 — elbow angle and economy | — | ~90° elbow = efficient; add link if found |

---

## Injury risk & corrective exercise

| What | URL | Notes |
|---|---|---|
| Rasmussen et al. 2021 — running injury rates review | https://bjsm.bmj.com/content/55/23/1357 | ~50% of recreational runners injured per year |
| Hamner et al. 2010 — muscle contributions to propulsion | https://pubmed.ncbi.nlm.nih.gov/20667590/ | Gastrocnemius, soleus drive propulsion; vasti absorb impact |
| Blagrove et al. 2018 — strength training for runners | https://link.springer.com/article/10.1007/s40279-017-0835-7 | Heavy resistance training improves economy; backs corrective-ex plan |

---

## Camera views — what each angle can and cannot measure

### Side view (side-left / side-right)
**Camera position:** level with mid-hip, 3–5 m away, perpendicular to direction of travel.

| Metric | Reliable? | Notes |
|---|---|---|
| Cadence | ✅ strong | |
| Trunk lean (forward/backward) | ✅ strong | |
| Knee flexion — midstance & contact | ✅ strong | |
| Overstride (foot ahead of hip) | ✅ strong | |
| Hip extension at toe-off | ✅ strong | |
| Knee drive (peak thigh angle) | ✅ strong | |
| Foot-strike pattern | ✅ strong | needs heel/toe kpts; RTMPose >> MediaPipe |
| Vertical oscillation | ✅ strong | hip-Y amplitude |
| Ground contact time | ✅ good | accuracy improves at 120/240 fps |
| Duty factor / flight time | ✅ good | fps-limited |
| Elbow angle | ✅ good | near arm clear; far arm may be partially occluded |
| Arm swing amplitude | ⚠️ limited | near arm only; far arm hidden behind torso |
| Heel recovery height | ✅ good | |
| Step / stride length | ✅ good | requires speed calibration |
| Head bobbing / forward head posture | ✅ good | **requires adding `head` keypoint (index 17)** |
| Pelvic drop | ❌ invisible | edge-on from side |
| Pronation | ❌ invisible | lateral motion, edge-on |
| Step width / crossover | ❌ invisible | depth axis |
| Lateral trunk sway | ❌ invisible | depth axis |

**Treadmill occlusion (handrails / arms):**
Handrails at waist height sit at the same depth plane as the runner's hips in 2-D.
- If a rail overlaps the hip or wrist keypoint, confidence drops → that keypoint is dropped for those frames
- Metrics are computed from medians across strides, so a few low-confidence frames don't ruin the result
- **Most at risk:** trunk lean (mid-hip), overstride (hip reference), arm swing if rail crosses wrist path
- **Mitigation:** position the camera slightly in front of or behind the treadmill (angled ~10–15°) so the rail is behind the runner in the image plane rather than overlapping their body; or film from a slightly higher angle to clear the rail. Handheld rails that the runner grips while filming should be avoided entirely — the wrist is then stationary and the engine will see zero arm swing.

---

### Rear view
**Camera position:** directly behind, level with mid-hip, 3–5 m away.

| Metric | Reliable? | Notes |
|---|---|---|
| Cadence | ✅ strong | |
| Pelvic drop | ✅ strong | primary reason to film rear |
| Step width / crossover | ✅ strong | |
| Lateral trunk sway | ✅ strong | |
| Arm crossover | ✅ good | hands crossing the midline |
| Trunk–pelvis counter-rotation | ⚠️ low confidence | 2-D proxy only; labeled as such in output |
| Pronation estimate | ⚠️ limited | rear-foot vs lower-leg; low-confidence in 2-D |
| Head lateral sway / compensatory tilt | ✅ good | **requires adding `head` keypoint** |
| Trunk lean (forward) | ❌ invisible | depth axis from behind |
| Overstride | ❌ invisible | depth axis |
| Knee flexion | ❌ invisible | depth axis |
| Vertical oscillation | ⚠️ very rough | hip-Y has much less range from behind |

**Camera tilt sensitivity:** rear-view metrics are the most sensitive to a tilted camera. If the camera isn't level, the hip-line baseline tilts with it, making pelvic drop systematically over- or under-reported. Keep camera level; use a tripod.

---

### Front view
**Camera position:** directly in front, level with mid-hip, 3–5 m away.

| Metric | Reliable? | Notes |
|---|---|---|
| Lateral trunk sway | ✅ good | similar to rear |
| Step width (rough) | ⚠️ limited | feet face camera; width harder to judge than from rear |
| Both arms simultaneously | ✅ unique advantage | only view where L/R arm swing are both unoccluded |
| Head bobbing (vertical) | ✅ good | **requires `head` keypoint** |
| Pelvic drop | ⚠️ limited | pelvis faces camera; tilt harder to measure than from rear |
| Foot mechanics (pronation, strike) | ❌ poor | toes face camera, heel/arch hidden |
| Overstride, knee flexion, trunk lean | ❌ invisible | depth axis |

**Treadmill partial body (below-knee only):**
If the treadmill console/screen or user's body blocks the camera above the knee, what survives:
- Step width and crossover detection — usable if ankles are clearly visible
- Foot-strike pattern — partial (toe/heel angle still somewhat visible)
- Everything from the knee up — **lost**. Pelvic drop, lateral sway, arm crossover all require upper-body keypoints.
- The quality check "runner too small in frame" will fire; the engine will still attempt analysis but the result is unreliable above foot-level metrics.
- **Verdict: below-knee front view is not sufficient for a meaningful gait report.** It could work as a *supplementary* foot-strike/step-width check only.

---

### Practical filming recommendation (treadmill)

```
Priority 1: Side view (left or right — pick the side with better lighting)
            → covers ~70% of actionable metrics
Priority 2: Rear view (full body, level camera, no handheld grip on rails)
            → adds pelvic drop, crossover, pronation
Priority 3: Front view (only if you specifically want bilateral arm comparison
            and the console doesn't block the torso)
```

Use the Combine screen (#/combine) to merge a side + rear run into one report.

---

## Camera setup & filming

| What | URL | Notes |
|---|---|---|
| Apple slow-mo frame rates (iPhone) | https://support.apple.com/en-us/101662 | 120 fps (1080p) or 240 fps (720p) available on most recent iPhones |
| Android slow-mo by device | — | Varies; Samsung Galaxy: 240 fps @ 720p |
| Tripod angle guide for treadmill filming | — | Add link; aim for camera level with mid-hip, ~3–5 m away |

---

## Similar tools (for comparison)

| Tool | URL | Notes |
|---|---|---|
| Kinovea | https://www.kinovea.org | Free, Windows; manual angle measurement; no auto-analysis |
| RunScribe | https://runscribe.com | IMU pod; gives GCT, braking-g, pronation — the kinetic half 2-D can't see |
| DARI Motion | https://darimotionhealth.com | Commercial markerless 3-D mocap; what a real gait lab uses |
| Sency / AI gait tools | https://sency.ai | ML-based pose; commercial |
| PhysiTrack / Vald | — | Clinical PT tools; not open |

---

## To add

- Peer-reviewed norms for heel recovery height (% leg) — not found yet
- Trunk–pelvis counter-rotation norms in recreational running
- Per-side step-length asymmetry thresholds (clinical vs recreational)
- High-frame-rate filming guide for Android devices
