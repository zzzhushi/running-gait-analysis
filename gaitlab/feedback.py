"""Rule-based coaching feedback.

Deterministic and explainable — each finding maps a metric (or asymmetry) that is out
of its target band to a plain-language explanation, a one-line cue you can think about
mid-run, and a corrective drill. No LLM, no API key. (An optional LLM layer could later
rephrase these; the structured findings stay the source of truth.)
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from . import asymmetry as asym_mod
from .geometry import clamp
from .targets import TARGETS

SEV_WEIGHT = {"high": 3, "med": 2, "low": 1, "good": 0}


def _val(values: Dict, key: str) -> float:
    v = values.get(key)
    return v if isinstance(v, (int, float)) else float("nan")


def build(values: Dict, per_side: Dict, asym: List[dict], view: str,
          foi: Dict, targets: Dict = None) -> Tuple[List[dict], float, str]:
    targets = targets or TARGETS
    items: List[dict] = []

    def add(sev, title, detail, cue, drill, metric=None, frame=None):
        items.append({
            "severity": sev, "title": title, "detail": detail,
            "cue": cue, "drill": drill, "metric": metric,
            "frame": frame,
        })

    is_side = view in ("side-left", "side-right")

    if is_side:
        cad = _val(values, "cadence")
        st = targets["cadence"].status(cad)
        if st != "good" and cad == cad:
            if cad < 170:
                add("high" if st == "bad" else "med",
                    "Increase your cadence",
                    f"Your cadence is about {cad:.0f} steps/min. Most runners are more efficient at "
                    "170-185. A low cadence usually goes hand-in-hand with overstriding and harder impacts.",
                    "Take quicker, lighter steps — aim to bump your step rate ~5-10% without speeding up.",
                    "Run 4x30s to a metronome set at your target cadence; jog easy between.",
                    "cadence")

        over = _val(values, "overstride")
        st = targets["overstride"].status(over)
        if st != "good" and over == over:
            add("high" if st == "bad" else "med",
                "You're overstriding",
                f"Your foot lands about {over:.0f}% of a leg-length ahead of your hips. Landing that far "
                "out in front creates a braking force on every step and raises impact loading.",
                "Let your foot land closer to under your hips, and lean slightly from the ankles — not the waist.",
                "High-cadence strides: 6x20s focusing on quick feet landing beneath you.",
                "overstride", foi.get("l_strike"))

        trunk = _val(values, "trunk_lean")
        st = targets["trunk_lean"].status(trunk)
        if trunk == trunk and trunk < 5:
            add("low", "Run a touch more forward",
                f"Your trunk is fairly upright ({trunk:.0f} deg). A small forward lean from the ankles helps "
                "you use gravity and reduces braking.",
                "Think 'tall, then tip' — a gentle whole-body lean from the ankles.",
                "Falling-start drill: stand tall, lean until you have to step, repeat into a run.",
                "trunk_lean")
        elif trunk == trunk and trunk > 16:
            add("med", "Too much trunk lean",
                f"You're leaning ~{trunk:.0f} deg forward, which can overload the lower back and hip flexors.",
                "Lift the chest and run a little taller; lean from the ankles, not by folding at the waist.",
                "Wall posture drill + core anti-extension work (dead bugs, planks).",
                "trunk_lean")

        kf = _val(values, "knee_flexion_midstance")
        st = targets["knee_flexion_midstance"].status(kf)
        if st == "bad" and kf == kf:
            add("med", "Stiff landing — let the knee bend",
                f"Your knee only bends ~{kf:.0f} deg at midstance. A stiffer leg absorbs less shock, so more "
                "impact travels to the joints.",
                "Aim for a soft, quiet landing — let the knee 'give' a little as you load it.",
                "Soft-landing drills and short downhill strides to train shock absorption.",
                "knee_flexion_midstance", foi.get("l_midstance"))

        ct = _val(values, "contact_time")
        st = targets["contact_time"].status(ct)
        if st != "good" and ct == ct:
            add("low", "Long ground contact",
                f"You're spending ~{ct:.0f} ms on the ground per step. Quicker, springier contacts tend to be "
                "more economical.",
                "Think 'hot pavement' — get off the ground a little faster.",
                "Pogo hops and ankle-stiffness skips, 3x10, twice a week.",
                "contact_time")

        he = _val(values, "hip_extension")
        st = targets["hip_extension"].status(he)
        if st != "good" and he == he:
            add("med" if st == "bad" else "low",
                "Limited hip extension",
                f"Your thigh drives only about {he:.0f}° behind you at push-off. Limited hip extension "
                "usually traces to tight hip flexors or under-active glutes, and it nudges you toward "
                "reaching out in front for stride length (overstriding) instead.",
                "Push the ground back behind you and stay tall through the hips.",
                "Hip-flexor mobility + glute activation: hip extensions, bridges, bounding strides.",
                "hip_extension", foi.get("l_toeoff"))

        kd = _val(values, "knee_drive")
        if targets["knee_drive"].status(kd) != "good" and kd == kd:
            add("low", "Limited knee drive",
                f"Your thigh swings forward only ~{kd:.0f}° in recovery. More knee drive sets up a longer, "
                "springier stride and helps you hold pace.",
                "Drive the knee forward and up a touch as the foot leaves the ground.",
                "A-skips and high-knee marching, building to bounding.",
                "knee_drive")

        ea = _val(values, "elbow_angle")
        if ea == ea and ea > 110:
            add("low", "Relax and bend your arms",
                f"Your elbows are quite straight (~{ea:.0f}°). Long, straight arms waste energy and tend to "
                "swing across your body.",
                "Bend the elbows to about 90° and swing front-to-back, hands relaxed.",
                "Arm-swing drill: 3×20s driving the elbows back, not across.",
                "elbow_angle")

        dfv = _val(values, "duty_factor")
        if targets["duty_factor"].status(dfv) == "bad" and dfv == dfv:
            add("low", "Long duty factor",
                f"Your foot is on the ground for ~{dfv:.0f}% of each stride. A shorter, springier contact tends "
                "to be faster and more economical.",
                "Quicker, lighter contacts — think 'off the ground fast'.",
                "Pogo hops and short hill sprints for reactive strength.",
                "duty_factor")

        vo = _val(values, "vertical_oscillation")
        st = targets["vertical_oscillation"].status(vo)
        if st == "bad" and vo == vo:
            add("low", "You're bouncing",
                f"Your hips travel up and down ~{vo:.0f}% of a leg-length each stride. Vertical bounce is energy "
                "spent fighting gravity instead of moving you forward.",
                "Drive forward, not up — keep the crown of your head on a level line.",
                "Run tall past a fence/rail and keep your head height steady.",
                "vertical_oscillation")

        fs = _val(values, "foot_strike_angle")
        if fs == fs and fs > 12 and over == over and over > 8:
            add("med", "Heavy heel-strike with overstriding",
                "You land clearly on the heel with the foot well ahead of you. Heel contact itself isn't bad, "
                "but combined with overstriding it amplifies braking and impact.",
                "Fixing the overstride (land under your hips) usually softens the heel-strike on its own.",
                "Same high-cadence strides as above; let foot-strike self-correct.",
                "foot_strike_angle", foi.get("l_strike"))
    else:
        pd = _val(values, "pelvic_drop")
        st = targets["pelvic_drop"].status(pd)
        if st != "good" and pd == pd:
            add("high" if st == "bad" else "med",
                "Hip drop (weak stabilizers)",
                f"Your pelvis drops about {pd:.0f} deg toward the swinging leg. Excess pelvic drop points to "
                "weak hip stabilizers and is linked to IT-band, knee, and hip pain.",
                "Run 'level hips' — imagine balancing a cup of water on each hip.",
                "Hip strength: single-leg squats, side planks, banded hip-hikes, 3x/week.",
                "pelvic_drop", foi.get("max_pelvic_drop"))

        if values.get("crossover"):
            add("med", "Crossover gait",
                "Your feet cross toward the midline at contact, which narrows your base and twists the load "
                "through the knee and IT band.",
                "Imagine running along two parallel rails, one foot on each.",
                "Banded lateral walks and single-leg balance to widen your base.",
                "step_width")

        sway = _val(values, "lateral_trunk_sway")
        if sway == sway and sway > 9:
            add("low", "Trunk swaying side to side",
                f"Your upper body sways ~{sway:.0f}% of a leg-length laterally each stride, often a knock-on of "
                "hip-drop or a weak core.",
                "Keep the chest steady and square to the front.",
                "Anti-rotation core work (Pallof press) + the hip drills above.",
                "lateral_trunk_sway")

        pr = _val(values, "pronation")
        st = targets["pronation"].status(pr)
        if st != "good" and pr == pr:
            add("low", "Possible overpronation (estimate)",
                f"The rear-foot appears to roll inward ~{pr:.0f}° at contact. This is a low-confidence 2-D "
                "rear-view estimate, so treat it as a prompt to look closer rather than a verdict.",
                "Check the wear pattern on your shoes; a stability shoe may help if it's pronounced.",
                "Calf and foot strength (heel raises, short-foot drills); review footwear with a fitter.",
                "pronation", foi.get("max_pelvic_drop"))

        if values.get("arm_crossover"):
            add("low", "Arms crossing your midline",
                "Your hands swing across the centre-line of your body. Cross-body arm swing drives a little "
                "rotation that your trunk and hips then have to cancel out.",
                "Swing the arms front-to-back like pistons; thumbs graze the hips.",
                "Mirror arm-swing drill — keep the hands from crossing your zipper line.",
                "arm_crossover")

    # --- asymmetry findings ---
    for a in asym[:3]:
        if a["status"] == "good":
            continue
        sev = "high" if a["status"] == "bad" else "med"
        add(sev, f"Left/right imbalance: {a['label']}",
            f"{a['label']} differs {a['diff_pct']:.0f}% between sides "
            f"(L {a['left']:.0f} vs R {a['right']:.0f} {a['unit']}), with the {a['worse_side']} side standing out. "
            "Imbalances over ~10% are worth addressing before they cause one-sided overuse.",
            f"Give the {a['worse_side']} side a little extra attention in strength work.",
            "Single-leg strength on the weaker side; film again in ~4 weeks to recheck.",
            a["key"])

    # positive note if nothing major
    if not any(i["severity"] in ("high", "med") for i in items):
        add("good", "Solid mechanics",
            "No major flags in this clip — your cadence, alignment, and symmetry look within healthy ranges.",
            "Keep doing what you're doing; recheck periodically.",
            "Maintain your current routine and strength work.", None)

    order = {"high": 0, "med": 1, "low": 2, "good": 3}
    items.sort(key=lambda i: order[i["severity"]])

    score, grade = _score(values, per_side, asym, view, targets)
    return items, score, grade


def _score(values: Dict, per_side: Dict, asym: List[dict], view: str, targets: Dict = None) -> Tuple[float, str]:
    targets = targets or TARGETS
    if view in ("side-left", "side-right"):
        keys = ["cadence", "trunk_lean", "knee_flexion_midstance", "overstride",
                "vertical_oscillation", "contact_time", "hip_extension", "knee_drive",
                "elbow_angle", "duty_factor"]
    else:
        keys = ["cadence", "pelvic_drop", "step_width", "lateral_trunk_sway", "pronation"]
    scores = []
    for k in keys:
        t = targets.get(k)
        v = values.get(k)
        if t and isinstance(v, (int, float)) and v == v:
            scores.append(t.score(v))
    base = sum(scores) / len(scores) if scores else 60.0
    penalty = clamp(asym_mod.overall_diff(asym) * 0.8, 0.0, 22.0)
    overall = clamp(base - penalty, 0.0, 100.0)
    grade = ("A" if overall >= 85 else "B" if overall >= 72 else
             "C" if overall >= 58 else "D" if overall >= 42 else "E")
    return round(overall, 1), grade
