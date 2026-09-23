"""Render tables and images strictly from an overstride debug record.

No function in this module imports the metric implementation or recomputes reach. The only
non-record input is the source-frame bitmap identified by each record. This keeps a label in
a PNG traceable to the same numeric field asserted by tests and written to CSV.
"""

from __future__ import annotations

import csv
import io
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from PIL import Image, ImageDraw, PngImagePlugin

from gaitlab.debug.overstride import frame_records, record_by_id

POSE_LEFT = "#4dabf7"
POSE_RIGHT = "#f59f00"
POSE_AXIAL = "#dce5ef"
REFERENCE = "#e64980"
DETECTOR = "#fa5252"
ADJUSTED = "#51cf66"
TEXT = "#f1f5f9"
PANEL = (8, 12, 18, 218)

BONES = (
    ("nose", "neck"), ("neck", "mid_hip"),
    ("mid_hip", "l_hip"), ("mid_hip", "r_hip"),
    ("neck", "l_shoulder"), ("l_shoulder", "l_elbow"), ("l_elbow", "l_wrist"),
    ("neck", "r_shoulder"), ("r_shoulder", "r_elbow"), ("r_elbow", "r_wrist"),
    ("l_hip", "l_knee"), ("l_knee", "l_ankle"), ("l_ankle", "l_heel"),
    ("l_heel", "l_big_toe"), ("l_ankle", "l_big_toe"),
    ("r_hip", "r_knee"), ("r_knee", "r_ankle"), ("r_ankle", "r_heel"),
    ("r_heel", "r_big_toe"), ("r_ankle", "r_big_toe"),
)


def _point_xy(point: Mapping[str, Any]) -> Optional[tuple[float, float]]:
    x, y = point.get("x"), point.get("y")
    if x is None or y is None or (point.get("confidence") is not None and point["confidence"] <= 0):
        return None
    return float(x), float(y)


def _fmt(value: Any, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _line(draw: ImageDraw.ImageDraw, a, b, *, fill, width=3) -> None:
    if a is not None and b is not None:
        draw.line((a[0], a[1], b[0], b[1]), fill=fill, width=width)


def _circle(draw: ImageDraw.ImageDraw, point, *, fill, radius=5, outline=None, width=1) -> None:
    if point is None:
        return
    x, y = point
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill,
                 outline=outline, width=width)


def _pose_color(name: str) -> str:
    if name.startswith("l_"):
        return POSE_LEFT
    if name.startswith("r_"):
        return POSE_RIGHT
    return POSE_AXIAL


def _tag(draw: ImageDraw.ImageDraw, point, text: str, *, fill: str) -> None:
    x, y = point
    box = draw.textbbox((x, y), text)
    draw.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill=PANEL)
    draw.text((x, y), text, fill=fill)


def render_plan(bundle: Mapping[str, Any], row: Mapping[str, Any], *,
                show_detector: bool = True, show_references: bool = True) -> dict:
    """Describe the exact record fields an annotated image will draw.

    Tests inspect this plan and PNG metadata. The raster renderer then consumes the plan,
    rather than reaching back into pose or metric code.
    """
    source = row["source_frame"]
    measurement = row["measurement_landmarks"]
    reach = row["reach"]["ankle"]
    inclination = row["inclination"]
    adjusted_here = any(
        item.get("side") == row["side"]
        and item.get("adjusted_frame_index") == source["decoded_index"]
        for item in bundle["events"].get("adjustments", [])
    )
    return {
        "record_id": row["record_id"],
        "source_frame_identifier": source["identifier"],
        "decoded_index": source["decoded_index"],
        "timestamp_s": source["timestamp_s"],
        "side": row["side"],
        "pose_landmarks": row["pose_landmarks"],
        "measurement_landmarks": measurement,
        "reach_pct_leg": reach["pct_leg"],
        "reach_px": reach["px"],
        "inclination_deg": inclination["degrees_from_vertical"],
        "detected_contact": bool(row["contact"]["detected"] and show_detector),
        "adjusted_contact": adjusted_here,
        "references": row["references"] if show_references else [],
        "validity": row["validity"],
        "diagnostic_name": row.get("diagnostic_name"),
    }


