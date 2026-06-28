"""Corrective exercise library, keyed by the issue a finding points at.

Each exercise has a name, why it helps, a starting dose, and a progression. These are
general strength/mobility/running-form drills from coaching and sports-PT practice — a
training aid, not a clinical prescription. For pain or a diagnosed injury, see a
physio/PT; this won't tell you the root cause for *you* specifically.
"""

from __future__ import annotations

from typing import List

# metric/issue key -> ordered list of exercises
EXERCISES = {
    "cadence": [
        {"name": "Metronome strides", "why": "Trains a quicker, lighter turnover.",
         "dose": "4×30s at target cadence, easy jog between", "progression": "Hold the new cadence for whole easy runs."},
        {"name": "Quick-feet A-skips", "why": "Grooves fast ground contacts.",
         "dose": "3×20m, 2–3×/week", "progression": "Add B-skips, then build to strides."},
    ],
    "overstride": [
        {"name": "High-cadence strides", "why": "Pulls the foot-strike back under your hips.",
         "dose": "6×20s focusing on landing beneath you", "progression": "Blend into tempo running."},
        {"name": "Falling-start runs", "why": "Teaches leaning from the ankles, not reaching.",
         "dose": "6×20m from a tall lean", "progression": "Carry the lean into a relaxed cruise."},
        {"name": "Wall posture drill", "why": "Builds the tall, forward-from-the-ankle position.",
         "dose": "3×30s holds", "progression": "Add a marching knee-drive."},
    ],
    "hip_extension": [
        {"name": "Couch stretch (hip flexors)", "why": "Frees the front of the hip so the thigh can drive back.",
         "dose": "2×45s/side daily", "progression": "Add an active glute squeeze at end range."},
        {"name": "Glute bridges → single-leg", "why": "Wakes up the glutes for push-off.",
         "dose": "3×12, then 3×8/leg", "progression": "Hip thrusts with load."},
        {"name": "Bounding strides", "why": "Trains powerful hip extension at speed.",
         "dose": "4×20m, 1–2×/week", "progression": "Increase distance/height once smooth."},
    ],
    "knee_flexion_midstance": [
        {"name": "Soft-landing drops", "why": "Teaches the knee to bend and absorb on landing.",
         "dose": "3×8 quiet landings", "progression": "Single-leg landings."},
        {"name": "Downhill strides", "why": "Forces shock absorption through the knee.",
         "dose": "4×20s on a gentle slope", "progression": "Slightly steeper / faster."},
    ],
    "trunk_lean": [
        {"name": "Lean-and-run drill", "why": "Finds a small whole-body forward lean.",
         "dose": "5×20m", "progression": "Hold the lean through a steady minute."},
        {"name": "Dead bugs / planks", "why": "A stable core lets you lean without folding.",
         "dose": "3×30s", "progression": "Add limb loading."},
    ],
    "vertical_oscillation": [
        {"name": "Run-tall-past-a-rail", "why": "Keeps energy going forward, not up.",
         "dose": "4×20s keeping head height level", "progression": "Combine with higher cadence."},
        {"name": "Pogo hops", "why": "Trains stiff, low, springy contacts.",
         "dose": "3×10", "progression": "Single-leg pogos."},
    ],
    "contact_time": [
        {"name": "Ankle-stiffness skips", "why": "Shortens time on the ground.",
         "dose": "3×20m", "progression": "Faster turnover, same height."},
        {"name": "Pogo hops", "why": "Reactive strength for quicker contacts.",
         "dose": "3×10", "progression": "Add single-leg / depth pogos."},
    ],
    "pelvic_drop": [
        {"name": "Side planks", "why": "Builds lateral hip/core endurance to keep the pelvis level.",
         "dose": "3×30s/side", "progression": "Add top-leg raises."},
        {"name": "Banded hip-hikes", "why": "Directly trains the hip abductors that stop the drop.",
         "dose": "3×12/side", "progression": "Add load / standing on a step."},
        {"name": "Single-leg squats", "why": "Controls hip + knee under bodyweight on one leg.",
         "dose": "3×8/side", "progression": "Lower box / add weight."},
    ],
    "step_width": [
        {"name": "Two-rails cue runs", "why": "Widens a crossover gait.",
         "dose": "5×20s imagining a foot on each rail", "progression": "Keep it on easy runs."},
        {"name": "Banded lateral walks", "why": "Strengthens the base to stop crossing midline.",
         "dose": "3×12 steps/side", "progression": "Heavier band, lower stance."},
    ],
    "pronation": [
        {"name": "Heel raises", "why": "Calf/foot strength to control roll-in.",
         "dose": "3×15", "progression": "Single-leg, then off a step."},
        {"name": "Short-foot drill", "why": "Trains the arch muscles.",
         "dose": "3×10 holds/side", "progression": "Standing → single-leg balance."},
        {"name": "Check footwear", "why": "Worn or wrong-support shoes amplify roll-in.",
         "dose": "Review shoe wear; consider a fitting", "progression": "Trial a stability shoe if pronounced."},
    ],
    "lateral_trunk_sway": [
        {"name": "Pallof press", "why": "Anti-rotation core to steady the trunk.",
         "dose": "3×10/side", "progression": "Split-stance / half-kneeling."},
        {"name": "Side planks", "why": "Lateral stability feeding into the hips.",
         "dose": "3×30s/side", "progression": "Add reaches."},
    ],
    "asymmetry": [
        {"name": "Single-leg strength (weaker side)", "why": "Closes a left/right gap by training the lagging side.",
         "dose": "Extra 1–2 sets on the weaker side (squats, calf raises, hip-hikes)",
         "progression": "Re-test in ~4 weeks; even up once matched."},
        {"name": "Single-leg balance", "why": "Improves one-sided control and proprioception.",
         "dose": "3×30s/side, weaker side first", "progression": "Eyes closed / unstable surface."},
    ],
}

ALIASES = {
    "contact_time_ms": "contact_time",
    "foot_strike_angle": "overstride",
    "knee_flexion_contact": "knee_flexion_midstance",
    "stride_length": "asymmetry",
}


def build_plan(findings: List[dict], limit: int = 5) -> List[dict]:
    """Turn the prioritized findings into a deduped corrective plan."""
    seen = set()
    plan: List[dict] = []
    for f in findings:
        if f.get("severity") not in ("high", "med", "low"):
            continue
        key = "asymmetry" if str(f.get("title", "")).startswith("Left/right") else f.get("metric")
        key = ALIASES.get(key, key)
        if not key or key in seen or key not in EXERCISES:
            continue
        seen.add(key)
        plan.append({
            "key": key,
            "title": f.get("title"),
            "severity": f.get("severity"),
            "exercises": EXERCISES[key],
        })
        if len(plan) >= limit:
            break
    return plan
