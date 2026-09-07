"""Descriptive observation assembly.

Single-metric coaching is disabled. Retained composites are explicitly
exploratory, confidence-gated same-stride co-occurrences.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
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
        if defn.interpretation == "descriptive":
            continue
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


def _composite_findings(observations: List[dict], view: str, targets: Dict,
                        confidences: Dict[str, str]) -> List[Tuple[dict, set]]:
    view_str = "side" if view in ("side-left", "side-right") else "rear"
    out: List[Tuple[dict, set]] = []
    rank = {"low": 0, "moderate": 1, "high": 2}
    for comp in registry.all_composites():
        if comp.view != view_str:
            continue
        component_keys = [condition.key.value for condition in comp.all_of]
        if any(rank.get(confidences.get(key, "low"), 0) < rank[comp.min_confidence]
               for key in component_keys):
            continue
        by_side: Dict[str, List[dict]] = {}
        for row in observations:
            if comp.fires(row, targets):
                by_side.setdefault(row.get("side", "unknown"), []).append(row)
        if not by_side:
            continue
        side, matches = max(by_side.items(), key=lambda item: len(item[1]))
        if len(matches) >= comp.min_observations:
            out.append((comp.finding(matches[0], side, len(matches)), set(comp.supersedes)))
    return out


def build(values: Dict, per_side: Dict, asym: List[dict], view: str,
          foi: Dict, targets: Dict = None, observations: Optional[List[dict]] = None,
          confidences: Optional[Dict[str, str]] = None) -> Tuple[List[dict], None, None]:
    targets = targets or METRIC_DEFS
    items = _single_metric_findings(values, view, targets, foi)

    # composites outrank (supersede) the single-metric findings of the metrics they name
    for finding, superseded in _composite_findings(
        observations or [], view, targets, confidences or {}
    ):
        items[:] = [i for i in items if i.get("metric") not in superseded]
        items.append(finding)

    # Do not turn asymmetry percentages into findings without a metric-specific MDC.
    for a in asym:
        if a.get("interpretation") != "exceeds_mdc":
            continue
        items.append(_make_finding(
            "low", f"Observed left/right difference: {a['label']}",
            f"The signed difference is {a['difference']:.1f} {a['unit']}, which exceeds the "
            f"registered minimum detectable change of {a['mdc']:.1f} {a['unit']}.",
            "Repeat the same protocol before treating this as a persistent change.", "", a["key"]))

    if not items:
        items.append(_make_finding(
            "good", "Descriptive analysis complete",
            "No validated clinical threshold was applied. Review the measurements, confidence, sample counts, and same-speed trends.",
            "Use repeated recordings under the same setup to distinguish persistent changes from measurement noise.",
            "", None))

    order = {"high": 0, "med": 1, "low": 2, "good": 3}
    items.sort(key=lambda i: order[i["severity"]])

    # surface at most 3 substantive findings (highest severity first); the
    # positive "good" note (if any) is kept alongside.
    non_good = [i for i in items if i["severity"] != "good"][:3]
    good = [i for i in items if i["severity"] == "good"]
    items = non_good + good

    return items, None, None