def render_annotated_frame(bundle: Mapping[str, Any], row: Mapping[str, Any],
                           background: Image.Image, *, show_detector: bool = True,
                           show_references: bool = True) -> tuple[Image.Image, dict]:
    """Overlay one record onto the exact decoded source image named by that record."""
    expected = (bundle["source"]["width"], bundle["source"]["height"])
    if background.size != expected:
        raise ValueError(
            f"decoded frame is {background.size}, pose coordinates expect {expected}; "
            "refusing a silently misaligned overlay"
        )
    plan = render_plan(bundle, row, show_detector=show_detector,
                       show_references=show_references)
    image = background.convert("RGB").copy()
    draw = ImageDraw.Draw(image, "RGBA")
    landmarks = plan["pose_landmarks"]

    for a, b in BONES:
        if a not in landmarks or b not in landmarks:
            continue
        pa, pb = _point_xy(landmarks[a]), _point_xy(landmarks[b])
        color = _pose_color(a if a.startswith(("l_", "r_")) else b)
        _line(draw, pa, pb, fill=color, width=4)
    for name, point in landmarks.items():
        _circle(draw, _point_xy(point), fill=_pose_color(name), radius=3)

    measured = plan["measurement_landmarks"]
    hip = _point_xy(measured["hip"])
    ankle = _point_xy(measured["ankle"])
    heel = _point_xy(measured["heel"])
    toe = _point_xy(measured["big_toe"])
    if hip:
        draw.line((hip[0], 0, hip[0], image.height), fill=(255, 255, 255, 180), width=2)
    if hip and ankle:
        _line(draw, hip, ankle, fill="#ffffff", width=3)
        _line(draw, (hip[0], ankle[1]), ankle, fill="#74c0fc", width=5)
        _tag(
            draw,
            ((hip[0] + ankle[0]) / 2, ankle[1] - 22),
            f"{_fmt(plan['reach_pct_leg'])}%leg",
            fill="#74c0fc",
        )
        _tag(
            draw,
            ((hip[0] + ankle[0]) / 2 + 8, (hip[1] + ankle[1]) / 2),
            f"{_fmt(plan['inclination_deg'])}°",
            fill="#ffffff",
        )
    _circle(draw, ankle, fill="#74c0fc", radius=8, outline="#ffffff", width=2)
    _circle(draw, heel, fill="#ffd43b", radius=7, outline="#ffffff", width=2)
    _circle(draw, toe, fill="#ff922b", radius=7, outline="#ffffff", width=2)

    for reference in plan["references"]:
        for _name, point in reference.get("landmarks", {}).items():
            if isinstance(point, list) and len(point) >= 2:
                p = (float(point[0]), float(point[1]))
            elif isinstance(point, dict):
                p = _point_xy(point)
            else:
                p = None
            _circle(draw, p, fill=None, radius=9, outline=REFERENCE, width=4)

    if plan["detected_contact"]:
        draw.polygon(((8, 8), (35, 8), (8, 35)), fill=DETECTOR)
    if plan["adjusted_contact"]:
        draw.polygon(((image.width - 8, 8), (image.width - 35, 8),
                      (image.width - 8, 35)), fill=ADJUSTED)

    lines = [
        f"{plan['record_id']}  {plan['side'].upper()}  frame {plan['decoded_index']}",
        f"t={plan['timestamp_s']:.6f}s  source={plan['source_frame_identifier']}",
        f"ankle reach={_fmt(plan['reach_pct_leg'])}%leg ({_fmt(plan['reach_px'])}px)",
        f"hip→ankle={_fmt(plan['inclination_deg'])}° from vertical",
        "conf hip/ankle/heel/toe=" + "/".join(
            _fmt(measured[name].get("confidence"))
            for name in ("hip", "ankle", "heel", "big_toe")
        ),
    ]
    if plan["diagnostic_name"]:
        lines.insert(0, plan["diagnostic_name"])
    layers = []
    if plan["detected_contact"]:
        layers.append("detected=red")
    if plan["adjusted_contact"]:
        layers.append("adjusted=green")
    if plan["references"]:
        layers.append("hand-reference=pink")
    if layers:
        lines.append("layers: " + ", ".join(layers))
    if not plan["validity"]["usable"]:
        lines.append("INVALID: " + "; ".join(plan["validity"]["reasons"]))
    bbox = draw.multiline_textbbox((0, 0), "\n".join(lines), spacing=4)
    panel_w = min(image.width, bbox[2] + 18)
    panel_h = bbox[3] + 16
    draw.rectangle((0, image.height - panel_h, panel_w, image.height), fill=PANEL)
    draw.multiline_text((8, image.height - panel_h + 7), "\n".join(lines),
                        fill=TEXT, spacing=4)
    return image, plan


def _png_info(plan: Mapping[str, Any], artifact: str) -> PngImagePlugin.PngInfo:
    info = PngImagePlugin.PngInfo()
    info.add_text("gaitlab.artifact", artifact)
    info.add_text("gaitlab.record_id", str(plan["record_id"]))
    info.add_text("gaitlab.source_frame", str(plan["source_frame_identifier"]))
    info.add_text("gaitlab.reach_pct_leg", json.dumps(plan["reach_pct_leg"]))
    return info


