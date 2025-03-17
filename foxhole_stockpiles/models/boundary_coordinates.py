"""This module contains the BoundaryCoordinates dataclass."""

from dataclasses import dataclass


@dataclass
class BoundaryCoordinates:
    """Dataclass for storing boundary coordinates."""

    min_x: int
    min_y: int
    max_x: int
    max_y: int
    min_quantity_x: int
    detected_item_height: int
    detected_item_width: int

    async def update_coordinates(
        self,
        coords: tuple[int, int, int, int],
        min_quantity_x: int,
        detected_item_height: int,
        detected_item_width: int,
    ) -> None:
        """Update the boundary coordinates.

        Args:
            coords (tuple[int, int, int, int]): The boundary coordinates.
            min_quantity_x (int): The minimum x coordinate of quantities.
            detected_item_height (int): The detected item height.
            detected_item_width (int): The detected item width.
        """
        self.min_x = min(self.min_x, coords[0])
        self.min_y = min(self.min_y, coords[1])
        self.max_x = max(self.max_x, coords[2])
        self.max_y = max(self.max_y, coords[3])
        self.min_quantity_x = min(self.min_quantity_x, min_quantity_x)
        self.detected_item_height = max(self.detected_item_height, detected_item_height)
        self.detected_item_width = max(self.detected_item_width, detected_item_width)
