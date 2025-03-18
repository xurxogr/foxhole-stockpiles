"""Tests for OCR service."""

import asyncio
import json
import os

import cv2
import pytest

from foxhole_stockpiles.services.ocr import OCR


@pytest.fixture
def images_dir():
    """Fixture for images directory."""
    return os.path.join(os.path.dirname(__file__), "images")


@pytest.fixture
def image_files(images_dir):
    """Fixture for image files."""
    return [f for f in os.listdir(images_dir) if f.endswith(".png")]


def get_image_files_for_parameterize():
    """Get image files for parameterization."""
    test_dir = os.path.dirname(__file__)
    images_dir = os.path.join(test_dir, "images")
    return [f for f in os.listdir(images_dir) if f.endswith(".png")]


@pytest.mark.parametrize("image_file", get_image_files_for_parameterize())
def test_ocr_scan_image(images_dir, image_file):
    """Test OCR scan image."""
    ocr = OCR()
    print(f"Testing {image_file}...")
    image_path = os.path.join(images_dir, image_file)
    json_path = image_path.replace(".png", ".json")
    with open(file=json_path, mode="r", encoding="utf-8") as f:
        try:
            expected_output = json.load(f)
        except json.JSONDecodeError:
            expected_output = {}
    image = cv2.imread(image_path)
    stockpile = asyncio.run(ocr.extract_stockpile_from_image(image=image, file_name=image_file))
    result = stockpile.model_dump() if stockpile is not None else {}
    # Do not compare timestamps
    result.pop("timestamp", None)
    expected_output.pop("timestamp", None)
    # Sort the dictionaries by keys before comparing
    result = {k: result[k] for k in sorted(result)} if result else None
    expected_output = (
        {k: expected_output[k] for k in sorted(expected_output)} if expected_output else None
    )
    print(result)
    print(expected_output)
    assert result == expected_output