def save_annotated_frame(bundle: Mapping[str, Any], row: Mapping[str, Any],
                         background: Image.Image, destination: Path, *,
                         show_detector: bool = True,
                         show_references: bool = True) -> dict:
    image, plan = render_annotated_frame(
        bundle, row, background, show_detector=show_detector,
        show_references=show_references,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", pnginfo=_png_info(plan, "annotated-frame"),
               compress_level=9)
    return plan


def write_strike_table(bundle: Mapping[str, Any], destination: Path) -> None:
    rows_by_id = record_by_id(bundle)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "record_id", "side", "strike_frame", "timestamp_s", "hip_x", "ankle_x",
        "heel_x", "toe_x", "midfoot_x", "leg_px", "reach_px", "reach_pct_leg",
        "inclination_deg", "hip_confidence", "ankle_confidence", "validity_reasons",
    ]
    with destination.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for contact in bundle["events"]["detected_contacts"]:
            row = rows_by_id[contact["record_id"]]
            points = row["measurement_landmarks"]
            writer.writerow({
                "record_id": row["record_id"],
                "side": row["side"],
                "strike_frame": row["source_frame"]["decoded_index"],
                "timestamp_s": row["source_frame"]["timestamp_s"],
                "hip_x": points["hip"]["x"],
                "ankle_x": points["ankle"]["x"],
                "heel_x": points["heel"]["x"],
                "toe_x": points["big_toe"]["x"],
                "midfoot_x": points["foot_midpoint_proxy"]["x"],
                "leg_px": bundle["measurement"]["denominator"]["value_px"],
                "reach_px": row["reach"]["ankle"]["px"],
                "reach_pct_leg": row["reach"]["ankle"]["pct_leg"],
                "inclination_deg": row["inclination"]["degrees_from_vertical"],
                "hip_confidence": points["hip"]["confidence"],
                "ankle_confidence": points["ankle"]["confidence"],
                "validity_reasons": "; ".join(row["validity"]["reasons"]),
            })


def trace_rows(bundle: Mapping[str, Any], center: Mapping[str, Any], radius: int = 10) -> list[dict]:
    side = center["side"]
    index = center["source_frame"]["decoded_index"]
    return [
        row for row in frame_records(bundle, side=side)
        if abs(row["source_frame"]["decoded_index"] - index) <= radius
    ]


