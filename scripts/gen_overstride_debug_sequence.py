#!/usr/bin/env python3
"""Regenerate the committed 9-frame overstride overlay diagnostic sequence.

    python scripts/gen_overstride_debug_sequence.py            # rewrite the committed assets
    python scripts/gen_overstride_debug_sequence.py --check    # exit 1 if any is stale

The endpoints come from the canonical authored reach fixture introduced before rendering work.
Intermediate frames interpolate the distal x coordinates only. This is an overlay/decode/time
fixture with neutral names, not a claim about acceptable or harmful running form.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw

from gaitlab.core.events import GaitEvents
from gaitlab.core.reach import Denominator
from gaitlab.core.schema import KEYPOINTS, PoseSequence
from gaitlab.debug.overstride import build_overstride_debug_record
from scripts.overstride_render import find_row, render_annotated_frame, save_grid

CANONICAL = ROOT / "tests" / "fixtures" / "overstride_stage3.json"
ASSETS = ROOT / "docs" / "validation" / "assets"
FRAME_COUNT = 9
ARTIFACTS = (
    "overstride-debug-sequence.record.json",
    "overstride-debug-sequence.source.gif",
    "overstride-debug-sequence.png",
    "overstride-debug-sequence.gif",
)


def _sequence():
    authored = json.loads(CANONICAL.read_text())
    start = authored["frames"][0]["points"]
    finish = authored["frames"][1]["points"]
    frames = []
    names = []
    for index in range(FRAME_COUNT):
        fraction = index / (FRAME_COUNT - 1)
        points = {}
        for name in start:
            points[name] = [
                start[name][axis] + (finish[name][axis] - start[name][axis]) * fraction
                for axis in range(3)
            ]
        frame = [(0.0, 0.0, 0.0)] * len(KEYPOINTS)
        for name, point in points.items():
            frame[KEYPOINTS.index(name)] = tuple(point)
        frames.append(frame)
        reach = round(20 * fraction, 1)
        names.append("zero_forward_reach" if index == 0 else f"positive_forward_reach_{reach:g}_pct")
    pose = authored["pose"]
    return PoseSequence(
        fps=float(pose["fps"]), width=int(pose["width"]), height=int(pose["height"]),
        view=pose["view"], frames=frames, source="authored:overstride_stage3-render-sequence",
        timestamps=[index / float(pose["fps"]) for index in range(FRAME_COUNT)],
        timestamp_source="authored (uniform f/fps)",
    ).validate(), names


def _background(index: int, size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size, (31 + index * 3, 38 + index * 2, 48 + index * 2))
    draw = ImageDraw.Draw(image)
    for x in range(0, size[0], 40):
        draw.line((x, 0, x, size[1]), fill=(55, 65, 78), width=1)
    for y in range(0, size[1], 40):
        draw.line((0, y, size[0], y), fill=(55, 65, 78), width=1)
    marker = 18
    draw.rectangle((0, 0, marker, marker), fill=(220, 38, 38))
    draw.rectangle((size[0] - marker - 1, 0, size[0] - 1, marker), fill=(34, 197, 94))
    draw.rectangle((0, size[1] - marker - 1, marker, size[1] - 1), fill=(234, 179, 8))
    draw.rectangle((size[0] - marker - 1, size[1] - marker - 1, size[0] - 1, size[1] - 1),
                   fill=(37, 99, 235))
    draw.text((14, 14), f"decoded frame {index}", fill="#f1f5f9")
    return image


def write_artifacts(destination: Path) -> None:
    """Write all four artifacts into `destination`, which must already exist."""
    sequence, names = _sequence()
    denominator = Denominator.injected(100.0, method="canonical authored 100 px")
    bundle = build_overstride_debug_record(
        sequence,
        GaitEvents(),
        source_id="overstride-debug-sequence.source.gif",
        denominator=denominator,
        facing=1,
    )
    for index, name in enumerate(names):
        find_row(bundle, "l", index)["diagnostic_name"] = name
    bundle["diagnostic_sequence"] = {
        "frame_record_ids": [find_row(bundle, "l", i)["record_id"] for i in range(FRAME_COUNT)],
        "names": names,
        "purpose": "decode/time/orientation/overlay validation only",
    }

    record_path = destination / "overstride-debug-sequence.record.json"
    record_path.write_text(json.dumps(bundle, indent=2, sort_keys=True, allow_nan=False) + "\n")

    backgrounds = [_background(index, (sequence.width, sequence.height)) for index in range(FRAME_COUNT)]
    backgrounds[0].save(
        destination / "overstride-debug-sequence.source.gif", save_all=True,
        append_images=backgrounds[1:], duration=round(1000 / sequence.fps), loop=0,
        optimize=False,
    )
    rendered = [
        render_annotated_frame(bundle, find_row(bundle, "l", index), backgrounds[index])
        for index in range(FRAME_COUNT)
    ]
    save_grid(
        rendered,
        destination / "overstride-debug-sequence.png",
        columns=3,
        artifact="diagnostic-sequence",
    )
    rendered_images = [image for image, _plan in rendered]
    rendered_images[0].save(
        destination / "overstride-debug-sequence.gif", save_all=True,
        append_images=rendered_images[1:], duration=500, loop=0, optimize=False,
    )


def stale_artifacts() -> list[str]:
    """Names of committed artifacts the current code no longer reproduces.

    PNG compression is allowed to differ across host zlib builds. Compare its decoded
    pixels and text metadata instead; those are the evidence a reviewer sees and the record
    identifiers that make it traceable. JSON and GIF remain byte-for-byte comparisons.
    """
    def matches(committed: Path, generated: Path) -> bool:
        if not committed.is_file():
            return False
        if committed.suffix != ".png":
            return committed.read_bytes() == generated.read_bytes()
        with Image.open(committed) as expected, Image.open(generated) as actual:
            return (
                expected.mode == actual.mode
                and expected.size == actual.size
                and expected.info == actual.info
                and expected.tobytes() == actual.tobytes()
            )

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        write_artifacts(fresh)
        return [
            name for name in ARTIFACTS
            if not matches(ASSETS / name, fresh / name)
        ]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        stale = stale_artifacts()
        if stale:
            print("stale, rerun scripts/gen_overstride_debug_sequence.py: "
                  + ", ".join(stale), file=sys.stderr)
            return 1
        return 0

    ASSETS.mkdir(parents=True, exist_ok=True)
    write_artifacts(ASSETS)
    print(ASSETS / "overstride-debug-sequence.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
