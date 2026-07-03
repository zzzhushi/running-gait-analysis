"""Single source of truth machinery.

Every metric and composite is defined ONCE, in its own module under
gaitlab/metrics/definitions/ (metrics) or gaitlab/metrics/definitions/composites/
(composites). This module supplies the shared record types those modules build
(`MetricDef`, `Composite`, `Cond`, `Ctx`) and the registry they register into.

A metric module looks like:

    from ..spec import MetricDef, register
    from ...core import geometry as geo

    def _compute(ctx, side):
        ...  # the formula — the one piece that is genuinely per-metric code

    register(MetricDef(
        key=MetricKey.OVERSTRIDE, label="Overstride", unit="%leg",
        good=(None, 8), warn=(None, 15), views=("side",), scored=True,
        per_side=True, asym_direction="higher_worse", aggregate="worst_high",
        keypoints=("l_hip", "l_ankle", "r_hip", "r_ankle"), foi="l_strike",
        compute=_compute, finding_text={...}, exercises=[...],
    ))

Everything about a metric — its bands, coaching copy, exercises, formula, and any
custom trigger/confidence/personalization rule — lives in that one file. Nothing
about it is declared anywhere else; the generic engines (compute, feedback,
asymmetry, analyze, exercises) only ever read the registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .keys import MetricKey

GOOD, WARN, BAD = "good", "warn", "bad"

# Pose places a joint centre with ~+/-2-4 deg of angular error, so small angular
# readings sit in the noise floor and must be reported at lower confidence.
NOISE_FLOOR_DEG = 4.0


def _within(value: float, band: Tuple[Optional[float], Optional[float]]) -> bool:
    lo, hi = band
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


def direction_of(value: float, band: Tuple[Optional[float], Optional[float]]) -> str:
    """"low", "high", or "any" based on where value falls relative to a good band."""
    lo, hi = band
    if lo is not None and value < lo:
        return "low"
    if hi is not None and value > hi:
        return "high"
    return "any"


def default_trigger(defn: "MetricDef", value: float, values: Dict, targets: Dict) -> Optional[Tuple[str, str]]:
    """The generic trigger: fire (direction, "low") whenever status != good.

    This is the common case — about a third of metrics fire this way. Metrics
    with a different severity rule or a non-band condition (a custom threshold,
    a boolean flag, a value derived from another metric) register their own
    `trigger_fn` instead; see that metric's module for why.
    """
    if value != value:  # NaN
        return None
    t = targets.get(defn.key, defn)
    if t.status(value) == GOOD:
        return None
    return direction_of(value, t.good), "low"


@dataclass
class MetricDef:
    """The single record for one metric: declarative facts + behavior hooks.

    Bands/text/exercises are the declarative part — always set. `compute`,
    `trigger_fn`, `value_confidence_fn`, and `personalize_fn` are optional
    behavior hooks: omit them to get the generic default; only a handful of
    metrics need a custom one (see their module's docstring for why).
    """

    key: MetricKey
    label: str
    unit: str
    good: Tuple[Optional[float], Optional[float]]
    warn: Tuple[Optional[float], Optional[float]]
    note: str = ""
    higher_is_better: Optional[bool] = None
    confidence: str = "high"        # "high" | "moderate" | "low"
    views: Tuple[str, ...] = ("side", "rear")  # where this metric is scored/carded
    # Where this metric's trigger() can raise a coaching finding. None = same as
    # `views`. Only cadence differs: it's scored/carded in both views, but only
    # ever raises a finding in the side view.
    trigger_views: Optional[Tuple[str, ...]] = None
    scored: bool = True             # False = informational only, excluded from score
    per_side: bool = False          # True = tracked in the left/right asymmetry table
    asym_direction: str = "neutral" # "higher_better" | "higher_worse" | "neutral"
    # Coaching text keyed by direction ("low", "high") or "any" (fires regardless
    # of direction — used by metrics that only ever flag one way).
    # Each value: {"title": str, "detail": str, "cue": str, "drill": str}.
    # {value} in detail is replaced with the measured value via .format().
    finding_text: Dict[str, Dict[str, str]] = field(default_factory=dict)
    exercises: List[Dict[str, str]] = field(default_factory=list)

    # --- how this metric is computed / displayed / triggered -------------
    compute: Optional[Callable] = None       # per_side_compute: (ctx, side)->float; else (ctx, None)->float
    per_side_compute: bool = False           # True: compute() is called once per side, then aggregated
    aggregate: str = "median"                # combiner for the two per-side raw values into one headline value
    is_boolean: bool = False                 # a flag metric (e.g. crossover): value is True/False, not scored
    keypoints: Tuple[str, ...] = ()          # contributing landmarks, for confidence propagation
    foi: Optional[str] = None                # frames_of_interest key this metric anchors on the overlay
    card_per_side_key: Optional[str] = None  # if set, the card also shows L/R using this per_side dict key
    # "always": shown whenever its view is active. "conditional": shown only once its
    # value is computed (calibration- or head-keypoint-gated). "hidden": never gets its
    # own card — it exists only as per-side data feeding asymmetry or another card.
    card_visibility: str = "always"
    # Force the card's status regardless of its good/warn band — for metrics with no
    # real band (both None) that would otherwise trivially compute "good".
    card_status: Optional[str] = None

    # --- optional overrides of the generic engine behavior ----------------
    # (defn, value, values, targets) -> (direction, severity) | None. Severity
    # varies too much per metric (flat "low", bad-only "med", bad/warn -> high/med,
    # ...) for one generic rule, so most metrics beyond the simplest register this.
    trigger_fn: Optional[Callable] = None
    value_confidence_fn: Optional[Callable] = None # (value) -> "low"|"moderate"|"high"
    personalize_fn: Optional[Callable] = None      # (defn, profile) -> MetricDef
    extra_fmt_fn: Optional[Callable] = None        # (values) -> dict of extra .format() args for finding_text

    # ------------------------------------------------------------------
    # Scoring (unchanged formula from the original targets.Target class)
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
        """0-100 score (100 = ideal mid-band, ~45 at warn edge, ~17 at deep BAD)."""
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

    def trigger(self, value: float, values: Dict, targets: Dict) -> Optional[Tuple[str, str]]:
        """(direction, severity) if this metric should raise a finding, else None."""
        fn = self.trigger_fn or default_trigger
        return fn(self, value, values, targets)

    def value_confidence(self, value: float) -> str:
        if value is None or value != value:
            return "low"
        if self.value_confidence_fn:
            return self.value_confidence_fn(value)
        return self.confidence

    def personalize(self, profile: Optional[dict]) -> "MetricDef":
        if not profile or not self.personalize_fn:
            return self
        return self.personalize_fn(self, profile)


@dataclass
class Cond:
    """One condition in a composite's `all_of` list.

    Compares a metric's already-computed value against a bound on that SAME
    metric's own band (`good_hi`, `good_lo`, `warn_hi`, `warn_lo`) so the
    composite can never drift from the metric's registered bands — or, for
    the rare metric with no band at all (e.g. foot_strike_angle), an explicit
    literal via `value=`.
    """

    key: MetricKey
    op: str                          # "<" | ">"
    band: Optional[str] = None       # "good_hi" | "good_lo" | "warn_hi" | "warn_lo"
    value: Optional[float] = None    # explicit literal, for metrics with no band

    def threshold(self, targets: Dict) -> Optional[float]:
        if self.value is not None:
            return self.value
        t = targets.get(self.key)
        if t is None:
            return None
        lo_g, hi_g = t.good
        lo_w, hi_w = t.warn
        return {"good_hi": hi_g, "good_lo": lo_g, "warn_hi": hi_w, "warn_lo": lo_w}[self.band]

    def holds(self, values: Dict, targets: Dict) -> bool:
        v = values.get(self.key)
        if v is None or v != v:
            return False
        threshold = self.threshold(targets)
        if threshold is None:
            return False
        return v < threshold if self.op == "<" else v > threshold


def cond(key: MetricKey, op: str, band: Optional[str] = None, value: Optional[float] = None) -> Cond:
    return Cond(key=key, op=op, band=band, value=value)


@dataclass
class Composite:
    """A conjunction of per-metric conditions that, together, tell a more useful
    coaching story than any single metric alone — and outranks (supersedes) the
    individual findings of the metrics it names once it fires.
    """

    id: str
    view: str                 # "side" | "rear"
    all_of: Tuple[Cond, ...]
    severity: str              # "high" | "med"
    title: str
    detail: str                # .format()-ed against `values` (by metric key) at fire time
    cue: str
    drill: str
    supersedes: Tuple[str, ...]

    def fires(self, values: Dict, targets: Dict) -> bool:
        return all(c.holds(values, targets) for c in self.all_of)

    def finding(self, values: Dict) -> dict:
        fmt = {str(k): v for k, v in values.items() if isinstance(v, (int, float))}
        return {
            "severity": self.severity, "title": self.title,
            "detail": self.detail.format(**fmt), "cue": self.cue, "drill": self.drill,
            "metric": self.id, "frame": None,
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_METRICS: Dict[MetricKey, MetricDef] = {}
_COMPOSITES: List[Composite] = []


def register(defn: MetricDef) -> MetricDef:
    _METRICS[defn.key] = defn
    return defn


def register_composite(comp: Composite) -> Composite:
    _COMPOSITES.append(comp)
    return comp


def all_metrics() -> Dict[MetricKey, MetricDef]:
    return _METRICS


def all_composites() -> List[Composite]:
    return _COMPOSITES


def asym_metrics() -> List[MetricDef]:
    """Metrics tracked in the left/right asymmetry table, in registration order."""
    return [d for d in _METRICS.values() if d.per_side]


def cards_for_view(view: str) -> List[MetricDef]:
    """Cards always shown for this view — excludes conditional/hidden metrics
    (see MetricDef.card_visibility)."""
    view_str = "side" if view in ("side", "side-left", "side-right") else "rear"
    return [d for d in _METRICS.values() if view_str in d.views and d.card_visibility == "always"]


def conditional_cards_for_view(view: str) -> List[MetricDef]:
    view_str = "side" if view in ("side", "side-left", "side-right") else "rear"
    return [d for d in _METRICS.values() if view_str in d.views and d.card_visibility == "conditional"]


def scored_keys(view: str) -> List[MetricKey]:
    view_str = "side" if view in ("side", "side-left", "side-right") else "rear"
    return [k for k, d in _METRICS.items() if d.scored and view_str in d.views]


def keypoints_map() -> Dict[str, Tuple[str, ...]]:
    return {k.value: d.keypoints for k, d in _METRICS.items() if d.keypoints}
