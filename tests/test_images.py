"""Tests for OCR service."""

import asyncio
import json
import os
import unittest

import cv2

from foxhole_stockpiles.services.ocr import OCR


class TestOCR(unittest.TestCase):
    """Test OCR service."""

    def setUp(self):
        """Set up the test."""
        self.images_dir = os.path.join(os.path.dirname(__file__), "images")
        self.image_files = [f for f in os.listdir(self.images_dir) if f.endswith(".png")]

    def test_ocr_scan_image(self):
        """Test OCR scan image."""
        ocr = OCR()
        for image_file in self.image_files:
            print(f"Testing {image_file}...")
            image_path = os.path.join(self.images_dir, image_file)
            json_path = image_path.replace(".png", ".json")

            with open(json_path, "r") as f:
                try:
                    expected_output = json.load(f)
                except json.JSONDecodeError:
                    expected_output = {}

            image = cv2.imread(image_path)
            stockpile = asyncio.run(
                ocr.extract_stockpile_from_image(image=image, file_name=image_file)
            )
            result = stockpile.model_dump() if stockpile is not None else None

            # Do not compare timestamps
            if "timestamp" in result:
                del result["timestamp"]
            if "timestamp" in expected_output:
                del expected_output["timestamp"]

            self.assertEqual(result, expected_output)


if __name__ == "__main__":
    unittest.main()
