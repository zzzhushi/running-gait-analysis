"""Portable pixel comparison for regenerated validation images.

Metadata is checked by callers separately; this tolerance only covers small font and
video-decoder raster differences between hosts.
"""

from PIL import Image, ImageChops, ImageStat

MAX_MEAN_CHANNEL_ERROR = 1.0
STRONG_PIXEL_THRESHOLD = 20
MAX_STRONG_PIXEL_FRACTION = 0.005


def portable_pixels_match(expected: Image.Image, actual: Image.Image) -> bool:
    if expected.size != actual.size or expected.mode != actual.mode:
        return False
    difference = ImageChops.difference(expected, actual)
    mean_channel_error = max(ImageStat.Stat(difference).mean)
    strong_pixels = sum(difference.convert("L").histogram()[STRONG_PIXEL_THRESHOLD + 1:])
    return (mean_channel_error <= MAX_MEAN_CHANNEL_ERROR
            and strong_pixels <= expected.width * expected.height * MAX_STRONG_PIXEL_FRACTION)
