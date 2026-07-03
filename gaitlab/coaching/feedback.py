"""Rule-based coaching feedback.

Deterministic and explainable — each finding maps a metric that is out of its target
band to a plain-language explanation, cue, and corrective drill sourced from the central
METRIC_DEFS registry. No LLM, no API key.

Finding text is defined in gaitlab/metrics/defs.py — to change coaching copy, edit there.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..core.geometry import clamp
from ..metrics import asymmetry as asym_mod
from ..metrics.defs import METRIC_DEFS
from ..metrics.keys import MetricKey

MK = MetricKey  # local shorthand


def _val(values: Dict, key) -> float:
    v = values.get(key)
    return v if isinstance(v, (int, float)) else float("nan")


def _direction(value: float, band: Tuple) -> str:
    """Return "low", "high", or "any" based on where value falls relative to band."""
    lo, hi = band
    if lo is not None and value < lo:
        return "low"
    if hi is not None and value > hi:
        return "high"
    return "any"


def _mk(sev, title, detail, cue, drill, metric):
    return {"severity": sev, "title": title, "detail": detail, "cue": cue,
            "drill": drill, "metric": metric, "frame": None}


def _composites(values: Dict, view: str, targets: Dict) -> List[Tuple[dict, set]]:
    """Fired composite patterns (tech_requirements.md §14) as (finding, superseded_keys).

    A composite is a conjunction of thresholded metrics; it outranks (supersedes) its
    component single-metric findings. Thresholds are read from each metric's own
    MetricDef band via `_bound()` (falling back to a literal only if the band is
    unset) so a composite can't silently drift from the registry if a band changes.
    """
    v = lambda k: _val(values, k)

    def ok(*xs):
        return all(x == x for x in xs)  # all non-NaN

    def bound(key, edge, side, fallback):
        """edge: 'good' or 'warn'; side: 0 (low bound) or 1 (high bound)."""
        t = targets.get(key)
        band = getattr(t, edge, None) if t else None
        val = band[side] if band else None
        return val if val is not None else fallback

    out: List[Tuple[dict, set]] = []

    if view in ("side-left", "side-right"):
        cad, over, he = v(MK.CADENCE), v(MK.OVERSTRIDE), v(MK.HIP_EXTENSION)
        kfm, tl, vo, fs = v(MK.KNEE_FLEXION_MIDSTANCE), v(MK.TRUNK_LEAN), v(MK.VERTICAL_OSCILLATION), v(MK.FOOT_STRIKE_ANGLE)
        kd = v(MK.KNEE_DRIVE)
        t_cad = targets.get(MK.CADENCE)
        cad_lo = t_cad.good[0] if t_cad and t_cad.good[0] is not None else 170
        cad_hi = t_cad.good[1] if t_cad and t_cad.good[1] is not None else 190
        over_hi = bound(MK.OVERSTRIDE, "good", 1, 8)
        he_lo = bound(MK.HIP_EXTENSION, "good", 0, 10)
        kfm_hi = bound(MK.KNEE_FLEXION_MIDSTANCE, "good", 1, 50)
        tl_hi = bound(MK.TRUNK_LEAN, "warn", 1, 16)
        vo_hi = bound(MK.VERTICAL_OSCILLATION, "warn", 1, 18)
        kd_lo = bound(MK.KNEE_DRIVE, "good", 0, 20)
        # foot_strike_angle has no good/warn band by design (no strike pattern is
        # inherently "good" or "bad" on its own — see its MetricDef note) — this
        # cutoff is specific to the heavy-heelstrike composite, not a registry value.
        fs_hi = 12

        # R14.1 — overstriding / reaching
        if ok(over, he, cad) and over > over_hi and he < he_lo and cad < cad_lo:
            out.append((_mk(
                "high", "Overstriding — quicken your cadence",
                f"You're reaching out in front: the foot lands ~{over:.0f}% of a leg ahead of your hips, "
                f"hip extension is limited (~{he:.0f}°), and cadence is low (~{cad:.0f} spm). Together these "
                "brake you on every step and raise impact loading.",
                "Lift cadence ~5-10% and let the foot land under your hips.",
                "High-cadence strides (6×20s) + couch stretch and glute bridges for hip extension.",
                "overstriding"), {"overstride", "hip_extension", "cadence"}))

        # R14.2 — sinking at mid-stance
        if ok(kfm, tl) and kfm > kfm_hi and tl > tl_hi:
            out.append((_mk(
                "high", "Sinking into mid-stance",
                f"Your knee collapses (~{kfm:.0f}° flexion) while the trunk pitches forward (~{tl:.0f}°) at "
                "mid-stance — a sign the stance leg and core aren't holding you tall.",
                "Run tall; don't sink into the stance leg.",
                "Glute bridges and anti-extension core work (dead bugs, planks).",
                "sinking_midstance"), {"knee_flexion_midstance", "trunk_lean"}))

        # R14.3 — bouncing
        if ok(vo, cad) and vo > vo_hi and cad < cad_lo:
            out.append((_mk(
                "high", "Bouncing — drive forward, not up",
                f"Your hips travel ~{vo:.0f}% of a leg vertically each stride at a low cadence (~{cad:.0f} spm), "
                "so drive is going up instead of forward.",
                "Lift cadence and keep the crown of your head on a level line.",
                "Run-tall-past-a-rail (4×20s) and pogo hops (3×10).",
                "bouncing"), {"vertical_oscillation", "cadence"}))

        # R14.4 — heavy heel-strike + overstride
        if ok(fs, over) and fs > fs_hi and over > over_hi:
            out.append((_mk(
                "med", "Heavy heel-strike with overstriding",
                "You land clearly on the heel with the foot well ahead of you. Heel contact itself isn't bad, "
                "but combined with overstriding it amplifies braking and impact.",
                "Fixing the overstride (land under your hips) usually softens the heel-strike on its own.",
                "High-cadence strides focusing on landing beneath you.",
                "heavy_heelstrike"), {"foot_strike_angle"}))

        # R14.6 — under-powered push-off / shuffle
        if ok(he, kd, cad) and he < he_lo and kd < kd_lo and cad > cad_hi:
            out.append((_mk(
                "med", "Shuffling — drive from the hip, not just the feet",
                f"Hip extension (~{he:.0f}°) and knee drive (~{kd:.0f}°) are both limited, and cadence is "
                f"high (~{cad:.0f} spm) — short, quick steps standing in for a powerful push-off.",
                "Push the ground back behind you and drive the knee forward; let each stride open up a touch.",
                "Hip-flexor mobility + glute activation (bridges) and A-skips for an active knee drive.",
                "underpowered_pushoff"), {"hip_extension", "knee_drive"}))

    else:
        pd, ha = v(MK.PELVIC_DROP), v(MK.HIP_ADDUCTION)
        crossover, sway = bool(values.get(MK.ARM_CROSSOVER)), v(MK.LATERAL_TRUNK_SWAY)
        pd_hi = bound(MK.PELVIC_DROP, "good", 1, 6)
        ha_hi = bound(MK.HIP_ADDUCTION, "good", 1, 8)
        sway_hi = bound(MK.LATERAL_TRUNK_SWAY, "good", 1, 8)

        # R14.5 — lateral chain: pelvis drops AND the hip/knee collapses inward together
        if ok(pd, ha) and pd > pd_hi and ha > ha_hi:
            out.append((_mk(
                "high", "Lateral hip collapse (weak stabilizers)",
                f"Your pelvis drops (~{pd:.0f}°) while the hip/knee collapses inward toward the midline "
                f"(~{ha:.0f}°) at the same time — together these point to weak hip abductors letting the "
                "whole lateral chain give way, not just one piece of it.",
                "Run 'level hips, knees tracking straight' — resist both the drop and the inward collapse.",
                "Hip-abductor strength: side planks, banded hip-hikes/clamshells, single-leg squats, 3x/week.",
                "lateral_chain"), {"pelvic_drop", "hip_adduction"}))

        # R14.7 — excess upper-body rotation
        if crossover and sway == sway and sway > sway_hi:
            out.append((_mk(
                "med", "Upper body rotating and swaying together",
                f"Your arms cross the midline while the trunk sways ~{sway:.0f}% of a leg-length laterally "
                "each stride — the cross-body arm swing is likely feeding the trunk sway, not just riding along with it.",
                "Swing the arms front-to-back like pistons; that alone often settles the trunk down.",
                "Mirror arm-swing drill (piston arms) + Pallof press for anti-rotation core control.",
                "upper_body_rotation"), {"lateral_trunk_sway", "arm_crossover"}))

    return out


def _one_sided_deficit(asym: List[dict]) -> Tuple[Optional[dict], set]:
    """R14.8 — consistent one-sided deficit (meta-asymmetry): the same side comes out
    worse across several per-side metrics. Pure self-comparison (no absolute cutoffs
    needed), which is the most defensible signal available given how little validated
    injury threshold evidence exists. Supersedes the individual asymmetry findings it
    absorbs so the same side isn't called out repeatedly.
    """
    flagged = [a for a in asym if a["status"] != "good"]
    by_side: Dict[str, List[dict]] = {"left": [], "right": []}
    for a in flagged:
        by_side[a["worse_side"]].append(a)
    left_n, right_n = len(by_side["left"]), len(by_side["right"])
    if left_n < 2 and right_n < 2:
        return None, set()
    if left_n == right_n:
        return None, set()  # ambiguous — don't guess which side
    side, entries = ("left", by_side["left"]) if left_n > right_n else ("right", by_side["right"])
    labels = ", ".join(a["label"] for a in entries)
    finding = _mk(
        "high", f"Your {side} side is consistently doing less",
        f"Across {len(entries)} measures ({labels}), your {side} side comes out worse every time. "
        "That consistency is a more useful signal than any single metric alone — it points to a real, "
        "one-sided pattern rather than noise.",
        f"Prioritize strength and mobility work on the {side} side specifically.",
        f"Single-leg strength on the {side} side (squats, calf raises, hip work); re-film in ~4 weeks to recheck.",
        "one_sided_deficit",
    )
    return finding, {a["key"] for a in entries}


def _finding(targets: Dict, key: MetricKey, value: float, direction: Optional[str] = None) -> Optional[dict]:
    """Look up finding_text from METRIC_DEFS (not personalized targets) for the given key/direction.

    Uses METRIC_DEFS for the coaching text (base copy); personalized targets only adjust bands.
    """
    if value != value:  # NaN
        return None
    base_def = METRIC_DEFS.get(key)
    if not base_def or not base_def.finding_text:
        return None
    d = direction or _direction(value, targets[key].good if key in targets else (None, None))
    return base_def.finding_text.get(d) or base_def.finding_text.get("any")


def build(values: Dict, per_side: Dict, asym: List[dict], view: str,
          foi: Dict, targets: Dict = None) -> Tuple[List[dict], float, str]:
    targets = targets or METRIC_DEFS
    items: List[dict] = []

    def add(sev, title, detail, cue, drill, metric=None, frame=None):
        items.append({
            "severity": sev, "title": title, "detail": detail,
            "cue": cue, "drill": drill, "metric": metric,
            "frame": frame,
        })

    def _add_from_def(sev, key, value, frame=None, extra_fmt=None):
        """Emit a finding for key using text from METRIC_DEFS."""
        ft = _finding(targets, key, value)
        if not ft:
            return
        fmt_args = {"value": value}
        if extra_fmt:
            fmt_args.update(extra_fmt)
        detail = ft["detail"].format(**fmt_args)
        add(sev, ft["title"], detail, ft["cue"], ft["drill"], key.value, frame)

    is_side = view in ("side-left", "side-right")

    if is_side:
        # --- cadence ---
        cad = _val(values, MK.CADENCE)
        t_cad = targets.get(MK.CADENCE)
        if t_cad and cad == cad:
            st = t_cad.status(cad)
            lo, hi = t_cad.good
            if st != "good" and (cad < lo or st == "bad"):
                sev = "high" if st == "bad" else "med"
                _add_from_def(sev, MK.CADENCE, cad)

        # --- overstride ---
        over = _val(values, MK.OVERSTRIDE)
        t_over = targets.get(MK.OVERSTRIDE)
        if t_over and t_over.status(over) != "good" and over == over:
            st = t_over.status(over)
            sev = "high" if st == "bad" else "med"
            _add_from_def(sev, MK.OVERSTRIDE, over, frame=foi.get("l_strike"))

        # --- trunk lean ---
        trunk = _val(values, MK.TRUNK_LEAN)
        t_trunk = targets.get(MK.TRUNK_LEAN)
        if t_trunk and trunk == trunk:
            st = t_trunk.status(trunk)
            lo, hi = t_trunk.good
            if st != "good" and (trunk < lo or st == "bad"):
                sev = "high" if st == "bad" else "med"
                _add_from_def(sev, MK.TRUNK_LEAN, trunk)

        # --- knee flexion midstance ---
        kf = _val(values, MK.KNEE_FLEXION_MIDSTANCE)
        t_kf = targets.get(MK.KNEE_FLEXION_MIDSTANCE)
        if t_kf and t_kf.status(kf) == "bad" and kf == kf:
            _add_from_def("med", MK.KNEE_FLEXION_MIDSTANCE, kf, frame=foi.get("l_midstance"))

        # --- contact time ---
        ct = _val(values, MK.CONTACT_TIME)
        t_ct = targets.get(MK.CONTACT_TIME)
        if t_ct and t_ct.status(ct) != "good" and ct == ct:
            _add_from_def("low", MK.CONTACT_TIME, ct)

        # --- hip extension ---
        he = _val(values, MK.HIP_EXTENSION)
        t_he = targets.get(MK.HIP_EXTENSION)
        if t_he and t_he.status(he) != "good" and he == he:
            st = t_he.status(he)
            sev = "med" if st == "bad" else "low"
            _add_from_def(sev, MK.HIP_EXTENSION, he, frame=foi.get("l_toeoff"))

        # --- knee drive ---
        kd = _val(values, MK.KNEE_DRIVE)
        t_kd = targets.get(MK.KNEE_DRIVE)
        if t_kd and t_kd.status(kd) != "good" and kd == kd:
            _add_from_def("low", MK.KNEE_DRIVE, kd)

        # --- elbow angle ---
        ea = _val(values, MK.ELBOW_ANGLE)
        t_ea = targets.get(MK.ELBOW_ANGLE)
        if t_ea and ea == ea and t_ea.status(ea) != "good":
            _add_from_def("low", MK.ELBOW_ANGLE, ea)

        # --- duty factor ---
        dfv = _val(values, MK.DUTY_FACTOR)
        t_df = targets.get(MK.DUTY_FACTOR)
        if t_df and t_df.status(dfv) == "bad" and dfv == dfv:
            _add_from_def("low", MK.DUTY_FACTOR, dfv)

        # --- vertical oscillation ---
        vo = _val(values, MK.VERTICAL_OSCILLATION)
        t_vo = targets.get(MK.VERTICAL_OSCILLATION)
        if t_vo and t_vo.status(vo) == "bad" and vo == vo:
            _add_from_def("low", MK.VERTICAL_OSCILLATION, vo)

        # --- head bobbing (value-derived trigger, uses {ref} for vo) ---
        hd = _val(values, MK.HEAD_DROP)
        if hd == hd and vo == vo and hd > max(vo * 1.5, 5.0):
            _add_from_def("low", MK.HEAD_DROP, hd, extra_fmt={"ref": vo})

    else:
        # --- pelvic drop ---
        pd = _val(values, MK.PELVIC_DROP)
        t_pd = targets.get(MK.PELVIC_DROP)
        if t_pd and t_pd.status(pd) != "good" and pd == pd:
            st = t_pd.status(pd)
            sev = "high" if st == "bad" else "med"
            _add_from_def(sev, MK.PELVIC_DROP, pd, frame=foi.get("max_pelvic_drop"))

        # --- crossover gait (boolean) ---
        if values.get(MK.CROSSOVER):
            ft = METRIC_DEFS[MK.STEP_WIDTH].finding_text.get("low", {})
            if ft:
                add("med", ft["title"], ft["detail"].format(value=0),
                    ft["cue"], ft["drill"], MK.STEP_WIDTH.value)

        # --- lateral trunk sway ---
        sway = _val(values, MK.LATERAL_TRUNK_SWAY)
        t_sway = targets.get(MK.LATERAL_TRUNK_SWAY)
        if t_sway and sway == sway and t_sway.status(sway) != "good":
            _add_from_def("low", MK.LATERAL_TRUNK_SWAY, sway)

        # --- head lateral sway ---
        hls = _val(values, MK.HEAD_LATERAL_SWAY)
        t_hls = targets.get(MK.HEAD_LATERAL_SWAY)
        if t_hls and hls == hls and t_hls.status(hls) != "good":
            _add_from_def("low", MK.HEAD_LATERAL_SWAY, hls)

        # --- pronation (informational, low-confidence) ---
        pr = _val(values, MK.PRONATION)
        t_pr = targets.get(MK.PRONATION)
        if t_pr and t_pr.status(pr) != "good" and pr == pr:
            _add_from_def("low", MK.PRONATION, pr, frame=foi.get("max_pelvic_drop"))

        # --- arm crossover (boolean) ---
        if values.get(MK.ARM_CROSSOVER):
            _add_from_def("low", MK.ARM_CROSSOVER, 0)

    # --- composite patterns (§14): a composite outranks its component findings ---
    for finding, superseded in _composites(values, view, targets):
        items[:] = [i for i in items if i.get("metric") not in superseded]
        items.append(finding)

    # --- one-sided deficit (meta-asymmetry): outranks the individual asymmetry
    # findings it absorbs, same supersession pattern as the composites above ---
    meta_finding, meta_keys = _one_sided_deficit(asym)
    if meta_finding:
        items.append(meta_finding)

    # --- asymmetry findings ---
    for a in asym[:3]:
        if a["status"] == "good" or a["key"] in meta_keys:
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

    # R14.0 — surface at most 3 substantive findings (highest severity first);
    # the positive "good" note (if any) is kept alongside.
    non_good = [i for i in items if i["severity"] != "good"][:3]
    good = [i for i in items if i["severity"] == "good"]
    items = non_good + good

    score, grade = _score(values, per_side, asym, view, targets)
    return items, score, grade


def _score(values: Dict, per_side: Dict, asym: List[dict], view: str, targets: Dict = None) -> Tuple[float, str]:
    targets = targets or METRIC_DEFS
    view_str = "side" if view in ("side-left", "side-right") else "rear"
    # Derive scored keys from METRIC_DEFS (scored=True, correct view).
    # Fall back to explicit lists if targets is a personalized copy with MetricKey keys.
    scored_keys = [k for k, d in METRIC_DEFS.items() if d.scored and view_str in d.views]
    scores = []
    for k in scored_keys:
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
