#!/usr/bin/env python3
"""Export a record-first overstride diagnostic bundle.

Examples:

  python scripts/export_overstride_debug.py \
    --pose tests/data/female_overstride.pose.rtmpose.json \
    --video tests/data/female_overstride.mp4 --output /tmp/overstride-debug

  # Blinded annotation bundle: source pixels only, tiling the whole clip, no model layer.
  python scripts/export_overstride_debug.py --sweep \
    --pose tests/data/female_overstride.pose.rtmpose.json \
    --video tests/data/female_overstride.mp4 --output /tmp/annotate

  # Diagnostic view centred anywhere, with the detector marker hidden.
  python scripts/export_overstride_debug.py --record /tmp/overstride-debug/debug-record.json \
    --video tests/data/female_overstride.mp4 --output /tmp/blinded \
    --strip-center l:240 --strip-radius 12 --hide-detector

The JSON record is written before any derived artifact. CSV and PNG outputs read only that
record; they never call the metric formula.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gaitlab.core.schema import PoseSequence
from gaitlab.debug.contacts import TIMEBASE_NOT_VALIDATED
from gaitlab.debug.overstride import build_overstride_debug_record, record_by_id
from scripts.overstride_render import (
    SourceFrames,
    find_row,
    render_annotated_frame,
    render_annotation_frame,
    save_annotated_frame,
    save_grid,
    save_reach_trace,
    sweep_centers,
    trace_rows,
    write_strike_table,
)


def _side_frame(value: str) -> tuple[str, int]:
    try:
        side, raw_frame = value.split(":", 1)
        frame = int(raw_frame)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected SIDE:FRAME, for example l:257") from exc
    if side not in ("l", "r") or frame < 0:
        raise argparse.ArgumentTypeError("side must be l or r and frame must be non-negative")
    return side, frame


def _load_json(path: Path):
    return json.loads(path.read_text())


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _media_identity(path: Path) -> dict[str, object]:
    """A portable identity for an input artifact, without recording its full local path."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def _require_record_video(bundle: dict, video: Path) -> None:
    """Refuse a re-render whose pixels are not the media named by the record."""
    expected = bundle.get("source", {}).get("video")
    if not isinstance(expected, dict) or not isinstance(expected.get("sha256"), str):
        raise SystemExit(
            "record has no source-video digest; cannot safely re-render it. "
            "Create a new debug record from its pose input first."
        )
    actual = _media_identity(video)
    if actual["sha256"] != expected["sha256"]:
        raise SystemExit(
            "video bytes do not match this debug record's source video; "
            "refusing a falsely traceable overlay"
        )


def _contact_sheet_rows(bundle, detected_rows):
    """Original, adjusted, and reference contacts, each retained as its own frame."""
    pairs = [(row["side"], row["source_frame"]["decoded_index"]) for row in detected_rows]
    for item in bundle["events"].get("adjustments", []):
        if isinstance(item.get("adjusted_frame_index"), int):
            pairs.append((item.get("side"), item["adjusted_frame_index"]))
    for item in bundle["events"].get("reference_contacts", []):
        frame = item.get("frame_index")
        interval = item.get("contact_interval_frames")
        if frame is None and isinstance(interval, list) and len(interval) == 2:
            frame = round((interval[0] + interval[1]) / 2)
        if isinstance(frame, int):
            pairs.append((item.get("side"), frame))
    unique = []
    seen = set()
    for side, frame in pairs:
        if side not in ("l", "r") or (side, frame) in seen:
            continue
        seen.add((side, frame))
        unique.append(find_row(bundle, side, frame))
    return unique


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pose", type=Path, help="pose JSON used to build a new debug record")
    source.add_argument("--record", type=Path, help="existing debug record to render without recomputing")
    parser.add_argument("--video", type=Path, required=True, help="source video or diagnostic GIF")
    parser.add_argument("--output", type=Path, required=True, help="output directory")
    parser.add_argument("--annotations", type=Path,
                        help="optional reference contacts/landmarks and contact adjustments JSON")
    parser.add_argument("--frame", action="append", default=[], type=_side_frame,
                        help="single annotated frame SIDE:FRAME; repeatable; defaults to all contacts")
    parser.add_argument("--strip-center", action="append", default=[], type=_side_frame,
                        help="arbitrary strip center SIDE:FRAME; repeatable; defaults to all contacts")
    parser.add_argument("--strip-radius", type=int, default=3)
    parser.add_argument("--trace-radius", type=int, default=10)
    parser.add_argument("--sweep", action="store_true",
                        help="write a blinded annotation bundle instead of a diagnostic one: "
                             "source pixels tiling the whole clip, no model or detector layer")
    parser.add_argument("--hide-detector", action="store_true",
                        help="hide detector markers for blinded annotation")
    parser.add_argument("--hide-references", action="store_true")
    parser.add_argument("--record-only", action="store_true")
    return parser


