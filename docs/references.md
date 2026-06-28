# GaitLab — Reference Links

Categorized reading list backing the design decisions and target values in this project.
Add URLs as you find them; the categories below match the metric/feature areas.

---

## Pose estimation & tooling

| What | URL | Notes |
|---|---|---|
| rtmlib (RTMPose wrapper used here) | https://github.com/Tau-J/rtmlib | Apache-2.0; Halpe26 body+feet, CPU inference |
| RTMPose paper (ECCV 2023) | https://arxiv.org/abs/2303.07399 | Accuracy benchmarks vs MediaPipe / OpenPose |
| RTMPose3D (future 3-D upgrade path) | https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose3d | Same ecosystem; no extra training |
| MediaPipe Pose Landmarker | https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker | Alternative extractor already wired in |
| Halpe-26 keypoint layout | https://github.com/Fang-Haoshu/Halpe-FullBody | Diagram of the 26-kpt body+feet indices |
| Kinovea (free gait video tool) | https://www.kinovea.org | Useful for manual angle verification / ground-truth |

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
