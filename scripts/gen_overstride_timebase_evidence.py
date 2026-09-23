#!/usr/bin/env python3
"""Regenerate issue #81's timebase report and fixed-index pose/video overlays.

Requires ffprobe, ffmpeg, and Pillow. `--check` verifies committed artifacts.
The manifest anchors are independent of the contact detector.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageChops, ImageDraw, ImageStat, PngImagePlugin
from extractor.timestamps import probe_timestamps
from gaitlab.core.schema import PoseSequence
from scripts.overstride_render import BONES, SourceFrames

ASSETS = ROOT / "docs/validation/assets"
MANIFEST = ASSETS / "overstride-timebase-manifest.json"
REPORT = "overstride-timebase-report.json"
# 50 us covers four-decimal pose rounding; 1 us allows ffprobe timestamp rounding.
TOLERANCE_S = 0.000051


def identity(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path.relative_to(ROOT)), "sha256": digest.hexdigest()}


def probe(path: Path) -> tuple[dict, list[float]]:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration:stream_tags=rotate:stream_side_data=rotation:format=duration",
               "-of", "json", str(path)]
    data = json.loads(subprocess.run(command, check=True, capture_output=True,
                                     text=True).stdout)
    stream = data["streams"][0]
    rotation = next((entry["rotation"] for entry in stream.get("side_data_list", [])
                     if "rotation" in entry), int(stream.get("tags", {}).get("rotate", 0)))
    pts = probe_timestamps(str(path))
    if pts is None:
        raise ValueError(f"no ffprobe frame PTS for {path}")
    return {
        "coded_width": int(stream["width"]), "coded_height": int(stream["height"]),
        "rotation_degrees": int(rotation),
        "nominal_fps": float(Fraction(stream["r_frame_rate"])),
        "container_average_fps": float(Fraction(stream["avg_frame_rate"])),
        "declared_frame_count": int(stream["nb_frames"]),
        "container_duration_s": float(data["format"]["duration"]),
        "stream_duration_s": float(stream["duration"]),
    }, pts


def inspect_case(case: dict) -> tuple[dict, PoseSequence, Path, list[float]]:
    clip = case["id"]
    video = ROOT / "tests/data" / f"{clip}.mp4"
    pose = ROOT / "tests/data" / f"{clip}.pose.rtmpose.json"
    seq = PoseSequence.from_pose_dict(json.loads(pose.read_text())).validate()
    metadata, pts = probe(video)
    if seq.timestamps is None:
        raise ValueError(f"{clip}: no stored pose timestamps")
    deltas = [abs(a - b) for a, b in zip(seq.timestamps, pts)]
    max_delta = max(deltas, default=None)
    gaps = [b - a for a, b in zip(pts, pts[1:])]
    median_gap = statistics.median(gaps)
    span = pts[-1] - pts[0]
    display_size = ((metadata["coded_height"], metadata["coded_width"])
                    if metadata["rotation_degrees"] % 180 else
                    (metadata["coded_width"], metadata["coded_height"]))
    checks = {
        "pose_and_probed_frame_counts_equal": len(seq.frames) == len(pts),
        "declared_and_probed_frame_counts_equal": metadata["declared_frame_count"] == len(pts),
        "stored_timestamps_strictly_increasing": all(b > a for a, b in zip(seq.timestamps, seq.timestamps[1:])),
        "stored_timestamps_match_current_container_pts": len(seq.timestamps) == len(pts)
        and max_delta is not None and max_delta <= TOLERANCE_S,
        "duration_within_one_median_frame": abs(span + median_gap - metadata["container_duration_s"])
        <= median_gap + TOLERANCE_S,
        "pose_and_display_dimensions_equal": (seq.width, seq.height) == display_size,
    }
    if not all(checks.values()):
        raise ValueError(f"{clip}: failed {', '.join(k for k, v in checks.items() if not v)}")
    anchor = case["anchor_frame"]
    if anchor is not None and not 0 <= anchor < len(pts):
        raise ValueError(f"{clip}: anchor out of range")
    radius = case.get("context_radius", 0)
    if not isinstance(radius, int) or radius < 0 or (anchor is None and radius):
        raise ValueError(f"{clip}: invalid context radius")
    after = case.get("context_after", radius)
    if not isinstance(after, int) or after < 0 or (anchor is None and after):
        raise ValueError(f"{clip}: invalid context after")
    context_indices = (list(range(max(0, anchor - radius),
                                  min(len(pts), anchor + after + 1)))
                       if anchor is not None and (radius or after) else [])
    report = {
        "id": clip, "video": identity(video), "pose_input": identity(pose),
        "pose_source": seq.source, "pose_view": seq.view,
        "stored_timestamp_source": seq.timestamp_source or "unrecorded (legacy fixture)",
        "timestamp_verification": "all stored timestamps compared to current video ffprobe PTS; historical extractor provider unproven",
        "probe_method": "ffprobe best_effort_timestamp_time in presentation order",
        "pose_frame_count": len(seq.frames), "probed_frame_count": len(pts),
        "pose_fps_metadata": seq.fps, "effective_fps_from_pts_span": (len(pts) - 1) / span,
        "first_pose_timestamp_s": seq.timestamps[0], "last_pose_timestamp_s": seq.timestamps[-1],
        "first_container_pts_s": pts[0], "last_container_pts_s": pts[-1],
        "pts_span_s": span, "median_frame_interval_s": median_gap,
        "max_pose_pts_delta_s": max_delta,
        "duration_estimate_minus_container_s": span + median_gap - metadata["container_duration_s"],
        "large_pts_gap_frame_indices": [i + 1 for i, gap in enumerate(gaps)
                                        if gap > 1.5 * median_gap],
        "pose_frame_count_note": seq.frame_count_note,
        "pose_display_width": seq.width, "pose_display_height": seq.height,
        "anchor_frame": anchor,
        "anchor_selection": ("fixed visual alignment sample; no contact label"
                             if anchor is not None else None),
        "anchor_pose_timestamp_s": seq.timestamps[anchor] if anchor is not None else None,
        "anchor_container_pts_s": pts[anchor] if anchor is not None else None,
        "context_frame_indices": context_indices,
        **metadata, "checks": checks,
    }
    return report, seq, video, pts


def footer_lines(case: dict, seq: PoseSequence, report: dict) -> list[str]:
    index = case["anchor_frame"]
    return [f"{case['id']} | decoded frame {index} | pose t={seq.timestamps[index]:.4f}s",
            f"video PTS={report['anchor_container_pts_s']:.6f}s | {len(seq.frames)} frames | fps={seq.fps:.3f}",
            "legacy timestamp provider unrecorded | contact/landmarks NOT validated"]


def render_anchor(case: dict, seq: PoseSequence, video: Path, report: dict,
                  destination: Path | None, *, decoded: Image.Image | None = None,
                  banner: bool = True) -> Image.Image:
    index = case["anchor_frame"]
    image = decoded.copy() if decoded is not None else SourceFrames(video, (seq.width, seq.height))(index)
    draw = ImageDraw.Draw(image, "RGBA")
    points = {name: seq.frames[index][i] for i, name in enumerate(seq.keypoint_names)}
    for left, right in BONES:
        if left in points and right in points and points[left][2] > 0 and points[right][2] > 0:
            draw.line((*points[left][:2], *points[right][:2]), fill=(0, 230, 255, 230), width=3)
    for x, y, confidence in points.values():
        if confidence > 0 and math.isfinite(x) and math.isfinite(y):
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 220, 0, 235))
    if banner:
        footer = footer_lines(case, seq, report)
        top = 0  # keep the feet unobstructed for visual alignment review
        draw.rectangle((0, top, image.width, 80), fill=(0, 0, 0, 230))
        for row, line in enumerate(footer):
            draw.text((8, top + 6 + row * 22), line, fill="white")
    if destination is not None:
        info = PngImagePlugin.PngInfo()
        for key, value in {"artifact": "issue81-timebase-anchor", "case": case["id"],
                           "decoded_frame": index, "pose_timestamp_s": seq.timestamps[index],
                           "container_pts_s": report["anchor_container_pts_s"],
                           "video_sha256": report["video"]["sha256"],
                           "pose_sha256": report["pose_input"]["sha256"]}.items():
            info.add_text("gaitlab." + key, str(value))
        image.save(destination, pnginfo=info, compress_level=9)
    return image


def render_context(case: dict, seq: PoseSequence, video: Path, report: dict,
                   pts: list[float], destination: Path) -> None:
    """Show neighboring decoded frames at readable foot size for human review."""
    indices = report["context_frame_indices"]
    source = SourceFrames(video, (seq.width, seq.height))
    source.preload(indices)
    columns = 3
    tile_width, crop_height, label_height = 480, 390, 34
    rows = math.ceil(len(indices) / columns)
    sheet = Image.new("RGB", (columns * tile_width, rows * (crop_height + label_height)),
                      (24, 30, 38))
    draw = ImageDraw.Draw(sheet)
    for position, index in enumerate(indices):
        neighbor = {**case, "anchor_frame": index}
        neighbor_report = {**report, "anchor_container_pts_s": pts[index]}
        annotated = render_anchor(neighbor, seq, video, neighbor_report, None,
                                  decoded=source(index), banner=False)
        # Context tiles show both feet; the separate anchor retains full-body orientation.
        lower_body = annotated.crop((0, round(seq.height * 0.543), seq.width, seq.height))
        lower_body = lower_body.resize((tile_width, crop_height), Image.Resampling.LANCZOS)
        x = (position % columns) * tile_width
        y = (position // columns) * (crop_height + label_height)
        sheet.paste(lower_body, (x, y + label_height))
        selected = index == case["anchor_frame"]
        if selected:
            draw.rectangle((x, y, x + tile_width - 1, y + label_height + crop_height - 1),
                           outline="#ffd43b", width=4)
        label = f"frame {index}  |  pose {seq.timestamps[index]:.4f}s  |  video PTS {pts[index]:.6f}s"
        if selected:
            label += "  |  SAMPLE"
        draw.text((x + 8, y + 8), label, fill="#ffd43b" if selected else "white")
    info = PngImagePlugin.PngInfo()
    for key, value in {"artifact": "issue81-timebase-context", "case": case["id"],
                       "frame_indices": json.dumps(indices), "selected_frame": case["anchor_frame"],
                       "video_sha256": report["video"]["sha256"],
                       "pose_sha256": report["pose_input"]["sha256"]}.items():
        info.add_text("gaitlab." + key, str(value))
    sheet.save(destination, pnginfo=info, compress_level=9)


def generate(destination: Path) -> list[str]:
    manifest = json.loads(MANIFEST.read_text())
    reports = []
    artifacts = [REPORT]
    for case in manifest["clips"]:
        report, seq, video, pts = inspect_case(case)
        reports.append(report)
        if case["anchor_frame"] is not None:
            name = f"overstride-timebase-{case['id']}-frame-{case['anchor_frame']}.png"
            render_anchor(case, seq, video, report, destination / name)
            artifacts.append(name)
        if report["context_frame_indices"]:
            name = f"overstride-timebase-{case['id']}-context.png"
            render_context(case, seq, video, report, pts, destination / name)
            artifacts.append(name)
    document = {
        "schema": "gaitlab.timebase-evidence/v1", "issue": 81,
        "manifest": identity(MANIFEST), "timestamp_tolerance_s": TOLERANCE_S,
        "duration_tolerance": "one median frame interval plus timestamp rounding allowance",
        "does_not_validate": ["historical video-to-pose extraction provenance",
                              "anatomical landmark correctness", "initial contact timing",
                              "leg-length denominator", "overstride value or clinical threshold"],
        "clips": reports,
    }
    (destination / REPORT).write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return artifacts


def stale_artifacts(*, portable_images: bool = False) -> list[str]:
    """Exact local check, or bounded visual check across CI decoder/font versions."""
    with tempfile.TemporaryDirectory() as temp:
        fresh = Path(temp)
        stale = []
        for name in generate(fresh):
            committed = ASSETS / name
            if not committed.is_file():
                stale.append(name)
            elif name.endswith(".json"):
                if committed.read_bytes() != (fresh / name).read_bytes():
                    stale.append(name)
            else:
                with Image.open(committed) as expected, Image.open(fresh / name) as actual:
                    if (expected.size != actual.size or expected.mode != actual.mode
                            or expected.info != actual.info):
                        stale.append(name)
                    elif portable_images:
                        difference = ImageChops.difference(expected, actual)
                        mean_channel_error = max(ImageStat.Stat(difference).mean)
                        strong_pixels = sum(difference.convert("L").histogram()[21:])
                        if (mean_channel_error > 1.0
                                or strong_pixels > expected.width * expected.height * 0.005):
                            stale.append(name)
                    elif expected.tobytes() != actual.tobytes():
                        stale.append(name)
        return stale


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv not in ([], ["--check"]):
        raise SystemExit("usage: gen_overstride_timebase_evidence.py [--check]")
    if argv == ["--check"]:
        stale = stale_artifacts()
        if stale:
            print("stale timebase evidence: " + ", ".join(stale), file=sys.stderr)
            return 1
        return 0
    print("\n".join(generate(ASSETS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
