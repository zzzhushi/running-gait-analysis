"""Published population reference equations used as context, never targets.

Equations are from Malisoux et al. (2023), 860 healthy recreational runners on
an instrumented treadmill. They predict a population mean under that protocol;
they do not define an optimum or an injury threshold.
"""

from __future__ import annotations

from typing import Dict, Optional

SOURCE = "Malisoux et al. 2023 (PMCID: PMC10588426)"
SOURCE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC10588426/"


def _number(profile: dict, key: str) -> Optional[float]:
    value = profile.get(key)
    return float(value) if isinstance(value, (int, float)) and value > 0 else None


def _sex(profile: dict) -> Optional[int]:
    value = (profile.get("sex") or "").lower()
    if value == "male":
        return 0
    if value == "female":
        return 1
    return None


def population_reference(metric: str, profile: dict) -> Optional[Dict]:
    age = _number(profile, "age_years")
    height_cm = _number(profile, "height_cm")
    mass = _number(profile, "body_mass_kg")
    speed = _number(profile, "speed_kmh")
    sex = _sex(profile)
    height = height_cm / 100.0 if height_cm else None

    value = None
    if metric == "cadence" and all(v is not None for v in (age, height, speed)):
        value = 203.056 + 0.193 * age - 44.242 * height + 3.067 * speed
    elif metric == "contact_time" and all(v is not None for v in (sex, mass, height, speed)):
        value = 259.01 + 12.8 * sex + 0.855 * mass + 77.122 * height - 17.314 * speed
    elif metric == "flight_time" and all(v is not None for v in (sex, age, mass, height, speed)):
        value = 280.618 - 13.232 * sex - 0.765 * age - 1.039 * mass + 139.558 * height + 3.307 * speed
    elif metric == "duty_factor" and all(v is not None for v in (sex, age, mass, speed)):
        value = 44.446 + 1.756 * sex + 0.039 * age + 0.121 * mass - 1.626 * speed
    elif metric == "vertical_oscillation_cm" and all(v is not None for v in (sex, age, mass, height)):
        value = (36.451 - 6.749 * sex - 0.275 * age - 0.284 * mass + 43.148 * height) / 10.0
    elif metric == "step_length" and all(v is not None for v in (age, height, speed)):
        value = -0.255 - 0.001 * age + 0.279 * height + 0.083 * speed
    if value is None:
        return None
    return {
        "value": round(value, 2),
        "label": "population estimate",
        "source": SOURCE,
        "url": SOURCE_URL,
        "caveat": "Reference value, not an optimal or injury-risk threshold.",
    }
