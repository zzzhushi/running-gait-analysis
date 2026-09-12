# Evidence register

This file is the bibliography for metric definitions and product claims. Stable IDs are
used by `MetricDef.reference_ids` and the generated specification. A citation supports
only the claim stated here; it does not automatically validate GaitLab's implementation.

## Evidence hierarchy

1. **Criterion validity for the same construct, view, population, and capture protocol**
   (ideally synchronized force plates or 3-D motion capture).
2. **Reliability studies and consensus definitions** for the same measurement.
3. **Population reference studies**, used only to show context conditional on speed and
   participant characteristics—not as “good” bands or injury thresholds.
4. **Association or intervention studies**, which may motivate research but do not prove
   diagnosis, causation, or an optimum for an individual.

The literature does not provide one definitive list of all metrics recoverable from an
arbitrary 2-D pose map. Recoverability depends on landmark definitions, camera plane,
frame rate, calibration, event detection, and the exact pose model. Two systematic reviews
found heterogeneous methods and mostly poor-to-moderate criterion validity for running
angles, especially outside the sagittal plane. That is why this project's own criterion
validation—not a generic range table—must be the final numerical source of truth.

## Core sources

| ID | Source | What it supports here |
|---|---|---|
| `Hensley2022` | [Hensley et al., *Reliability and validity of 2-dimensional video analysis for a running task: a systematic review*](https://pubmed.ncbi.nlm.nih.gov/36087406/) | 2-D running methods are heterogeneous; validity varies and categorical interpretation may outperform false angular precision. |
| `Leporace2023` | [Leporace et al., *Validity and reliability of two-dimensional video-based assessment to measure joint angles during running*](https://pubmed.ncbi.nlm.nih.gov/37541054/) | Most angular outcomes have low-to-moderate validity versus 3-D; extra caution is required for frontal and transverse planes. |
| `Cronin2023` | [*The accuracy of markerless motion capture combined with computer vision techniques for measuring running kinematics*](https://pubmed.ncbi.nlm.nih.gov/36680411/) | Direct criterion comparison for sagittal hip, knee, and ankle running kinematics; results remain model- and protocol-specific. |
| `Michelini2020` | [Michelini et al., *Two-dimensional video gait analysis: a systematic review of reliability, validity, and best practice considerations*](https://pubmed.ncbi.nlm.nih.gov/32507049/) | General 2-D gait measurement properties and capture considerations; running-specific claims rely on the running studies below. |
| `Patoz2021` | [Patoz et al., *A novel kinematic detection of foot-strike and toe-off events during noninstrumented treadmill running to estimate contact time*](https://pubmed.ncbi.nlm.nih.gov/34517256/) | Heel/toe kinematics can support running event estimates when the exact algorithm is validated against force data. It does not validate GaitLab's different algorithm. |
| `Oliveira2019` | [Oliveira et al., *Validity and Reliability of 2-Dimensional Video-Based Assessment to Analyze Foot Strike Pattern and Step Rate During Running: A Systematic Review*](https://pmc.ncbi.nlm.nih.gov/articles/PMC6745811/) | Step rate and categorical foot-strike assessment can be reliable in standardized 2-D running video, while criterion-validity evidence was limited. |
| `Malisoux2023` | [Malisoux et al., *Reference Values and Determinants of Spatiotemporal and Kinetic Variables in Recreational Runners*](https://pmc.ncbi.nlm.nih.gov/articles/PMC10588426/) | Published sex-, speed-, and anthropometry-aware population equations for cadence, contact/flight time, duty factor, vertical oscillation, and step length. These are population estimates, not targets. |
| `Hof1996` | [Hof, *Scaling gait data to body size*](https://doi.org/10.1016/0966-6362(95)01057-2) | Defines dimensionless gait scaling using leg length, including speed divided by `sqrt(g × leg length)`. It supports normalization, not GaitLab's pose-derived leg-length accuracy. |
| `Altman2012` | [Altman & Davis, *A kinematic method for footstrike pattern detection in barefoot and shod runners*](https://pubmed.ncbi.nlm.nih.gov/22075193/) | Foot-strike-angle definition and the −1.6°/8° classifier boundaries reported for the authors' protocol. Camera and footwear conventions must match before reuse. |
| `Xie2022` | [Xie et al., *Sex-specific differences in biomechanics among runners: a systematic review with meta-analysis*](https://pmc.ncbi.nlm.nih.gov/articles/PMC9539551/) | Some running kinematics differ by sex at group level. This does not justify a blanket “female normal band,” and the source uses binary study categories. |
| `MalisouxInjury2021` | [*Sex-Specific Differences in Running Injuries: a systematic review with meta-analysis*](https://pmc.ncbi.nlm.nih.gov/articles/PMC8053184/) | Overall injury rate was not different between sexes, although injury types differed; sex is not a universal risk multiplier. |
| `Sadeghi2000` | [Sadeghi et al., *Symmetry and limb dominance in able-bodied gait: a review*](https://pubmed.ncbi.nlm.nih.gov/10758292/) | Symmetry is construct- and task-dependent; a single universal asymmetry cutoff is not defensible. |
| `Zifchock2008` | [Zifchock et al., *The symmetry angle: a novel, robust method of quantifying asymmetry*](https://pubmed.ncbi.nlm.nih.gov/17913499/) | Normalized symmetry indices depend on denominator/reference choice and can behave poorly; native-unit side differences should remain visible. |
| `Ceyssens2019` | [Ceyssens et al., *Biomechanical Risk Factors Associated with Running-Related Injuries: a systematic review*](https://pubmed.ncbi.nlm.nih.gov/31028658/) | Prospective injury evidence is sparse and inconsistent; observations should not become diagnosis or injury-risk scores. |
| `Willwacher2022` | [Willwacher et al., *Running-Related Biomechanical Risk Factors for Overuse Injuries*](https://pmc.ncbi.nlm.nih.gov/articles/PMC9325808/) | Injury associations are injury- and population-specific; they do not support generic causal composite labels. |

## Standards and tooling

| ID | Source | Use |
|---|---|---|
| `ISB2002` | [Wu et al., ISB recommendations on joint coordinate systems](https://pubmed.ncbi.nlm.nih.gov/11934426/) | Coordinate-system terminology. Image-plane angles are proxies, not full 3-D joint rotations. |
| `RTMPose2023` | [Jiang et al., RTMPose](https://arxiv.org/abs/2303.07399) | Pose architecture; benchmark accuracy is not metric-level biomechanical validity. |
| `Halpe26` | [Halpe Full-Body keypoint definitions](https://github.com/Fang-Haoshu/Halpe-FullBody) | Source landmark index map for the local extractor. |
| `MediaPipePose` | [MediaPipe Pose Landmarker documentation](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) | Browser pose source and landmark semantics. |

## Claims intentionally not made

- There is no universal ideal cadence, contact time, pelvic drop, knee flexion, or
  left/right asymmetry percentage independent of speed, anatomy, task, and protocol.
- A population mean or regression estimate is not an individualized target.
- A pose landmark confidence score is not biomechanical validity.
- A 2-D composite pattern is not a diagnosis, a force estimate, or proof of injury risk.
- Published validation of a different app or model does not validate GaitLab.
