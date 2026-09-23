#!/usr/bin/env python3
"""Put independently saved pose estimates beside the same decoded video frame.

This is review tooling, not a landmark-accuracy test. Refuse a pose sequence whose
frame grid cannot be paired one-to-one with the source video.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

from gaitlab.core.schema import PoseSequence
from scripts.gen_overstride_timebase_evidence import TOLERANCE_S, probe
from scripts.overstride_render import SourceFrames

LANDMARKS = ("hip", "knee", "ankle", "heel", "big_toe")
COLORS = {"l": "#4dabf7", "r": "#f59f00"}
PANEL_WIDTH = 600
HEADER_HEIGHT = 64
FONT = ImageFont.load_default(size=17)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_alignment(seq: PoseSequence, pts: list[float], size: tuple[int, int],
                    *, name: str) -> None:
    """An index is reviewable only when it names the same decoded instant and pixels."""
    if seq.view not in ("side-left", "side-right"):
        raise ValueError(f"{name}: {seq.view} is not a side view; overstride review is side-only")
    if (seq.width, seq.height) != size:
        raise ValueError(f"{name}: pose dimensions {(seq.width, seq.height)} != video {size}")
    if seq.timestamps is None or len(seq.frames) != len(pts):
        raise ValueError(f"{name}: pose needs one timestamped frame per video frame")
    mismatch = next((i for i, (a, b) in enumerate(zip(seq.timestamps, pts))
                     if abs(a - b) > TOLERANCE_S), None)
    if mismatch is not None:
        raise ValueError(
            f"{name}: frame {mismatch} pose timestamp {seq.timestamps[mismatch]:.6f}s "
            f"!= video PTS {pts[mismatch]:.6f}s; refusing a misleading overlay"
        )


def _pose_points(seq: PoseSequence, frame: int, side: str) -> dict[str, tuple[float, float]]:
    names = {name: i for i, name in enumerate(seq.keypoint_names)}
    points = {}
    for landmark in LANDMARKS:
        key = f"{side}_{landmark}"
        if key not in names:
            continue
        x, y, confidence = seq.frames[frame][names[key]][:3]
        if confidence > 0 and math.isfinite(x) and math.isfinite(y):
            points[landmark] = (x, y)
    return points


def overlay(source: Image.Image, seq: PoseSequence, frame: int) -> Image.Image:
    image = source.copy().convert("RGB")
    draw = ImageDraw.Draw(image)
    for side in ("l", "r"):
        points = _pose_points(seq, frame, side)
        color = COLORS[side]
        for a, b in (("hip", "knee"), ("knee", "ankle"), ("ankle", "heel"),
                     ("heel", "big_toe"), ("ankle", "big_toe")):
            if a in points and b in points:
                draw.line((*points[a], *points[b]), fill=color, width=4)
        for name, (x, y) in points.items():
            draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=color, outline="white", width=2)
            if name in ("hip", "ankle", "heel", "big_toe"):
                dx, dy = {"hip": (9, -24), "ankle": (9, -27),
                          "heel": (-88, -17), "big_toe": (9, -8)}[name]
                label = f"{side.upper()} {name}"
                bounds = draw.textbbox((x + dx, y + dy), label, font=FONT)
                draw.rectangle((bounds[0] - 3, bounds[1] - 2,
                                bounds[2] + 3, bounds[3] + 2), fill="black")
                draw.text((x + dx, y + dy), label, fill=color, font=FONT)
    return image


def _panel(image: Image.Image, title: str, pts: float, top: int) -> Image.Image:
    # The crop includes hip and both shoes while making foot points reviewable.
    crop = image.crop((0, top, image.width, image.height))
    height = round(crop.height * PANEL_WIDTH / crop.width)
    crop = crop.resize((PANEL_WIDTH, height), Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (PANEL_WIDTH, height + HEADER_HEIGHT), "#17202b")
    panel.paste(crop, (0, HEADER_HEIGHT))
    draw = ImageDraw.Draw(panel)
    draw.text((10, 7), title, fill="white", font=FONT)
    draw.text((10, 33), f"decoded video PTS {pts:.6f}s", fill="#cbd5e1", font=FONT)
    return panel


def render_frame(source: Image.Image, poses: dict[str, PoseSequence], frame: int,
                 pts: float, *, clip: str, video_hash: str,
                 pose_hashes: dict[str, str], destination: Path) -> None:
    top = round(source.height * 0.43)
    panels = [_panel(source, "SOURCE ONLY: reference labels go here", pts, top)]
    panels += [_panel(overlay(source, seq, frame), name, pts, top)
               for name, seq in poses.items()]
    sheet = Image.new("RGB", (PANEL_WIDTH * len(panels), panels[0].height), "#17202b")
    for column, panel in enumerate(panels):
        sheet.paste(panel, (column * PANEL_WIDTH, 0))
    info = PngImagePlugin.PngInfo()
    for key, value in {
        "artifact": "issue82-landmark-review",
        "clip": clip,
        "frame_index": str(frame),
        "video_pts_s": f"{pts:.6f}",
        "video_sha256": video_hash,
        "pose_sha256": json.dumps(pose_hashes, sort_keys=True),
        "does_not_validate": "anatomical landmarks; contact timing; denominator; overstride",
    }.items():
        info.add_text("gaitlab." + key, value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, pnginfo=info, compress_level=9)


def _source_video(video: Path, frames: list[int]):
    metadata, pts = probe(video)
    size = ((metadata["coded_height"], metadata["coded_width"])
            if metadata["rotation_degrees"] % 180 else
            (metadata["coded_width"], metadata["coded_height"]))
    if not frames or any(not 0 <= index < len(pts) for index in frames):
        raise ValueError("at least one in-range frame index is required")
    sources = SourceFrames(video, size)
    sources.preload(frames)
    return pts, size, sources


def build_source_only(video: Path, frames: list[int], output: Path) -> list[Path]:
    """Export exact, unaltered decoded pixels for model-hidden human annotation."""
    pts, _size, sources = _source_video(video, frames)
    video_hash = sha256(video)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in frames:
        path = output / f"{video.stem}-source-frame-{index}.png"
        info = PngImagePlugin.PngInfo()
        for key, value in {
            "artifact": "issue82-source-only",
            "clip": video.stem,
            "frame_index": str(index),
            "video_pts_s": f"{pts[index]:.6f}",
            "video_sha256": video_hash,
            "model_layers_visible": "false",
        }.items():
            info.add_text("gaitlab." + key, value)
        sources(index).save(path, pnginfo=info, compress_level=9)
        paths.append(path)
    return paths


def build_review(video: Path, pose_paths: dict[str, Path], frames: list[int],
                 output: Path) -> list[Path]:
    pts, size, sources = _source_video(video, frames)
    poses = {}
    for name, path in pose_paths.items():
        seq = PoseSequence.from_pose_dict(json.loads(path.read_text())).validate()
        check_alignment(seq, pts, size, name=name)
        poses[name] = seq
    if not poses:
        raise ValueError("at least one pose input is required")
    video_hash = sha256(video)
    pose_hashes = {name: sha256(path) for name, path in pose_paths.items()}
    paths = []
    for index in frames:
        path = output / f"{video.stem}-landmarks-frame-{index}.png"
        render_frame(sources(index), poses, index, pts[index], clip=video.stem,
                     video_hash=video_hash, pose_hashes=pose_hashes,
                     destination=path)
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--rtmpose", type=Path)
    parser.add_argument("--blazepose", type=Path)
    parser.add_argument("--browser", type=Path,
                        help="optional JSON exported from a real browser extraction")
    parser.add_argument("--frame", type=int, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-only", action="store_true",
                        help="export unaltered raw frames, with no pose inputs or layers")
    args = parser.parse_args()
    if args.source_only:
        if args.rtmpose or args.blazepose or args.browser:
            parser.error("--source-only may not receive any pose input")
        try:
            paths = build_source_only(args.video, args.frame, args.output)
        except (ValueError, FileNotFoundError) as exc:
            raise SystemExit(str(exc)) from exc
        for path in paths:
            print(path)
        return
    if not args.rtmpose or not args.blazepose:
        parser.error("comparison requires both --rtmpose and --blazepose")
    poses = {"RTMPose": args.rtmpose, "Python BlazePose": args.blazepose}
    if args.browser:
        poses["Browser MediaPipe"] = args.browser
    try:
        paths = build_review(args.video, poses, args.frame, args.output)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
