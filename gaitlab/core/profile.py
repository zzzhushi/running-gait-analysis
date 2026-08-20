"""The runner's profile, and the calibration derived from it.

A profile is the only user-supplied context the engine takes: sex and body
measurements that personalize metric bands, plus treadmill speed. It used to be a
bare dict threaded through six layers — `analyze()` rebuilt a subset of it by
re-listing keys, `ctx._calibration()` read those keys again, and two metric
modules read them a third time — so the field list existed in several places at
once and adding a field meant finding all of them.

`RunnerProfile` gives that shape one definition. `Calibration` names the two
derived quantities the engine actually consumes.

Deliberately decoupled from PoseSequence: `calibrate()` takes the two pixel
measurements it needs as plain numbers rather than a pose, so the unit-conversion
rules can be tested without constructing a skeleton.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

# The profile fields the engine understands. Single source of truth — `from_dict`
# and `to_dict` both derive from it, so adding a field means editing one line.
FIELDS = ("sex", "height_cm", "leg_length_cm", "speed_kmh")


@dataclass(frozen=True)
class Calibration:
    """Pixel-to-centimetre scale and treadmill speed in SI.

    Either may be None when the profile lacks the inputs to derive it; every
    metric that needs one checks first and returns None (see
    vertical_oscillation_cm, vertical_ratio, stride_length, step_length).
    """

    px_per_cm: Optional[float] = None
    speed_mps: Optional[float] = None


@dataclass(frozen=True)
class RunnerProfile:
    """Sex and body measurements supplied by the runner. All fields optional."""

    sex: Optional[str] = None
    height_cm: Optional[float] = None
    leg_length_cm: Optional[float] = None
    speed_kmh: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "RunnerProfile":
        """Build from the wire format, ignoring keys the engine doesn't know.

        Tolerant by design: profiles arrive from the browser, the CLI, and the
        HTTP API, and an unrecognized key should not fail an analysis.
        """
        if not data:
            return cls()
        return cls(**{f: data.get(f) for f in FIELDS})

    def to_dict(self) -> dict:
        """Wire format, omitting unset fields.

        Omission rather than null matters: the browser only sends the fields the
        runner filled in, and the report echoes that sparse shape back.
        """
        return {f: getattr(self, f) for f in FIELDS if getattr(self, f) is not None}

    def __bool__(self) -> bool:
        """False when nothing was supplied, so `if profile:` reads naturally."""
        return any(getattr(self, f) is not None for f in FIELDS)

    @property
    def speed_mps(self) -> Optional[float]:
        return float(self.speed_kmh) / 3.6 if self.speed_kmh else None

    def calibrate(self, leg_px: float, body_px_height: Optional[float]) -> Calibration:
        """Derive the pixel scale, preferring measured leg length over height.

        Leg length is the more reliable scale: it is measured directly against the
        same limb the pose model tracks, whereas height-derived scale depends on
        head and heel keypoints that are noisier and can be cut off by the frame.
        """
        px_per_cm = None
        if self.leg_length_cm and leg_px > 0:
            px_per_cm = leg_px / float(self.leg_length_cm)
        elif self.height_cm and body_px_height and body_px_height > 0:
            px_per_cm = body_px_height / float(self.height_cm)
        return Calibration(px_per_cm=px_per_cm, speed_mps=self.speed_mps)
