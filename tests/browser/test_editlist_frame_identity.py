"""Issue #99: prove WebCodecs frame indices independently of timestamp labels."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

from tests.browser.test_browser_extraction import CLIP, DATA

SAMPLED_INDICES = (0, 1, 1401, 1408, 1415)
GRID = 16

_DECODE_PIXEL_GRID = f"""
async (url) => {{
  const {{ demuxVideoTrack }} = await import('/web/js/pose.js');
  const track = await demuxVideoTrack(url);
  const targets = new Set({list(SAMPLED_INDICES)});
  const canvas = document.createElement('canvas');
  canvas.width = track.codedWidth;
  canvas.height = track.codedHeight;
  const ctx = canvas.getContext('2d', {{willReadFrequently: true}});
  const grids = {{}};
  let index = 0;
  const decoder = new VideoDecoder({{
    output: frame => {{
      if (targets.has(index)) {{
        ctx.drawImage(frame, 0, 0);
        const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
        const grid = [];
        for (let row = 0; row < {GRID}; row++) {{
          const y = Math.floor((row + 0.5) * canvas.height / {GRID});
          for (let col = 0; col < {GRID}; col++) {{
            const x = Math.floor((col + 0.5) * canvas.width / {GRID});
            const offset = (y * canvas.width + x) * 4;
            grid.push(pixels[offset], pixels[offset + 1], pixels[offset + 2]);
          }}
        }}
        grids[index] = grid;
      }}
      index++;
      frame.close();
    }},
    error: error => {{ throw error; }},
  }});
  decoder.configure({{
    codec: track.codec, codedWidth: track.codedWidth,
    codedHeight: track.codedHeight, description: track.description,
  }});
  for (const s of track.samples) decoder.decode(new EncodedVideoChunk({{
    type: s.is_sync ? 'key' : 'delta',
    timestamp: track.timeline.timestampUs(s),
    duration: Math.round(s.duration * 1e6 / track.timescale),
    data: s.data,
  }}));
  await decoder.flush();
  decoder.close();
  return {{ count: index, width: canvas.width, height: canvas.height, grids }};
}}
"""


def _ffmpeg_grids(tmp_path: Path, candidates: list[int], width: int, height: int):
    output = tmp_path / "frame-%02d.png"
    select = "+".join(f"eq(n\\,{index})" for index in candidates)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-noautorotate", "-i",
         str(DATA / f"{CLIP}.mp4"), "-vf", f"select={select}", "-vsync", "0",
         str(output)], check=True, timeout=120,
    )
    grids = {}
    for n, index in enumerate(candidates, start=1):
        with Image.open(tmp_path / f"frame-{n:02d}.png") as source:
            image = source.convert("RGB")
            assert image.size == (width, height)
            grids[index] = [channel
                            for row in range(GRID)
                            for col in range(GRID)
                            for channel in image.getpixel((
                                int((col + 0.5) * width / GRID),
                                int((row + 0.5) * height / GRID),
                            ))]
    return grids


def test_browser_decoded_images_match_same_index_ffmpeg_frames(page, site, tmp_path):
    browser = page.evaluate(_DECODE_PIXEL_GRID, f"{site}/tests/data/{CLIP}.mp4")
    assert browser["count"] == 1424
    candidates = sorted({neighbor for index in SAMPLED_INDICES
                         for neighbor in (index - 1, index, index + 1)
                         if 0 <= neighbor < browser["count"]})
    reference = _ffmpeg_grids(tmp_path, candidates, browser["width"], browser["height"])
    for index in SAMPLED_INDICES:
        observed = browser["grids"][str(index)]
        errors = {neighbor: sum(abs(a - b) for a, b in zip(observed, reference[neighbor]))
                  for neighbor in (index - 1, index, index + 1)
                  if neighbor in reference}
        assert min(errors, key=errors.get) == index, f"frame {index}: pixel errors {errors}"
