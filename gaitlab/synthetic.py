"""Procedural running-gait generator.

Produces a normalized PoseSequence via simple 2-D forward kinematics (sinusoidal hip
and knee motion). It is the same shape RTMPose/MediaPipe emit, so it serves two jobs:

  1. deterministic ground-truth input for the unit tests, and
  2. a zero-setup demo so the app shows a real analysis before you film anything.

`asymmetry` (0..1) deliberately reduces one leg's knee range / increases one hip's
drop, so the left/right and injury-risk features have something to detect.
"""

from __future__ import annotations

import math
import random
from typing import List

from .schema import KEYPOINTS, KP_INDEX, Point, PoseSequence


def _blank_frame() -> List[Point]:
    return [(0.0, 0.0, 0.0) for _ in KEYPOINTS]


def _set(frame: List[Point], name: str, x: float, y: float, score: float = 1.0) -> None:
    frame[KP_INDEX[name]] = (x, y, score)


def _rot_forward(local_x: float, local_y: float, tilt: float, facing: int):
    """Place a foot-local point (x forward, y down) into image space, tilt>0 lifts toe."""
    return (facing * local_x * math.cos(tilt), local_y - local_x * math.sin(tilt))


def generate(
    view: str = "side-left",
    fps: float = 60.0,
    duration: float = 4.0,
    cadence: float = 172.0,
    width: int = 1080,
    height: int = 1920,
    asymmetry: float = 0.0,
    noise: float = 0.0,
    seed: int = 0,
) -> PoseSequence:
    if view in ("rear", "front"):
        return _generate_rear(view, fps, duration, cadence, width, height, asymmetry, noise, seed)
    return _generate_side(view, fps, duration, cadence, width, height, asymmetry, noise, seed)


def _generate_side(view, fps, duration, cadence, width, height, asymmetry, noise, seed):
    rng = random.Random(seed)
    n = max(2, int(round(duration * fps)))
    facing = -1 if view == "side-right" else 1

    H = height * 0.82
    hipX = width * 0.5
    hipY0 = height * 0.50
    torso = 0.30 * H
    head = 0.13 * H
    thigh = 0.245 * H
    shank = 0.245 * H
    foot_len = 0.15 * H
    upper_arm = 0.16 * H
    fore_arm = 0.15 * H

    stride_freq = (cadence / 60.0) / 2.0
    vosc_amp = 0.028 * H
    trunk_lean = math.radians(8.0)

    frames: List[List[Point]] = []
    for f in range(n):
        t = f / fps
        phase_l = 2 * math.pi * stride_freq * t
        phase_r = phase_l + math.pi
        hip_y = hipY0 - vosc_amp * math.cos(2 * phase_l)
        hip = (hipX, hip_y)

        fr = _blank_frame()
        _set(fr, "mid_hip", hip[0], hip[1])

        for side, phase, asym in (("l", phase_l, 0.0), ("r", phase_r, asymmetry)):
            thigh_swing = math.radians(28.0) * (1 - 0.30 * asym)
            thigh_angle = thigh_swing * math.sin(phase)
            k0 = math.radians(12.0)
            k_amp = math.radians(58.0) * (1 - 0.45 * asym)
            # early-stance "absorption" bump so the knee is bent ~40 deg at midstance
            wrapped = (phase - 0.8 + math.pi) % (2 * math.pi) - math.pi
            absorb = math.radians(28.0) * (1 - 0.40 * asym)
            absorb_term = absorb * math.exp(-(wrapped ** 2) / (2 * 0.45 ** 2))
            knee_flex = k0 + k_amp * (1 - math.cos(phase)) / 2.0 + absorb_term
            shank_angle = thigh_angle - knee_flex

            knee = (hip[0] + thigh * math.sin(thigh_angle),
                    hip[1] + thigh * math.cos(thigh_angle))
            ankle = (knee[0] + shank * math.sin(shank_angle),
                     knee[1] + shank * math.cos(shank_angle))

            foot_tilt = math.radians(9.0) * math.sin(phase) - math.radians(2.0)
            hx, hy = _rot_forward(-0.30 * foot_len, 0.06 * foot_len, foot_tilt, facing)
            tx, ty = _rot_forward(0.72 * foot_len, 0.06 * foot_len, foot_tilt, facing)
            sx, sy = _rot_forward(0.66 * foot_len, 0.10 * foot_len, foot_tilt, facing)

            hipx = hipX + facing * (0.04 * H if side == "l" else -0.04 * H) * 0  # overlap in side view
            _set(fr, f"{side}_hip", hip[0], hip[1])
            _set(fr, f"{side}_knee", knee[0], knee[1])
            _set(fr, f"{side}_ankle", ankle[0], ankle[1])
            _set(fr, f"{side}_heel", ankle[0] + hx, ankle[1] + hy)
            _set(fr, f"{side}_big_toe", ankle[0] + tx, ankle[1] + ty)
            _set(fr, f"{side}_small_toe", ankle[0] + sx, ankle[1] + sy)

        # torso + head
        neck = (hip[0] + torso * math.sin(trunk_lean), hip[1] - torso * math.cos(trunk_lean))
        nose = (neck[0] + head * math.sin(trunk_lean), neck[1] - head * math.cos(trunk_lean))
        _set(fr, "neck", neck[0], neck[1])
        _set(fr, "nose", nose[0], nose[1])

        # arms swing opposite to the legs
        for side, phase in (("l", phase_l + math.pi), ("r", phase_r + math.pi)):
            arm_angle = math.radians(24.0) * math.sin(phase)
            sh = (neck[0], neck[1] + 0.02 * H)
            elbow = (sh[0] + upper_arm * math.sin(arm_angle),
                     sh[1] + upper_arm * math.cos(arm_angle))
            wrist = (elbow[0] + fore_arm * math.sin(arm_angle + math.radians(35)),
                     elbow[1] + fore_arm * math.cos(arm_angle + math.radians(35)))
            _set(fr, f"{side}_shoulder", sh[0], sh[1])
            _set(fr, f"{side}_elbow", elbow[0], elbow[1])
            _set(fr, f"{side}_wrist", wrist[0], wrist[1])

        if noise > 0:
            fr = [(x + rng.gauss(0, noise), y + rng.gauss(0, noise), s) for (x, y, s) in fr]
        frames.append(fr)

    return PoseSequence(fps=fps, width=width, height=height, view=view,
                        frames=frames, source="synthetic")


