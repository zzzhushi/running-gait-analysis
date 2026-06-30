"""Central metric registry: thresholds, coaching text, and exercises in one place.

Each MetricDef entry is the single source of truth for a metric. To change a
threshold, coaching cue, or drill — edit this file only.

finding_text keys:
  "low"  — value below the good band (too little of a good thing)
  "high" — value above the good band (too much)
  "any"  — fires regardless of direction (or for metrics that only flag one way)

Use {value} in detail strings; it is replaced with the measured value via .format().
For head_drop, {ref} is also available (the paired vertical_oscillation value).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

from .keys import MetricKey

GOOD, WARN, BAD = "good", "warn", "bad"


@dataclass
class MetricDef:
    """Runtime definition for one metric: scoring bands + all human-facing content."""

    key: MetricKey
    label: str
    unit: str
    good: Tuple[Optional[float], Optional[float]]
    warn: Tuple[Optional[float], Optional[float]]
    note: str = ""
    higher_is_better: Optional[bool] = None
    confidence: str = "high"        # "high" | "moderate" | "low"
    views: Tuple[str, ...] = ("side", "rear")
    scored: bool = True             # False = informational only, excluded from score
    per_side: bool = False          # True = contributes to asymmetry detection
    asym_direction: str = "neutral" # "higher_better" | "higher_worse" | "neutral"
    # Coaching text keyed by direction ("low", "high") or "any".
    # Each value: {"title": str, "detail": str, "cue": str, "drill": str}
    # {value} in detail is replaced with the measured value via .format().
    finding_text: Dict[str, Dict[str, str]] = field(default_factory=dict)
    exercises: List[Dict[str, str]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Scoring (same logic as the old targets.Target class)
    # ------------------------------------------------------------------

    def status(self, value: float) -> str:
        if value is None or value != value:
            return WARN
        if _within(value, self.good):
            return GOOD
        if _within(value, self.warn):
            return WARN
        return BAD

    def score(self, value: float) -> float:
        """0–100 score (100 = ideal mid-band, ~45 at warn edge, ~17 at deep BAD)."""
        if value is None or value != value:
            return 50.0
        if self.status(value) == GOOD:
            return 100.0
        lo_g, hi_g = self.good
        lo_w, hi_w = self.warn
        if lo_g is not None and value < lo_g:
            span = (lo_g - lo_w) if lo_w is not None else (lo_g if lo_g else 1.0)
            frac = (lo_g - value) / span if span else 1.0
        elif hi_g is not None and value > hi_g:
            span = (hi_w - hi_g) if hi_w is not None else (hi_g if hi_g else 1.0)
            frac = (value - hi_g) / span if span else 1.0
        else:
            frac = 0.0
        frac = max(0.0, min(1.5, frac))
        return max(0.0, 100.0 - 55.0 * frac)


def _within(value: float, band: Tuple[Optional[float], Optional[float]]) -> bool:
    lo, hi = band
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


# ---------------------------------------------------------------------------
# Central metric registry
# ---------------------------------------------------------------------------

METRIC_DEFS: Dict[MetricKey, MetricDef] = {

    MetricKey.CADENCE: MetricDef(
        key=MetricKey.CADENCE,
        label="Cadence",
        unit="spm",
        good=(170, 185),
        warn=(160, 195),
        note="Most runners are efficient at 170-185 steps/min. Low cadence usually means overstriding.",
        higher_is_better=True,
        confidence="high",
        views=("side", "rear"),
        scored=True,
        finding_text={
            "low": {
                "title": "Increase your cadence",
                "detail": (
                    "Your cadence is about {value:.0f} steps/min. Most runners are more efficient at "
                    "170-185. A low cadence usually goes hand-in-hand with overstriding and harder impacts."
                ),
                "cue": "Take quicker, lighter steps — aim to bump your step rate ~5-10% without speeding up.",
                "drill": "Run 4×30s to a metronome set at your target cadence; jog easy between.",
            },
            "high": {
                "title": "Your cadence is very high",
                "detail": (
                    "Your cadence is about {value:.0f} steps/min, above the typical efficient range. An "
                    "unusually high cadence can indicate overly short, shuffling steps and may limit "
                    "stride power."
                ),
                "cue": "Allow a little more flight time — let each stride open up a touch.",
                "drill": "Relaxed strides at easy pace focusing on full hip extension at push-off.",
            },
        },
        exercises=[
            {"name": "Metronome strides",
             "why": "Trains a quicker, lighter turnover.",
             "dose": "4×30s at target cadence, easy jog between",
             "progression": "Hold the new cadence for whole easy runs."},
            {"name": "Quick-feet A-skips",
             "why": "Grooves fast ground contacts.",
             "dose": "3×20m, 2–3×/week",
             "progression": "Add B-skips, then build to strides."},
        ],
    ),

    MetricKey.TRUNK_LEAN: MetricDef(
        key=MetricKey.TRUNK_LEAN,
        label="Trunk lean",
        unit="deg",
        good=(5, 12),
        warn=(0, 16),
        note="A slight forward lean from the ankles (~5-12 deg) helps. Upright = braking; too far = back load.",
        confidence="high",
        views=("side",),
        scored=True,
        finding_text={
            "low": {
                "title": "Run a touch more forward",
                "detail": (
                    "Your trunk is fairly upright ({value:.0f} deg). A small forward lean from the "
                    "ankles helps you use gravity and reduces braking."
                ),
                "cue": "Think 'tall, then tip' — a gentle whole-body lean from the ankles.",
                "drill": "Falling-start drill: stand tall, lean until you have to step, repeat into a run.",
            },
            "high": {
                "title": "Too much trunk lean",
                "detail": (
                    "You're leaning ~{value:.0f} deg forward, which can overload the lower back and "
                    "hip flexors."
                ),
                "cue": "Lift the chest and run a little taller; lean from the ankles, not by folding at the waist.",
                "drill": "Wall posture drill + core anti-extension work (dead bugs, planks).",
            },
        },
        exercises=[
            {"name": "Lean-and-run drill",
             "why": "Finds a small whole-body forward lean.",
             "dose": "5×20m",
             "progression": "Hold the lean through a steady minute."},
            {"name": "Dead bugs / planks",
             "why": "A stable core lets you lean without folding.",
             "dose": "3×30s",
             "progression": "Add limb loading."},
        ],
    ),

    MetricKey.KNEE_FLEXION_MIDSTANCE: MetricDef(
        key=MetricKey.KNEE_FLEXION_MIDSTANCE,
        label="Knee flexion (midstance)",
        unit="deg",
        good=(38, 50),
        warn=(28, 58),
        note="~40-50 deg of knee bend at midstance absorbs landing shock. Stiff knees jar the joints.",
        confidence="high",
        views=("side",),
        scored=True,
        per_side=True,
        asym_direction="higher_better",
        finding_text={
            "any": {
                "title": "Stiff landing — let the knee bend",
                "detail": (
                    "Your knee only bends ~{value:.0f} deg at midstance. A stiffer leg absorbs less "
                    "shock, so more impact travels to the joints."
                ),
                "cue": "Aim for a soft, quiet landing — let the knee 'give' a little as you load it.",
                "drill": "Soft-landing drills and short downhill strides to train shock absorption.",
            },
        },
        exercises=[
            {"name": "Soft-landing drops",
             "why": "Teaches the knee to bend and absorb on landing.",
             "dose": "3×8 quiet landings",
             "progression": "Single-leg landings."},
            {"name": "Downhill strides",
             "why": "Forces shock absorption through the knee.",
             "dose": "4×20s on a gentle slope",
             "progression": "Slightly steeper / faster."},
        ],
    ),

    MetricKey.OVERSTRIDE: MetricDef(
        key=MetricKey.OVERSTRIDE,
        label="Overstride",
        unit="%leg",
        good=(None, 8),
        warn=(None, 15),
        note="Foot should land close to under your hips. Landing far ahead (>~8% of leg length) brakes you.",
        confidence="high",
        views=("side",),
        scored=True,
        per_side=True,
        asym_direction="higher_worse",
        finding_text={
            "high": {
                "title": "You're overstriding",
                "detail": (
                    "Your foot lands about {value:.0f}% of a leg-length ahead of your hips. Landing "
                    "that far out in front creates a braking force on every step and raises impact loading."
                ),
                "cue": "Let your foot land closer to under your hips, and lean slightly from the ankles — not the waist.",
                "drill": "High-cadence strides: 6×20s focusing on quick feet landing beneath you.",
            },
        },
        exercises=[
            {"name": "High-cadence strides",
             "why": "Pulls the foot-strike back under your hips.",
             "dose": "6×20s focusing on landing beneath you",
             "progression": "Blend into tempo running."},
            {"name": "Falling-start runs",
             "why": "Teaches leaning from the ankles, not reaching.",
             "dose": "6×20m from a tall lean",
             "progression": "Carry the lean into a relaxed cruise."},
            {"name": "Wall posture drill",
             "why": "Builds the tall, forward-from-the-ankle position.",
             "dose": "3×30s holds",
             "progression": "Add a marching knee-drive."},
        ],
    ),

    MetricKey.VERTICAL_OSCILLATION: MetricDef(
        key=MetricKey.VERTICAL_OSCILLATION,
        label="Vertical oscillation",
        unit="%leg",
        good=(None, 12),
        warn=(None, 18),
        note="Bouncing wastes energy. Lower vertical travel of the hips is generally more economical.",
        confidence="high",
        views=("side",),
        scored=True,
        finding_text={
            "high": {
                "title": "You're bouncing",
                "detail": (
                    "Your hips travel up and down ~{value:.0f}% of a leg-length each stride. Vertical "
                    "bounce is energy spent fighting gravity instead of moving you forward."
                ),
                "cue": "Drive forward, not up — keep the crown of your head on a level line.",
                "drill": "Run tall past a fence/rail and keep your head height steady.",
            },
        },
        exercises=[
            {"name": "Run-tall-past-a-rail",
             "why": "Keeps energy going forward, not up.",
             "dose": "4×20s keeping head height level",
             "progression": "Combine with higher cadence."},
            {"name": "Pogo hops",
             "why": "Trains stiff, low, springy contacts.",
             "dose": "3×10",
             "progression": "Single-leg pogos."},
        ],
    ),

    MetricKey.CONTACT_TIME: MetricDef(
        key=MetricKey.CONTACT_TIME,
        label="Ground contact time",
        unit="ms",
        good=(None, 250),
        warn=(None, 300),
        note="Efficient runners spend ~200-250 ms on the ground per step. Long contact = less reactive.",
        confidence="high",
        views=("side",),
        scored=True,
        finding_text={
            "high": {
                "title": "Long ground contact",
                "detail": (
                    "You're spending ~{value:.0f} ms on the ground per step. Quicker, springier contacts "
                    "tend to be more economical."
                ),
                "cue": "Think 'hot pavement' — get off the ground a little faster.",
                "drill": "Pogo hops and ankle-stiffness skips, 3×10, twice a week.",
            },
        },
        exercises=[
            {"name": "Ankle-stiffness skips",
             "why": "Shortens time on the ground.",
             "dose": "3×20m",
             "progression": "Faster turnover, same height."},
            {"name": "Pogo hops",
             "why": "Reactive strength for quicker contacts.",
             "dose": "3×10",
             "progression": "Add single-leg / depth pogos."},
        ],
    ),

    MetricKey.DUTY_FACTOR: MetricDef(
        key=MetricKey.DUTY_FACTOR,
        label="Duty factor",
        unit="%",
        good=(None, 40),
        warn=(None, 48),
        note="Share of the stride your foot is on the ground. Lower is springier/faster (fps-limited estimate).",
        confidence="high",
        views=("side",),
        scored=True,
        finding_text={
            "high": {
                "title": "Long duty factor",
                "detail": (
                    "Your foot is on the ground for ~{value:.0f}% of each stride. A shorter, springier "
                    "contact tends to be faster and more economical."
                ),
                "cue": "Quicker, lighter contacts — think 'off the ground fast'.",
                "drill": "Pogo hops and short hill sprints for reactive strength.",
            },
        },
        exercises=[
            {"name": "Pogo hops",
             "why": "Reactive strength to shorten ground contact.",
             "dose": "3×10",
             "progression": "Single-leg / depth pogos."},
            {"name": "Short hill sprints",
             "why": "Power and a springier contact.",
             "dose": "6×10s steep hill, walk back",
             "progression": "Add reps over weeks."},
        ],
    ),

    MetricKey.HIP_EXTENSION: MetricDef(
        key=MetricKey.HIP_EXTENSION,
        label="Hip extension (peak)",
        unit="deg",
        good=(10, None),
        warn=(5, None),
        note=(
            "How far the thigh drives behind you at push-off. Limited extension often means tight hip "
            "flexors or under-active glutes — and a tendency to overstride to compensate."
        ),
        higher_is_better=True,
        confidence="high",
        views=("side",),
        scored=True,
        per_side=True,
        asym_direction="higher_better",
        finding_text={
            "low": {
                "title": "Limited hip extension",
                "detail": (
                    "Your thigh drives only about {value:.0f}° behind you at push-off. Limited hip "
                    "extension usually traces to tight hip flexors or under-active glutes, and it nudges "
                    "you toward reaching out in front for stride length (overstriding) instead."
                ),
                "cue": "Push the ground back behind you and stay tall through the hips.",
                "drill": "Hip-flexor mobility + glute activation: hip extensions, bridges, bounding strides.",
            },
        },
        exercises=[
            {"name": "Couch stretch (hip flexors)",
             "why": "Frees the front of the hip so the thigh can drive back.",
             "dose": "2×45s/side daily",
             "progression": "Add an active glute squeeze at end range."},
            {"name": "Glute bridges → single-leg",
             "why": "Wakes up the glutes for push-off.",
             "dose": "3×12, then 3×8/leg",
             "progression": "Hip thrusts with load."},
            {"name": "Bounding strides",
             "why": "Trains powerful hip extension at speed.",
             "dose": "4×20m, 1–2×/week",
             "progression": "Increase distance/height once smooth."},
        ],
    ),

    MetricKey.KNEE_DRIVE: MetricDef(
        key=MetricKey.KNEE_DRIVE,
        label="Knee drive (peak)",
        unit="deg",
        good=(20, None),
        warn=(10, None),
        note="How far the thigh swings forward in recovery. More knee drive feeds a longer, springier stride.",
        higher_is_better=True,
        confidence="high",
        views=("side",),
        scored=True,
        per_side=True,
        asym_direction="higher_better",
        finding_text={
            "low": {
                "title": "Limited knee drive",
                "detail": (
                    "Your thigh swings forward only ~{value:.0f}° in recovery. More knee drive sets up "
                    "a longer, springier stride and helps you hold pace."
                ),
                "cue": "Drive the knee forward and up a touch as the foot leaves the ground.",
                "drill": "A-skips and high-knee marching, building to bounding.",
            },
        },
        exercises=[
            {"name": "A-skips",
             "why": "Grooves an active forward-up knee drive.",
             "dose": "3×20m",
             "progression": "A-skips → bounding."},
            {"name": "High-knee marching",
             "why": "Strength and pattern for the knee lift.",
             "dose": "3×20m",
             "progression": "Add a run-out at the end."},
        ],
    ),

    MetricKey.ELBOW_ANGLE: MetricDef(
        key=MetricKey.ELBOW_ANGLE,
        label="Elbow angle",
        unit="deg",
        good=(75, 105),
        warn=(60, 120),
        note="A relaxed ~90° elbow. Very straight arms waste energy and tend to swing across the body.",
        confidence="high",
        views=("side",),
        scored=True,
        per_side=True,
        asym_direction="neutral",
        finding_text={
            "high": {
                "title": "Relax and bend your arms",
                "detail": (
                    "Your elbows are quite straight (~{value:.0f}°). Long, straight arms waste energy "
                    "and tend to swing across your body."
                ),
                "cue": "Bend the elbows to about 90° and swing front-to-back, hands relaxed.",
                "drill": "Arm-swing drill: 3×20s driving the elbows back, not across.",
            },
        },
        exercises=[
            {"name": "Arm-swing drill",
             "why": "Trains a relaxed ~90° elbow swinging front-to-back.",
             "dose": "3×20s, tall and relaxed",
             "progression": "Carry the cue into easy runs."},
        ],
    ),

    MetricKey.PELVIC_DROP: MetricDef(
        key=MetricKey.PELVIC_DROP,
        label="Pelvic drop",
        unit="deg",
        good=(None, 6),
        warn=(None, 10),
        note="The hip of the swinging leg dropping >~10 deg points to weak hip stabilizers (injury risk).",
        confidence="moderate",  # value-dependent per R3.3; < ~4° is near noise floor
        views=("rear",),
        scored=True,
        per_side=True,
        asym_direction="higher_worse",
        finding_text={
            "high": {
                "title": "Hip drop (weak stabilizers)",
                "detail": (
                    "Your pelvis drops about {value:.0f} deg toward the swinging leg. Excess pelvic drop "
                    "points to weak hip stabilizers and is linked to IT-band, knee, and hip pain."
                ),
                "cue": "Run 'level hips' — imagine balancing a cup of water on each hip.",
                "drill": "Hip strength: single-leg squats, side planks, banded hip-hikes, 3×/week.",
            },
        },
        exercises=[
            {"name": "Side planks",
             "why": "Builds lateral hip/core endurance to keep the pelvis level.",
             "dose": "3×30s/side",
             "progression": "Add top-leg raises."},
            {"name": "Banded hip-hikes",
             "why": "Directly trains the hip abductors that stop the drop.",
             "dose": "3×12/side",
             "progression": "Add load / standing on a step."},
            {"name": "Single-leg squats",
             "why": "Controls hip + knee under bodyweight on one leg.",
             "dose": "3×8/side",
             "progression": "Lower box / add weight."},
        ],
    ),

    MetricKey.PRONATION: MetricDef(
        key=MetricKey.PRONATION,
        label="Pronation (estimate)",
        unit="deg",
        good=(None, 8),
        warn=(None, 12),
        note=(
            "Estimated rear-foot roll-in at contact. This is a low-confidence 2-D rear-view estimate — "
            "treat it as a flag to check your shoe wear and ankle, not a measurement."
        ),
        confidence="low",
        views=("rear",),
        scored=False,  # R17.1: low confidence, excluded from headline score
        per_side=True,
        asym_direction="higher_worse",
        finding_text={
            "high": {
                "title": "Possible overpronation (estimate)",
                "detail": (
                    "The rear-foot appears to roll inward ~{value:.0f}° at contact. This is a "
                    "low-confidence 2-D rear-view estimate, so treat it as a prompt to look closer "
                    "rather than a verdict."
                ),
                "cue": "Check the wear pattern on your shoes; a stability shoe may help if it's pronounced.",
                "drill": "Calf and foot strength (heel raises, short-foot drills); review footwear with a fitter.",
            },
        },
        exercises=[
            {"name": "Heel raises",
             "why": "Calf/foot strength to control roll-in.",
             "dose": "3×15",
             "progression": "Single-leg, then off a step."},
            {"name": "Short-foot drill",
             "why": "Trains the arch muscles.",
             "dose": "3×10 holds/side",
             "progression": "Standing → single-leg balance."},
            {"name": "Check footwear",
             "why": "Worn or wrong-support shoes amplify roll-in.",
             "dose": "Review shoe wear; consider a fitting",
             "progression": "Trial a stability shoe if pronounced."},
        ],
    ),

    MetricKey.STEP_WIDTH: MetricDef(
        key=MetricKey.STEP_WIDTH,
        label="Step width / crossover",
        unit="%leg",
        good=(2, 14),
        warn=(0, 22),
        note="Feet should not cross the midline. Crossover narrows your base and stresses the IT band.",
        confidence="high",
        views=("rear",),
        scored=True,
        finding_text={
            "low": {
                "title": "Crossover gait",
                "detail": (
                    "Your feet cross toward the midline at contact, which narrows your base and twists "
                    "the load through the knee and IT band."
                ),
                "cue": "Imagine running along two parallel rails, one foot on each.",
                "drill": "Banded lateral walks and single-leg balance to widen your base.",
            },
        },
        exercises=[
            {"name": "Two-rails cue runs",
             "why": "Widens a crossover gait.",
             "dose": "5×20s imagining a foot on each rail",
             "progression": "Keep it on easy runs."},
            {"name": "Banded lateral walks",
             "why": "Strengthens the base to stop crossing midline.",
             "dose": "3×12 steps/side",
             "progression": "Heavier band, lower stance."},
        ],
    ),

    MetricKey.LATERAL_TRUNK_SWAY: MetricDef(
        key=MetricKey.LATERAL_TRUNK_SWAY,
        label="Lateral trunk sway",
        unit="%leg",
        good=(None, 8),
        warn=(None, 12),
        note="Side-to-side lean of the upper body. A lot of sway often follows hip drop or a weak core.",
        confidence="high",
        views=("rear",),
        scored=True,
        finding_text={
            "high": {
                "title": "Trunk swaying side to side",
                "detail": (
                    "Your upper body sways ~{value:.0f}% of a leg-length laterally each stride, often "
                    "a knock-on of hip-drop or a weak core."
                ),
                "cue": "Keep the chest steady and square to the front.",
                "drill": "Anti-rotation core work (Pallof press) + the hip drills above.",
            },
        },
        exercises=[
            {"name": "Pallof press",
             "why": "Anti-rotation core to steady the trunk.",
             "dose": "3×10/side",
             "progression": "Split-stance / half-kneeling."},
            {"name": "Side planks",
             "why": "Lateral stability feeding into the hips.",
             "dose": "3×30s/side",
             "progression": "Add reaches."},
        ],
    ),

    MetricKey.ASYMMETRY: MetricDef(
        key=MetricKey.ASYMMETRY,
        label="Left/right asymmetry",
        unit="%",
        good=(None, 5),
        warn=(None, 10),
        note="Under ~5% difference left-to-right is normal. Over ~10% is worth addressing.",
        confidence="high",
        views=("side", "rear"),
        scored=True,
        exercises=[
            {"name": "Single-leg strength (weaker side)",
             "why": "Closes a left/right gap by training the lagging side.",
             "dose": "Extra 1–2 sets on the weaker side (squats, calf raises, hip-hikes)",
             "progression": "Re-test in ~4 weeks; even up once matched."},
            {"name": "Single-leg balance",
             "why": "Improves one-sided control and proprioception.",
             "dose": "3×30s/side, weaker side first",
             "progression": "Eyes closed / unstable surface."},
        ],
    ),

    # -----------------------------------------------------------------------
    # Per-side-only entries (contribute to asymmetry, not globally scored)
    # -----------------------------------------------------------------------

    MetricKey.KNEE_FLEXION_CONTACT: MetricDef(
        key=MetricKey.KNEE_FLEXION_CONTACT,
        label="Knee flexion (contact)",
        unit="deg",
        good=(None, None),
        warn=(None, None),
        note="Knee bend angle at initial foot contact. Informational; more flex = softer landing.",
        confidence="high",
        views=("side",),
        scored=False,
        per_side=True,
        asym_direction="neutral",
    ),

    MetricKey.FOOT_STRIKE_ANGLE: MetricDef(
        key=MetricKey.FOOT_STRIKE_ANGLE,
        label="Foot-strike angle",
        unit="deg",
        good=(None, None),
        warn=(None, None),
        note=(
            "Where your foot first contacts: heel, midfoot, or forefoot. None is inherently bad — "
            "it's the overstride that matters."
        ),
        confidence="moderate",
        views=("side",),
        scored=False,
        per_side=True,
        asym_direction="neutral",
        finding_text={
            "any": {
                "title": "Heavy heel-strike with overstriding",
                "detail": (
                    "You land clearly on the heel with the foot well ahead of you. Heel contact itself "
                    "isn't bad, but combined with overstriding it amplifies braking and impact."
                ),
                "cue": "Fixing the overstride (land under your hips) usually softens the heel-strike on its own.",
                "drill": "Same high-cadence strides as above; let foot-strike self-correct.",
            },
        },
    ),

    MetricKey.CONTACT_TIME_MS: MetricDef(
        key=MetricKey.CONTACT_TIME_MS,
        label="Ground contact time",
        unit="ms",
        good=(None, 250),
        warn=(None, 300),
        note="Per-side contact time in milliseconds. Used for left/right asymmetry detection.",
        confidence="high",
        views=("side",),
        scored=False,
        per_side=True,
        asym_direction="higher_worse",
    ),

    MetricKey.ARM_SWING: MetricDef(
        key=MetricKey.ARM_SWING,
        label="Arm swing",
        unit="%leg",
        good=(None, None),
        warn=(None, None),
        note="Fore-aft arm drive. Aim for relaxed, even swing front-to-back (not across the body).",
        confidence="moderate",
        views=("side",),
        scored=False,
        per_side=True,
        asym_direction="neutral",
    ),

    MetricKey.HEEL_RECOVERY: MetricDef(
        key=MetricKey.HEEL_RECOVERY,
        label="Heel recovery",
        unit="%leg",
        good=(None, None),
        warn=(None, None),
        note="How much the heel picks up in swing (proxy). More recovery = a shorter, springier swing leg.",
        confidence="moderate",
        views=("side",),
        scored=False,
        per_side=True,
        asym_direction="neutral",
    ),

    MetricKey.STRIDE_LENGTH: MetricDef(
        key=MetricKey.STRIDE_LENGTH,
        label="Stride length",
        unit="m",
        good=(None, None),
        warn=(None, None),
        note="From treadmill speed × stride time. Requires speed input.",
        confidence="moderate",
        views=("side",),
        scored=False,
        per_side=True,
        asym_direction="higher_better",
    ),

    MetricKey.STEP_LENGTH: MetricDef(
        key=MetricKey.STEP_LENGTH,
        label="Step length",
        unit="m",
        good=(None, None),
        warn=(None, None),
        note="Distance per step (speed × step time). Requires speed input.",
        confidence="moderate",
        views=("side",),
        scored=False,
        per_side=True,
        asym_direction="higher_better",
    ),

    # -----------------------------------------------------------------------
    # Arm crossover — boolean flag, no thresholds
    # -----------------------------------------------------------------------

    MetricKey.ARM_CROSSOVER: MetricDef(
        key=MetricKey.ARM_CROSSOVER,
        label="Arm crossover",
        unit="",
        good=(None, None),
        warn=(None, None),
        note="Arms swinging across the body midline add rotation that the trunk has to cancel out.",
        confidence="moderate",
        views=("rear",),
        scored=False,
        finding_text={
            "any": {
                "title": "Arms crossing your midline",
                "detail": (
                    "Your hands swing across the centre-line of your body. Cross-body arm swing drives "
                    "a little rotation that your trunk and hips then have to cancel out."
                ),
                "cue": "Swing the arms front-to-back like pistons; thumbs graze the hips.",
                "drill": "Mirror arm-swing drill — keep the hands from crossing your zipper line.",
            },
        },
        exercises=[
            {"name": "Mirror arm-swing drill",
             "why": "Stops cross-body swing that adds rotation.",
             "dose": "3×20s, hands not crossing the midline",
             "progression": "Carry the cue into runs."},
        ],
    ),

    MetricKey.HEAD_DROP: MetricDef(
        key=MetricKey.HEAD_DROP,
        label="Head bobbing",
        unit="%leg",
        good=(None, None),
        warn=(None, None),
        note=(
            "Vertical head-crown bounce per stride. Ideally tracks with hip VO; "
            "a much higher value suggests the head is nodding independently."
        ),
        confidence="moderate",
        views=("side",),
        scored=False,
        finding_text={
            "high": {
                "title": "Head bobbing",
                "detail": (
                    "Your head bounces ~{value:.1f}% of a leg-length per stride — noticeably more than "
                    "your hip ({ref:.1f}%). Extra head movement is wasted energy and can contribute to "
                    "neck and upper-back fatigue."
                ),
                "cue": "Keep your chin level and fix your gaze on the horizon — imagine a book balanced on your head.",
                "drill": "Head-still drill: run alongside a fence and keep your eye level steady for 30 s at a time.",
            },
        },
    ),

    MetricKey.HEAD_LATERAL_SWAY: MetricDef(
        key=MetricKey.HEAD_LATERAL_SWAY,
        label="Head lateral sway",
        unit="%leg",
        good=(None, 6),
        warn=(None, 10),
        note="Side-to-side head movement per stride (rear view). Excess sway signals poor upper-body stability.",
        confidence="moderate",
        views=("rear",),
        scored=False,
        finding_text={
            "high": {
                "title": "Head swaying side to side",
                "detail": (
                    "Your head moves ~{value:.1f}% of a leg-length laterally per stride. "
                    "Excess head sway wastes energy and can strain the neck and upper back."
                ),
                "cue": "Fix your gaze on a distant point and keep your head still over your shoulders as you run.",
                "drill": "Head-still drill: run and hold your eye level steady for 30 s. Pair with lateral hip work.",
            },
        },
    ),
}


# ---------------------------------------------------------------------------
# Personalisation
# ---------------------------------------------------------------------------

def personalize(profile: Optional[dict]) -> Dict[MetricKey, MetricDef]:
    """Return a copy of METRIC_DEFS with bands adjusted for the runner's profile.

    - Cadence is centred on stature (leg length preferred, else height) and nudged
      up with pace — shorter runners and faster paces both raise the efficient cadence.
    - Pelvic-drop band widens slightly for female runners (wider pelvis / larger Q-angle).
    """
    defs = dict(METRIC_DEFS)
    if not profile:
        return defs

    sex = (profile.get("sex") or "").lower()
    height = profile.get("height_cm")
    leg = profile.get("leg_length_cm")
    speed = profile.get("speed_kmh")

    h = (leg / 0.48) if leg else height
    if h:
        center = 188.0 - 0.615 * (float(h) - 157.0)
        if speed:
            center += 1.2 * (float(speed) - 10.0)
        center = max(160.0, min(200.0, center))
        note = (
            f"Personalized to your stature{' and speed' if speed else ''}: you're likely most "
            f"efficient near {center:.0f} steps/min. Shorter runners and faster paces sit higher "
            "than the old '180' rule of thumb."
        )
        defs[MetricKey.CADENCE] = replace(
            METRIC_DEFS[MetricKey.CADENCE],
            good=(round(center - 7), round(center + 7)),
            warn=(round(center - 14), round(center + 14)),
            note=note,
        )

    if sex == "female":
        base = METRIC_DEFS[MetricKey.PELVIC_DROP]
        defs[MetricKey.PELVIC_DROP] = replace(
            base,
            good=(None, 7),
            warn=(None, 11),
            note=base.note + " (Range set for female norms, which typically show a little more pelvic motion.)",
        )

    return defs
