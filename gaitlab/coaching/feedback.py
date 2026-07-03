"""Rule-based coaching feedback — generic engine.

Every finding comes from the metric registry: a metric's own `trigger()`
decides whether it fires and at what severity, and its `finding_text` supplies
the copy. This module has no per-metric knowledge; to change what triggers a
finding or what it says, edit that metric's module under
gaitlab/metrics/definitions/ (or its composite under .../definitions/composites/).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..core.geometry import clamp
from ..metrics import asymmetry as asym_mod
from ..metrics import spec as registry
from ..metrics.defs import METRIC_DEFS


def _make_finding(severity: str, title: str, detail: str, cue: str, drill: str, metric, frame=None) -> dict:
    return {"severity": severity, "title": title, "detail": detail, "cue": cue,
            "drill": drill, "metric": metric, "frame": frame}


def _format_finding_text(defn, direction: str, value, values: Dict) -> dict:
    """Look up finding_text for `direction` (falling back to "any"), and format
    its {value} / metric-specific extra placeholders."""
    ft = defn.finding_text.get(direction) or defn.finding_text.get("any")
    if not ft:
        return None
    fmt_args = {"value": value}
    if defn.extra_fmt_fn:
        fmt_args.update(defn.extra_fmt_fn(values))
    return {
        "title": ft["title"], "detail": ft["detail"].format(**fmt_args),
        "cue": ft["cue"], "drill": ft["drill"],
    }


def _single_metric_findings(values: Dict, view: str, targets: Dict, foi: Dict) -> List[dict]:
    view_str = "side" if view in ("side-left", "side-right") else "rear"
    items: List[dict] = []
    for defn in registry.all_metrics().values():
        trigger_views = defn.trigger_views or defn.views
        if view_str not in trigger_views or not defn.finding_text:
            continue
        value = values.get(defn.key.value)
        if value is None:
            continue
        result = defn.trigger(value, values, targets)
        if not result:
            continue
        direction, severity = result
        text = _format_finding_text(defn, direction, value, values)
        if not text:
            continue
        frame = foi.get(defn.foi) if defn.foi else None
        items.append(_make_finding(severity, text["title"], text["detail"], text["cue"], text["drill"],
                                    defn.key.value, frame))
    return items


def _composite_findings(values: Dict, view: str, targets: Dict) -> List[Tuple[dict, set]]:
    view_str = "side" if view in ("side-left", "side-right") else "rear"
    out: List[Tuple[dict, set]] = []
    for comp in registry.all_composites():
        if comp.view != view_str:
            continue
        if comp.fires(values, targets):
            out.append((comp.finding(values), set(comp.supersedes)))
    return out


def build(values: Dict, per_side: Dict, asym: List[dict], view: str,
          foi: Dict, targets: Dict = None) -> Tuple[List[dict], float, str]:
    targets = targets or METRIC_DEFS
    items = _single_metric_findings(values, view, targets, foi)

    # composites outrank (supersede) the single-metric findings of the metrics they name
    for finding, superseded in _composite_findings(values, view, targets):
        items[:] = [i for i in items if i.get("metric") not in superseded]
        items.append(finding)

    # asymmetry findings
    for a in asym[:3]:
        if a["status"] == "good":
            continue
        sev = "high" if a["status"] == "bad" else "med"
        items.append(_make_finding(
            sev, f"Left/right imbalance: {a['label']}",
            f"{a['label']} differs {a['diff_pct']:.0f}% between sides "
            f"(L {a['left']:.0f} vs R {a['right']:.0f} {a['unit']}), with the {a['worse_side']} side standing out. "
            "Imbalances over ~10% are worth addressing before they cause one-sided overuse.",
            f"Give the {a['worse_side']} side a little extra attention in strength work.",
            "Single-leg strength on the weaker side; film again in ~4 weeks to recheck.",
            a["key"]))

    # positive note if nothing major
    if not any(i["severity"] in ("high", "med") for i in items):
        items.append(_make_finding(
            "good", "Solid mechanics",
            "No major flags in this clip — your cadence, alignment, and symmetry look within healthy ranges.",
            "Keep doing what you're doing; recheck periodically.",
            "Maintain your current routine and strength work.", None))

    order = {"high": 0, "med": 1, "low": 2, "good": 3}
    items.sort(key=lambda i: order[i["severity"]])

    # surface at most 3 substantive findings (highest severity first); the
    # positive "good" note (if any) is kept alongside.
    non_good = [i for i in items if i["severity"] != "good"][:3]
    good = [i for i in items if i["severity"] == "good"]
    items = non_good + good

    score, grade = _score(values, per_side, asym, view, targets)
    return items, score, grade


def _score(values: Dict, per_side: Dict, asym: List[dict], view: str, targets: Dict = None) -> Tuple[float, str]:
    targets = targets or METRIC_DEFS
    view_str = "side" if view in ("side-left", "side-right") else "rear"
    scored_keys = registry.scored_keys(view_str)
    scores = []
    for k in scored_keys:
        t = targets.get(k)
        v = values.get(k.value)
        if t and isinstance(v, (int, float)) and v == v:
            scores.append(t.score(v))
    base = sum(scores) / len(scores) if scores else 60.0
    penalty = clamp(asym_mod.overall_diff(asym) * 0.8, 0.0, 22.0)
    overall = clamp(base - penalty, 0.0, 100.0)
    grade = ("A" if overall >= 85 else "B" if overall >= 72 else
             "C" if overall >= 58 else "D" if overall >= 42 else "E")
    return round(overall, 1), grade
