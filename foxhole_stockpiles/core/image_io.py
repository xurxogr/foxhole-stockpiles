"""Pillow-backed image I/O and conversions.

Replaces OpenCV across the runtime and tooling for the handful of basic
operations they need: loading/decoding/saving BGR ``uint8`` arrays, resizing,
and swapping between BGR and RGB channel order. The OCR/matching itself lives in
the external ``fs-ocr`` engine, so OpenCV is no longer a dependency.

Arrays are BGR ``uint8`` (the order ``fs-ocr`` expects and the format the old
``cv2.imread`` produced).
"""

import io
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

# Resampling filters chosen to approximate the OpenCV interpolation modes the
# code previously used.
_RESAMPLE = {
    "area": Image.Resampling.BOX,  # downscaling (cv2.INTER_AREA)
    "nearest": Image.Resampling.NEAREST,  # cv2.INTER_NEAREST
    "linear": Image.Resampling.BILINEAR,  # cv2.INTER_LINEAR (default)
}


def _to_bgr(img: Image.Image) -> NDArray[np.uint8]:
    """Convert a PIL image to a contiguous BGR uint8 array.

    Args:
        img (Image.Image): Source image (any mode).

    Returns:
        NDArray[np.uint8]: H x W x 3 BGR array.
    """
    rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    return np.ascontiguousarray(rgb[:, :, ::-1])


def read_bgr(path: str | Path) -> NDArray[np.uint8] | None:
    """Load an image file as a BGR uint8 array.

    Args:
        path (str | Path): Path to the image file.

    Returns:
        NDArray[np.uint8] | None: BGR image, or None if it cannot be read
            (mirrors ``cv2.imread`` returning None on failure).
    """
    try:
        with Image.open(path) as img:
            return _to_bgr(img)
    except (OSError, ValueError):
        return None


def decode_bgr(data: bytes) -> NDArray[np.uint8] | None:
    """Decode encoded image bytes (e.g. PNG) to a BGR uint8 array.

    Args:
        data (bytes): Encoded image bytes.

    Returns:
        NDArray[np.uint8] | None: BGR image, or None if it cannot be decoded.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            return _to_bgr(img)
    except (OSError, ValueError):
        return None


def write_bgr(path: str | Path, image: NDArray[np.uint8]) -> None:
    """Save a BGR or BGRA uint8 array to an image file.

    A 4-channel BGRA image is written as RGBA with its alpha preserved (matching
    ``cv2.imwrite`` of a 4-channel array); a 3-channel BGR image is written as
    RGB.

    Args:
        path (str | Path): Destination path (format inferred from extension).
        image (NDArray[np.uint8]): H x W x 3 (BGR) or H x W x 4 (BGRA) image.
    """
    if image.ndim == 3 and image.shape[2] == 4:
        # BGRA -> RGBA (swap R/B, keep alpha last).
        rgba = np.ascontiguousarray(image[:, :, [2, 1, 0, 3]])
        Image.fromarray(rgba, "RGBA").save(str(path))
        return
    rgb = np.ascontiguousarray(image[:, :, ::-1])
    Image.fromarray(rgb).save(str(path))


def resize_bgr(
    image: NDArray[np.uint8], width: int, height: int, mode: str = "linear"
) -> NDArray[np.uint8]:
    """Resize a BGR uint8 array to ``(width, height)``.

    Channel order is preserved (resampling is per-channel), so BGR in yields
    BGR out.

    Args:
        image (NDArray[np.uint8]): H x W x 3 BGR image.
        width (int): Target width.
        height (int): Target height.
        mode (str): One of ``"area"``, ``"nearest"``, ``"linear"``. Defaults to
            ``"linear"``.

    Returns:
        NDArray[np.uint8]: Resized BGR image.
    """
    pil = Image.fromarray(np.ascontiguousarray(image))
    resized = pil.resize((width, height), _RESAMPLE[mode])
    return np.asarray(resized, dtype=np.uint8)


def swap_rb(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Swap the red and blue channels (BGR<->RGB), returning a contiguous copy.

    Args:
        image (NDArray[np.uint8]): H x W x 3 image.

    Returns:
        NDArray[np.uint8]: Image with red/blue channels swapped.
    """
    return np.ascontiguousarray(image[:, :, ::-1])