def _write_annotation_bundle(args, seq: PoseSequence) -> int:
    """Write a blinded annotation bundle: source pixels, neutral names, nothing else.

    Hiding the detector marker is not enough on its own. A directory whose filenames,
    contact sheet, traces or record are selected by the detector announces its predictions
    without drawing one, so this bundle contains none of them and the frames carry no
    pose, measurement or metric layer.
    """
    frames = SourceFrames(args.video, (seq.width, seq.height))
    centers = sweep_centers(seq.n, args.strip_radius)
    indices = sorted({
        index
        for center in centers
        for index in range(max(center - args.strip_radius, 0),
                           min(center + args.strip_radius, seq.n - 1) + 1)
    })
    frames.preload(indices)

    directory = args.output / "frames"
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for index in indices:
        path = directory / f"frame-{index:06d}.png"
        render_annotation_frame(
            frames(index), index, seq.time_at(index), clip=args.video.stem
        ).save(path, format="PNG")
        written.append(path.relative_to(args.output).as_posix())

    _write_json(args.output / "manifest.json", {
        "purpose": "blinded initial-contact annotation",
        "annotation_rule": "initial-contact-v1",
        "clip": args.video.stem,
        "source_video": _media_identity(args.video),
        "pose_input": _media_identity(args.pose),
        "coverage": "full-sweep",
        "frame_count": seq.n,
        "window_radius": args.strip_radius,
        "frames": written,
        "does_not_validate": [TIMEBASE_NOT_VALIDATED],
        "detector_markers_visible": False,
        "model_layers_visible": False,
    })
    print(args.output)
    return 0


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.strip_radius < 0 or args.trace_radius < 0:
        raise SystemExit("strip and trace radii must be non-negative")
    args.output.mkdir(parents=True, exist_ok=True)
    record_path = args.output / "debug-record.json"

    if args.sweep:
        if not args.pose:
            raise SystemExit("--sweep builds an annotation bundle from --pose, not a record")
        return _write_annotation_bundle(
            args, PoseSequence.from_pose_dict(_load_json(args.pose)).validate()
        )

    if args.pose:
        seq = PoseSequence.from_pose_dict(_load_json(args.pose)).validate()
        annotations = _load_json(args.annotations) if args.annotations else None
        bundle = build_overstride_debug_record(
            seq,
            source_id=args.video.name,
            annotations=annotations,
        )
        bundle["source"]["video"] = _media_identity(args.video)
        bundle["source"]["pose_input"] = _media_identity(args.pose)
        _write_json(record_path, bundle)  # authoritative artifact is always first
    else:
        bundle = _load_json(args.record)
        if not args.record_only:
            _require_record_video(bundle, args.video)
        _write_json(record_path, bundle)

    if args.record_only:
        print(record_path)
        return 0

    frames = SourceFrames(
        args.video,
        (int(bundle["source"]["width"]), int(bundle["source"]["height"])),
    )
    rows_by_id = record_by_id(bundle)
    contacts = [rows_by_id[item["record_id"]] for item in bundle["events"]["detected_contacts"]]
    sheet_rows = _contact_sheet_rows(bundle, contacts)
    requested_frames = (
        [find_row(bundle, side, frame) for side, frame in args.frame] if args.frame else contacts
    )
    strip_centers = (
        [find_row(bundle, side, frame) for side, frame in args.strip_center]
        if args.strip_center else contacts
    )
    show_detector = not args.hide_detector
    show_references = not args.hide_references

    needed_indices = {
        row["source_frame"]["decoded_index"]
        for row in requested_frames + sheet_rows
    }
    for center in strip_centers:
        needed_indices.update(
            row["source_frame"]["decoded_index"]
            for row in trace_rows(bundle, center, radius=args.strip_radius)
        )
    frames.preload(needed_indices)

    write_strike_table(bundle, args.output / "strikes.csv")
    manifest = {
        "record": "debug-record.json",
        "strike_table": "strikes.csv",
        "annotated_frames": [],
        "reach_traces": [],
        "strips": [],
        "contact_sheet": None,
        "detector_markers_visible": show_detector,
        "coverage": "detector-seeded",
    }

    rendered_contacts = []
    for row in contacts:
        trace_path = args.output / "traces" / f"{row['record_id']}.png"
        save_reach_trace(bundle, row, trace_path, radius=args.trace_radius)
        manifest["reach_traces"].append(str(trace_path.relative_to(args.output)))
    for row in sheet_rows:
        background = frames(row["source_frame"]["decoded_index"])
        rendered_contacts.append(render_annotated_frame(
            bundle, row, background, show_detector=show_detector,
            show_references=show_references,
        ))
    if rendered_contacts:
        sheet = args.output / "contact-sheet.png"
        save_grid(rendered_contacts, sheet, columns=4, artifact="contact-sheet")
        manifest["contact_sheet"] = str(sheet.relative_to(args.output))

    for row in requested_frames:
        path = args.output / "frames" / f"{row['record_id']}.png"
        save_annotated_frame(
            bundle, row, frames(row["source_frame"]["decoded_index"]), path,
            show_detector=show_detector, show_references=show_references,
        )
        manifest["annotated_frames"].append(str(path.relative_to(args.output)))

    for center in strip_centers:
        strip = []
        for row in trace_rows(bundle, center, radius=args.strip_radius):
            image, plan = render_annotated_frame(
                bundle, row, frames(row["source_frame"]["decoded_index"]),
                show_detector=show_detector, show_references=show_references,
            )
            strip.append((image, plan))
        path = args.output / "strips" / f"{center['record_id']}-r{args.strip_radius}.png"
        save_grid(strip, path, columns=len(strip), artifact="frame-strip")
        manifest["strips"].append(str(path.relative_to(args.output)))

    _write_json(args.output / "manifest.json", manifest)
    print(args.output / "manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