def _generate_rear(view, fps, duration, cadence, width, height, asymmetry, noise, seed):
    rng = random.Random(seed)
    n = max(2, int(round(duration * fps)))

    H = height * 0.82
    cx = width * 0.5
    hipY0 = height * 0.50
    hip_hw = 0.10 * H
    thigh = 0.245 * H
    shank = 0.245 * H
    torso = 0.30 * H
    sway = 0.012 * H

    stride_freq = (cadence / 60.0) / 2.0
    vosc_amp = 0.026 * H
    # pelvic drop amplitude (px of vertical hip-line offset); asymmetry deepens one side
    drop_amp = 0.020 * H

    frames: List[List[Point]] = []
    for f in range(n):
        t = f / fps
        phase_l = 2 * math.pi * stride_freq * t
        phase_r = phase_l + math.pi
        body_y = hipY0 - vosc_amp * math.cos(2 * phase_l)
        body_x = cx + sway * math.sin(phase_l)

        # During left stance the right (swing) hip drops, and vice-versa.
        s = math.sin(phase_l)
        drop_r = drop_amp * max(0.0, s) * (1 + 0.9 * asymmetry)   # right hip drops in left stance
        drop_l = drop_amp * max(0.0, -s)
        l_hip = (body_x - hip_hw, body_y + drop_l)
        r_hip = (body_x + hip_hw, body_y + drop_r)

        fr = _blank_frame()
        _set(fr, "mid_hip", body_x, (l_hip[1] + r_hip[1]) / 2)
        _set(fr, "l_hip", l_hip[0], l_hip[1])
        _set(fr, "r_hip", r_hip[0], r_hip[1])

        for side, hip, phase in (("l", l_hip, phase_l), ("r", r_hip, phase_r)):
            # foot swings laterally inward a touch and lifts during swing
            lift = max(0.0, math.sin(phase))
            lateral = 0.02 * H * math.sin(phase)
            knee = (hip[0] + lateral * 0.5, hip[1] + thigh * (1 - 0.04 * lift))
            ankle = (hip[0] + lateral, hip[1] + (thigh + shank) * (1 - 0.16 * lift))
            # rear-foot roll-in (pronation): heel sits lateral of the ankle; more on the right
            toward_mid = 1.0 if ankle[0] < body_x else -1.0
            evert = (0.005 * H * (1 + 0.6 * asymmetry)) if side == "r" else (0.003 * H)
            heel = (ankle[0] - toward_mid * evert, ankle[1] + 0.03 * H)
            toe = (ankle[0] - toward_mid * evert, ankle[1] + 0.06 * H)
            _set(fr, f"{side}_knee", knee[0], knee[1])
            _set(fr, f"{side}_ankle", ankle[0], ankle[1])
            _set(fr, f"{side}_heel", heel[0], heel[1])
            _set(fr, f"{side}_big_toe", toe[0], toe[1])
            _set(fr, f"{side}_small_toe", toe[0] + 0.02 * H, toe[1])

        neck = (body_x, body_y - torso)
        nose = (body_x, neck[1] - 0.13 * H)
        _set(fr, "neck", neck[0], neck[1])
        _set(fr, "nose", nose[0], nose[1])
        _set(fr, "l_shoulder", body_x - 0.14 * H, neck[1] + 0.02 * H)
        _set(fr, "r_shoulder", body_x + 0.14 * H, neck[1] + 0.02 * H)
        for side, sgn in (("l", -1), ("r", 1)):
            _set(fr, f"{side}_elbow", body_x + sgn * 0.16 * H, neck[1] + 0.18 * H)
            _set(fr, f"{side}_wrist", body_x + sgn * 0.15 * H, neck[1] + 0.34 * H)

        if noise > 0:
            fr = [(x + rng.gauss(0, noise), y + rng.gauss(0, noise), sc) for (x, y, sc) in fr]
        frames.append(fr)

    return PoseSequence(fps=fps, width=width, height=height, view=view,
                        frames=frames, source="synthetic")


def demo_runs():
    """Labeled demo sequences (label, sequence, calibration) for seeding an empty library."""
    return [
        ("Treadmill — side (clean)", generate("side-left", cadence=188, asymmetry=0.05, seed=1),
         {"sex": "female", "height_cm": 158, "leg_length_cm": 76, "speed_kmh": 12.5}),
        ("Treadmill — side (overstride)", generate("side-left", cadence=158, asymmetry=0.18, seed=2), None),
        ("Treadmill — rear (hip drop)", generate("rear", cadence=170, asymmetry=0.5, seed=3),
         {"sex": "female", "height_cm": 158}),
    ]
