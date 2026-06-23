"""Tests for the Pillow-backed image I/O helpers.

These guard the OpenCV replacement: the helpers must produce BGR/BGRA arrays
byte-identical to the ``cv2`` calls they replaced, including preserving the
alpha channel of 4-channel template icons (a regression that silently corrupted
generated template databases).
"""

from pathlib import Path

import numpy as np
import pytest

from foxhole_stockpiles.core.image_io import (
    decode_bgr,
    read_bgr,
    resize_bgr,
    swap_rb,
    write_bgr,
)


@pytest.fixture
def bgr_image() -> np.ndarray:
    """Create a deterministic 3-channel BGR image.

    Returns:
        np.ndarray: A 16x20x3 uint8 BGR image.
    """
    rng = np.random.default_rng(7)
    return rng.integers(0, 256, (16, 20, 3), dtype=np.uint8)


@pytest.fixture
def bgra_image() -> np.ndarray:
    """Create a deterministic 4-channel BGRA image (a template icon).

    Returns:
        np.ndarray: A 16x20x4 uint8 BGRA image.
    """
    rng = np.random.default_rng(11)
    return rng.integers(0, 256, (16, 20, 4), dtype=np.uint8)


class TestReadWriteRoundTrip:
    """Round-trip behaviour of write_bgr/read_bgr."""

    def test_bgr_round_trip_is_exact(self, tmp_path: Path, bgr_image: np.ndarray) -> None:
        """A 3-channel BGR image survives a write/read round-trip unchanged.

        Args:
            tmp_path (Path): Temporary directory.
            bgr_image (np.ndarray): Source BGR image.
        """
        path = tmp_path / "bgr.png"
        write_bgr(path, bgr_image)

        result = read_bgr(path)
        assert result is not None
        assert np.array_equal(result, bgr_image)

    def test_bgra_round_trip_drops_alpha_keeps_bgr(
        self, tmp_path: Path, bgra_image: np.ndarray
    ) -> None:
        """A 4-channel BGRA write then read yields the raw BGR (alpha dropped).

        This mirrors ``cv2.imwrite`` (preserves the 4 channels on disk) followed
        by ``cv2.imread`` (drops alpha) and is the contract the template database
        builder relies on.

        Args:
            tmp_path (Path): Temporary directory.
            bgra_image (np.ndarray): Source BGRA image.
        """
        path = tmp_path / "bgra.png"
        write_bgr(path, bgra_image)

        result = read_bgr(path)
        assert result is not None
        assert result.shape == (16, 20, 3)
        assert np.array_equal(result, bgra_image[:, :, :3])

    def test_bgra_alpha_is_preserved_on_disk(self, tmp_path: Path, bgra_image: np.ndarray) -> None:
        """The alpha channel is preserved in the written file, not folded into color.

        Args:
            tmp_path (Path): Temporary directory.
            bgra_image (np.ndarray): Source BGRA image.
        """
        from PIL import Image

        path = tmp_path / "bgra.png"
        write_bgr(path, bgra_image)

        with Image.open(path) as img:
            assert img.mode == "RGBA"
            rgba = np.asarray(img)
        # Stored alpha equals source alpha; stored RGB equals source R,G,B.
        assert np.array_equal(rgba[:, :, 3], bgra_image[:, :, 3])
        assert np.array_equal(rgba[:, :, 0], bgra_image[:, :, 2])  # R <- source R


class TestDecode:
    """decode_bgr behaviour."""

    def test_decode_matches_read(self, tmp_path: Path, bgr_image: np.ndarray) -> None:
        """Decoding PNG bytes equals reading the same file.

        Args:
            tmp_path (Path): Temporary directory.
            bgr_image (np.ndarray): Source BGR image.
        """
        path = tmp_path / "x.png"
        write_bgr(path, bgr_image)

        decoded = decode_bgr(path.read_bytes())
        assert decoded is not None
        assert np.array_equal(decoded, bgr_image)

    def test_decode_invalid_returns_none(self) -> None:
        """Undecodable bytes yield None (parity with cv2.imdecode)."""
        assert decode_bgr(b"not an image") is None


class TestReadFailure:
    """read_bgr failure behaviour."""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """A missing path yields None (parity with cv2.imread).

        Args:
            tmp_path (Path): Temporary directory.
        """
        assert read_bgr(tmp_path / "nope.png") is None


class TestResizeAndSwap:
    """resize_bgr and swap_rb behaviour."""

    def test_resize_shape_and_dtype(self, bgr_image: np.ndarray) -> None:
        """Resizing yields the requested size and uint8 dtype.

        Args:
            bgr_image (np.ndarray): Source BGR image.
        """
        out = resize_bgr(bgr_image, 8, 6, mode="area")
        assert out.shape == (6, 8, 3)
        assert out.dtype == np.uint8

    def test_swap_rb_is_involution(self, bgr_image: np.ndarray) -> None:
        """Swapping red/blue twice returns the original.

        Args:
            bgr_image (np.ndarray): Source BGR image.
        """
        assert np.array_equal(swap_rb(swap_rb(bgr_image)), bgr_image)