def save_reach_trace(bundle: Mapping[str, Any], center: Mapping[str, Any], destination: Path,
                     *, radius: int = 10) -> None:
    """Render an inspectable ±radius reach plot using stored values only."""
    rows = trace_rows(bundle, center, radius)
    width, height = 900, 420
    margin = (70, 45, 35, 70)
    image = Image.new("RGB", (width, height), "#0b0f14")
    draw = ImageDraw.Draw(image)
    values = [row["reach"]["ankle"]["pct_leg"] for row in rows]
    finite = [value for value in values if value is not None]
    lo, hi = (min(finite), max(finite)) if finite else (-1.0, 1.0)
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    pad = max(1.0, (hi - lo) * 0.12)
    lo, hi = lo - pad, hi + pad
    plot_w = width - margin[0] - margin[2]
    plot_h = height - margin[1] - margin[3]

    def xy(i, value):
        x = margin[0] + (i / max(1, len(rows) - 1)) * plot_w
        y = margin[1] + (hi - value) / (hi - lo) * plot_h
        return x, y

    draw.rectangle((margin[0], margin[1], margin[0] + plot_w, margin[1] + plot_h),
                   outline="#64748b", width=1)
    points = [xy(i, value) for i, value in enumerate(values) if value is not None]
    if len(points) > 1:
        draw.line(points, fill="#74c0fc", width=4)
    center_index = center["source_frame"]["decoded_index"]
    for i, (row, value) in enumerate(zip(rows, values)):
        if value is None:
            continue
        point = xy(i, value)
        selected = row["source_frame"]["decoded_index"] == center_index
        _circle(draw, point, fill=DETECTOR if selected else "#74c0fc", radius=6 if selected else 3)
        draw.text((point[0] - 7, margin[1] + plot_h + 10),
                  str(row["source_frame"]["decoded_index"]), fill="#cbd5e1")
    title = (f"{center['record_id']}  {center['side'].upper()}  ±{radius} frames  "
             f"contact={center_index}  reach={_fmt(center['reach']['ankle']['pct_leg'])}%leg")
    draw.text((margin[0], 16), title, fill=TEXT)
    draw.text((8, margin[1] + plot_h // 2), "%leg", fill="#cbd5e1")
    destination.parent.mkdir(parents=True, exist_ok=True)
    plan = render_plan(bundle, center)
    image.save(destination, format="PNG", pnginfo=_png_info(plan, "reach-trace"),
               compress_level=9)


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "#111827")
    canvas.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return canvas


def save_grid(images: Iterable[tuple[Image.Image, Mapping[str, Any]]], destination: Path,
              *, columns: int, artifact: str) -> None:
    items = list(images)
    if not items:
        raise ValueError(f"cannot render empty {artifact}")
    cell = (320, 420)
    rows = math.ceil(len(items) / columns)
    grid = Image.new("RGB", (cell[0] * columns, cell[1] * rows), "#030712")
    for index, (image, _plan) in enumerate(items):
        grid.paste(_fit(image, cell), ((index % columns) * cell[0], (index // columns) * cell[1]))
    ids = [plan["record_id"] for _image, plan in items]
    info = PngImagePlugin.PngInfo()
    info.add_text("gaitlab.artifact", artifact)
    info.add_text("gaitlab.record_ids", json.dumps(ids, separators=(",", ":")))
    destination.parent.mkdir(parents=True, exist_ok=True)
    grid.save(destination, format="PNG", pnginfo=info, compress_level=9)


# ffmpeg's expression parser rejects a `select` chain longer than this, so a clip with
# many contacts is decoded in several passes rather than one oversized filter.
SELECT_TERMS_PER_PASS = 80


class SourceFrames:
    """Decode source frames by exact zero-based index, caching repeated requests."""

    def __init__(self, path: Path, expected_size: tuple[int, int]):
        self.path = path
        self.expected_size = expected_size
        self._cache: dict[int, Image.Image] = {}

    def __call__(self, index: int) -> Image.Image:
        if index not in self._cache:
            self._cache[index] = self._decode(index)
        return self._cache[index].copy()

    def preload(self, indices: Iterable[int]) -> None:
        """Decode many exact indices, in as few passes through a video as the filter allows."""
        missing = sorted(set(indices) - self._cache.keys())
        if not missing:
            return
        if self.path.suffix.lower() in {".gif", ".tif", ".tiff"}:
            for index in missing:
                self._cache[index] = self._decode(index)
            return
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg is required to decode video frames")
        for start in range(0, len(missing), SELECT_TERMS_PER_PASS):
            self._preload_batch(missing[start:start + SELECT_TERMS_PER_PASS])

    def _preload_batch(self, missing: list[int]) -> None:
        selection = "+".join(f"eq(n\\,{index})" for index in missing)
        with tempfile.TemporaryDirectory(prefix="gaitlab-frames-") as temp:
            pattern = str(Path(temp) / "%06d.png")
            command = [
                "ffmpeg", "-v", "error", "-i", str(self.path),
                "-vf", f"select={selection}", "-vsync", "0", pattern,
            ]
            subprocess.run(command, check=True, capture_output=True)
            decoded_paths = sorted(Path(temp).glob("*.png"))
            if len(decoded_paths) != len(missing):
                raise IndexError(
                    f"requested {len(missing)} decoded frames but video returned "
                    f"{len(decoded_paths)}"
                )
            for index, path in zip(missing, decoded_paths):
                with Image.open(path) as image:
                    decoded = image.convert("RGB")
                if decoded.size != self.expected_size:
                    raise ValueError(
                        f"decoded frame is {decoded.size}, pose record expects "
                        f"{self.expected_size}; check rotation/orientation before rendering"
                    )
                self._cache[index] = decoded

    def _decode(self, index: int) -> Image.Image:
        if self.path.suffix.lower() in {".gif", ".tif", ".tiff"}:
            with Image.open(self.path) as image:
                image.seek(index)
                decoded = image.convert("RGB")
        else:
            if not shutil.which("ffmpeg"):
                raise RuntimeError("ffmpeg is required to decode video frames")
            command = [
                "ffmpeg", "-v", "error", "-i", str(self.path),
                "-vf", f"select=eq(n\\,{index})", "-vsync", "0", "-frames:v", "1",
                "-f", "image2pipe", "-vcodec", "png", "-",
            ]
            completed = subprocess.run(command, check=True, capture_output=True)
            if not completed.stdout:
                raise IndexError(f"video has no decoded frame {index}")
            decoded = Image.open(io.BytesIO(completed.stdout)).convert("RGB")
        if decoded.size != self.expected_size:
            raise ValueError(
                f"decoded frame is {decoded.size}, pose record expects {self.expected_size}; "
                "check rotation/orientation before rendering"
            )
        return decoded


def find_row(bundle: Mapping[str, Any], side: str, frame_index: int) -> dict:
    for row in bundle["frames"]:
        if row["side"] == side and row["source_frame"]["decoded_index"] == frame_index:
            return row
    raise KeyError(f"no {side}-side debug record for frame {frame_index}")
