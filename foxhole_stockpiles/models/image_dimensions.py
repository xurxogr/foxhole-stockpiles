"""This module contains the ImageDimensions dataclass."""

from dataclasses import dataclass


@dataclass
class ImageDimensions:
    """Dataclass for storing image dimensions."""

    width: int
    height: int
    item_width: int
    item_height: int
    item_spacing_width: int
    item_spacing_height: int
