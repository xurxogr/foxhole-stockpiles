"""OCR Service."""

import json
import logging
import os.path
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy
from keras.models import load_model
from pytesseract import pytesseract

from foxhole_stockpiles.core.config import AppSettings
from foxhole_stockpiles.enums.stockpile_type import StockpileType
from foxhole_stockpiles.models.boundary_coordinates import BoundaryCoordinates
from foxhole_stockpiles.models.image_dimensions import ImageDimensions
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.singletonmeta import SingletonMeta


class OCR(metaclass=SingletonMeta):
    """OCR Service class."""

    def __init__(self, settings: AppSettings) -> None:
        """Initialize the OCR service.

        Args:
            settings (AppSettings): Application settings
        """
        self._logger = logging.getLogger(__name__)
        self._logger.info("Initializing OCR service")
        self._settings = settings
        # Models and classes.
        self._icons_model, self._icons_classes = self._load_model(
            path=self._settings.models.icons_path
        )

    def _load_model(self, path: str) -> tuple:
        """Load a model and its classes.

        Args:
            path (str): Path of the model to load

        Returns:
            tuple: Model and classes loaded
        """
        model = None
        classes = None
        try:
            model = load_model(f"{path}.keras")
            with open(file=f"{path}.json", encoding="utf-8") as file:
                classes = json.load(file)
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as ex:
            raise RuntimeError(
                f"Couldn't load the models. Error: ({type(ex).__name__}: {str(ex)})"
            ) from None

        return model, classes

    async def _extract_item_from_image(self, image: cv2.typing.MatLike) -> str:
        """Extract the id of the identified item in an image.

        Args:
            image (cv2.typing.MatLike): Image to detect the type and name from

        Returns:
            str: Item detected. Empty string if not detected
        """
        # Resize the image to 32x32 to match the model
        resized_image = cv2.resize(image, (32, 32))
        expanded_imagen = numpy.expand_dims(resized_image, axis=0)

        prediction = self._icons_model.predict(expanded_imagen, verbose=0)

        top_2 = numpy.argsort(prediction[0])[-2:][::-1]
        top_score = prediction[0][top_2[0]]
        second_score = prediction[0][top_2[1]]
        top = self._icons_classes[top_2[0]]
        second = self._icons_classes[top_2[1]]

        # Check if the difference with the next item is below a threshold.
        threshold_score = self._settings.developer.icons_model_threshold_score
        score_diff = top_score - second_score
        if score_diff < threshold_score:
            self._logger.info(
                "Score diff < %s: %.3f. %s, %s", threshold_score, score_diff, top, second
            )

        return top

    async def _extract_text_from_image(self, image: cv2.typing.MatLike) -> str:
        """Extract text from an image.

        Args:
            image (cv2.typing.MatLike): Image to extract text from

        Returns:
            str: Extracted text. Empty string if not detected
        """
        if image is None:
            return ""

        # Upscale the image to improve the OCR detection.
        # Tesseract works better with larger images
        resized_image = cv2.resize(
            image,
            None,
            fx=self._settings.ocr.text_recognition_scale,
            fy=self._settings.ocr.text_recognition_scale,
            interpolation=cv2.INTER_CUBIC,
        )
        resized_image[resized_image < 170] = 0

        # Convert to black numbers with white background
        cropped_image = cv2.threshold(resized_image, 127, 255, cv2.THRESH_BINARY_INV)[1]

        config = "--psm 7"
        lang = "custom+eng+fra+deu+por+rus+chi_sim"
        pytesseract_text = pytesseract.image_to_string(cropped_image, lang=lang, config=config)
        return pytesseract_text.split("\n")[0]

    async def _extract_stockpile_type_from_image(self, image: cv2.typing.MatLike) -> StockpileType:
        """Extract the stockpile type from an image.

        Args:
            image (cv2.typing.MatLike): Image to extract the type from

        Returns:
            stockpile_type: Type detected. UNDEFINED if not detected
        """
        name = await self._extract_text_from_image(image=image)
        if not name:
            return StockpileType.UNDEFINED

        type_found = None
        translations = self._settings.stockpile_types.model_dump()
        for valid_names in translations.values():
            if name in valid_names:
                type_found = valid_names[0]
                break

        try:
            return StockpileType(str(type_found))
        except ValueError:
            self._logger.error("Stockpile type not found: '%s'", name)
            return StockpileType.UNDEFINED

    async def extract_stockpile_from_image(
        self, image: cv2.typing.MatLike, file_name: str = "Buffer"
    ) -> Stockpile | None:
        """Extract the stockpile from an image.

        Args:
            image: cv2.typing.MatLike = Image to read the stockpile from
            file_name (str): Name of the file

        Returns:
            Stockpile | None: Stockpile detected. None if not detected
        """
        if image is None:
            return None

        # Calculate image dimensions and scaling
        image_dimensions = await self._calculate_image_dimensions(image=image, file_name=file_name)

        # Process image to find item contours
        contours = await self._process_image_for_contours(image=image)

        # Extract items from contours
        items, quantities, boundary_coordinates = await self._extract_items_from_contours(
            image=image,
            contours=contours,
            dimensions=image_dimensions,
        )

        if not items:
            await self._save_failed_detection(file_name=file_name, image=image)
            return None

        # Calculate stockpile boundaries
        boundaries = await self._calculate_stockpile_boundaries(
            boundary_coordinates=boundary_coordinates,
            item_spacing_height=image_dimensions.item_spacing_height,
            item_spacing_width=image_dimensions.item_spacing_width,
        )

        # Extract stockpile metadata (type and name)
        type_, name = await self._extract_stockpile_metadata(image=image, boundaries=boundaries)

        # Create and process stockpile
        stockpile = Stockpile(
            name=name,
            type=type_,
            items=items,
            resolution=f"{image_dimensions.width}x{image_dimensions.height}",
        )

        # Save stockpile-related images if needed
        file_name_preffix = await self.get_save_image_prefix(
            file_name=file_name, image=image, stockpile=stockpile
        )

        if file_name_preffix:
            await self.save_image(
                file_name=file_name_preffix,
                image=image,
                name_image=image[
                    boundaries["name_y1"] : boundaries["name_y2"],
                    boundaries["name_x1"] : boundaries["name_x2"],
                ],
                type_image=image[
                    boundaries["type_y1"] : boundaries["type_y2"],
                    boundaries["type_x1"] : boundaries["type_x2"],
                ],
            )

        # Process quantities
        await self._process_stockpile_quantities(
            image=image, stockpile=stockpile, quantities=quantities
        )

        return stockpile

    async def _calculate_image_dimensions(
        self, image: cv2.typing.MatLike, file_name: str
    ) -> ImageDimensions:
        """Calculate the dimensions and scaling factors for the image.

        Args:
            image (cv2.typing.MatLike): The input image
            file_name (str): Name of the file for logging

        Returns:
            ImageDimensions: Image dimensions and scaling factors
        """
        width = image.shape[1]
        height = image.shape[0]
        image_ratio = height / self._settings.ocr.base_height

        item_width = int(self._settings.ocr.item_width * image_ratio)
        item_height = int(self._settings.ocr.item_height * image_ratio)
        item_spacing_width = int(image_ratio * self._settings.ocr.item_spacing_width)
        item_spacing_height = int(image_ratio * self._settings.ocr.item_spacing_height)

        self._logger.debug(
            "Parsing image %s. width: %d, height: %d, ratio: %.2f. "
            "Item size: %dx%d, spacing: %dx%d",
            file_name,
            width,
            height,
            image_ratio,
            item_width,
            item_height,
            item_spacing_width,
            item_spacing_height,
        )

        return ImageDimensions(
            width=width,
            height=height,
            item_width=item_width,
            item_height=item_height,
            item_spacing_width=item_spacing_width,
            item_spacing_height=item_spacing_height,
        )

    async def _process_image_for_contours(self, image: cv2.typing.MatLike) -> Any:
        """Process the image to extract contours.

        Args:
            image (cv2.typing.MatLike): The input image

        Returns:
            Any: List of contours found in the image
        """
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray_image, 50, 255, cv2.THRESH_BINARY)[1]
        return cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]

    async def _get_contour(
        self, cnt: Any, dimensions: ImageDimensions
    ) -> tuple[int, int, int, int] | None:
        """Check if the contour is valid based on the dimensions.

        Args:
            cnt (Any): Contour to check
            dimensions (ImageDimensions): Image dimensions and scaling factors

        Returns:
            tuple[int, int, int, int] | None: Coordinates of the contour (x, y, w, h) or None
                if invalid
        """
        approx = cv2.approxPolyDP(cnt, 0.01 * cv2.arcLength(cnt, True), True)
        if len(approx) != 4:
            return None

        x, y, w, h = cv2.boundingRect(cnt)
        pixel_error = 2
        if (
            abs(w - dimensions.item_width) > pixel_error
            or abs(h - dimensions.item_height) > pixel_error
        ):
            return None

        return (x, y, w, h)

    async def _get_icon_boundaries_from_quantity_boundaries(
        self, contour: tuple[int, int, int, int], item_spacing: int
    ) -> tuple:
        """Get the coordinates of the icon from the rectangle.

        Args:
            contour (tuple): Coordinates of the quantity rectangle (x, y, w, h)
            item_spacing (int): Spacing between the icon and the quantity

        Returns:
            tuple: Coordinates of the icon (x1, y1, x2, y2)
        """
        # [Icon][Spacing][Quantity]. Icon should be square and we know the height
        # x contains the quantity, substract the icon width (w == h) and the spacing
        # adapted to the image resolution
        icon_x2 = contour[0] - item_spacing
        icon_x1 = icon_x2 - contour[3]
        icon_y1 = contour[1]
        icon_y2 = contour[1] + contour[3]

        return icon_x1, icon_y1, icon_x2, icon_y2

    async def _extract_items_from_contours(
        self, image: cv2.typing.MatLike, contours: list, dimensions: ImageDimensions
    ) -> tuple:
        """Extract stockpile items from the detected contours.

        Args:
            image (cv2.typing.MatLike): The input image
            contours (list): List of contours
            dimensions (ImageDimensions): Image dimensions and scaling factors

        Returns:
            tuple: A tuple containing (items, quantities, boundary_coordinates) or None if
                no items were detected
        """
        items = []
        quantities = []

        # Initialize boundary variables
        boundary_coordinates = BoundaryCoordinates(
            min_x=10000,
            min_y=10000,
            max_x=0,
            max_y=0,
            min_quantity_x=10000,
            detected_item_height=0,
            detected_item_width=0,
        )

        item_number = 0

        for cnt in contours:
            contour = await self._get_contour(cnt=cnt, dimensions=dimensions)
            if not contour:
                continue

            quantities.append(contour)

            # Calculate icon boundaries from quantity boundaries
            # Icon is on the left side of the quantity separated by a spacing
            icon_boundaries = await self._get_icon_boundaries_from_quantity_boundaries(
                contour=contour,
                item_spacing=dimensions.item_spacing_width,
            )

            # Process the item icon
            items.append(
                await self._process_item_icon(
                    image=image,
                    icon_coords=icon_boundaries,
                    item_number=item_number,
                )
            )

            coords = (
                icon_boundaries[0],
                icon_boundaries[1],
                contour[0] + contour[2],
                contour[1] + contour[3],
            )
            # Update boundary coordinates
            await boundary_coordinates.update_coordinates(
                coords=coords,
                min_quantity_x=contour[0] + contour[2],
                detected_item_height=contour[3],
                detected_item_width=contour[2],
            )
            item_number += 1

        if not items:
            return None, None, None

        return (
            items,
            quantities,
            boundary_coordinates,
        )

    async def _process_item_icon(
        self, image: cv2.typing.MatLike, icon_coords: tuple[int, int, int, int], item_number: int
    ) -> StockpileItem:
        """Process and identify an item icon from the image.

        Args:
            image (cv2.typing.MatLike): The input image
            icon_coords (tuple): Coordinates (x1, y1, x2, y2) of the icon
            item_number (int): Current item counter

        Returns:
            StockpileItem: Item detected
        """
        icon_x1, icon_y1, icon_x2, icon_y2 = icon_coords
        icon_image = image[icon_y1:icon_y2, icon_x1:icon_x2]
        item_id = await self._extract_item_from_image(image=icon_image)

        # Handle crated items
        crated = False
        if "crated" in item_id:
            crated = True
            item_id = item_id.replace("_crated", "").replace("-crated", "")

        # Auto-collect training data: organize by resolution and CodeName
        if self._settings.developer.auto_collect_training_data:
            await self._save_training_data_icon(
                icon_image=icon_image,
                item_id=item_id,
                crated=crated,
                image=image,
                item_number=item_number
            )

        # Legacy icon saving (if enabled)
        if self._settings.developer.save_icons_image:
            # Create a directory with the name of the predicted item, if it doesn't exist
            directory = f"{self._settings.developer.icons_save_path}/{item_id}/"
            if not os.path.exists(directory):
                os.makedirs(directory)

            date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            width, height = image.shape[1], image.shape[0]
            cv2.imwrite(
                f"{directory}{item_number}_{item_id}_{width}x{height}_{date_str}.png",
                icon_image,
            )

        return StockpileItem(code=item_id, crated=crated)

    async def _save_training_data_icon(
        self,
        icon_image: cv2.typing.MatLike,
        item_id: str,
        crated: bool,
        image: cv2.typing.MatLike,
        item_number: int
    ) -> None:
        """Save icon for training data collection organized by resolution and CodeName.

        Args:
            icon_image (cv2.typing.MatLike): The extracted icon image
            item_id (str): The detected item CodeName
            crated (bool): Whether the item is crated
            image (cv2.typing.MatLike): The original screenshot
            item_number (int): Current item counter
        """
        try:
            # Get image resolution
            width, height = image.shape[1], image.shape[0]
            resolution = f"{width}x{height}"

            # Create folder name based on crated status
            folder_name = f"{item_id}-crated" if crated else item_id

            # Create directory structure: training_data/icons/resolution/CodeName/
            base_path = Path(self._settings.developer.training_data_path)
            icon_path = base_path / "icons" / resolution / folder_name
            icon_path.mkdir(parents=True, exist_ok=True)

            # Find the next available number for this CodeName in this resolution
            existing_files = list(icon_path.glob("*.png"))
            next_number = len(existing_files) + 1

            # Save the icon with simple numbering
            icon_filename = f"{next_number}.png"
            icon_filepath = icon_path / icon_filename

            cv2.imwrite(str(icon_filepath), icon_image)

            self._logger.debug(
                f"Saved training data icon: {folder_name} ({resolution}) -> {icon_filename}"
            )

        except Exception as e:
            self._logger.error(f"Error saving training data icon for {item_id}: {e}")

    async def _calculate_stockpile_boundaries(
        self,
        boundary_coordinates: BoundaryCoordinates,
        item_spacing_height: int,
        item_spacing_width: int,
    ) -> dict[str, int]:
        """Calculate the boundaries of the stockpile.

        Args:
            boundary_coordinates (BoundaryCoordinates): Boundary coordinates
            item_spacing_height (int): Vertical spacing between items
            item_spacing_width (int): Horizontal spacing between items

        Returns:
            dict[str, int: Dictionary with boundary coordinates
        """
        # Include the title in the cropped image
        min_x = boundary_coordinates.min_x
        min_y = boundary_coordinates.min_y
        max_x = boundary_coordinates.max_x

        min_y -= boundary_coordinates.detected_item_height + item_spacing_height
        min_x -= item_spacing_width

        max_x += item_spacing_width
        # Empty stockpiles have at least 2 items and the 3rd column is empty
        min_width = 3 * (boundary_coordinates.min_quantity_x - min_x) + min_x + item_spacing_height
        max_x = max(max_x, min_width)

        # Calculate title coordinates
        type_y1 = min_y + item_spacing_height
        type_y2 = min_y + boundary_coordinates.detected_item_height - item_spacing_height

        return {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": boundary_coordinates.max_y,
            "type_x1": min_x + item_spacing_width,
            "type_x2": min_x + 4 * boundary_coordinates.detected_item_width,
            "type_y1": type_y1,
            "type_y2": type_y2,
            "name_x1": max_x - 3 * boundary_coordinates.detected_item_width - item_spacing_width,
            "name_x2": max_x - boundary_coordinates.detected_item_width,
            "name_y1": type_y1,
            "name_y2": type_y2,
        }

    async def _extract_stockpile_metadata(
        self, image: cv2.typing.MatLike, boundaries: dict
    ) -> tuple[StockpileType, str]:
        """Extract stockpile type and name from the image.

        Args:
            image (cv2.typing.MatLike): The input image
            boundaries (dict): Dictionary with boundary coordinates

        Returns:
            tuple: (stockpile_type, stockpile_name)
        """
        stockpile_type_image = image[
            boundaries["type_y1"] : boundaries["type_y2"],
            boundaries["type_x1"] : boundaries["type_x2"],
        ]

        stockpile_name_image = image[
            boundaries["name_y1"] : boundaries["name_y2"],
            boundaries["name_x1"] : boundaries["name_x2"],
        ]

        type_ = await self._extract_stockpile_type_from_image(image=stockpile_type_image)

        # Extract name only for certain stockpile types
        if type_ in [StockpileType.SEAPORT, StockpileType.STORAGE_DEPOT]:
            name = await self._extract_text_from_image(image=stockpile_name_image)
        else:
            name = ""

        return (type_, name)

    async def _save_failed_detection(self, file_name: str, image: cv2.typing.MatLike) -> None:
        """Save an image when detection fails.

        Args:
            file_name (str): Name of the file
            image (cv2.typing.MatLike): The input image
        """
        saved_file_name = await self.get_save_image_prefix(file_name=file_name, image=image)
        if saved_file_name:
            await self.save_image(file_name=saved_file_name, image=image)

    async def _process_stockpile_quantities(
        self, image: cv2.typing.MatLike, stockpile: Stockpile, quantities: list
    ) -> None:
        """Process and assign quantities to stockpile items.

        Args:
            image (cv2.typing.MatLike): The input image
            stockpile (Stockpile): The stockpile object to update
            quantities (list): List of quantity coordinates
            file_name (str): Name of the file
            boundaries (dict): Dictionary with boundary coordinates
        """
        # Create image for quantity processing
        quantities_image = await self.create_quantitites_image(
            original_image=image,
            quantity_coords=quantities,
            padding=self._settings.ocr.quantities_padding,
        )

        # Detect quantities
        detected_quantities = await self.process_quantities(image=quantities_image)

        # Validate quantity matching
        if len(detected_quantities) != len(stockpile.items):
            await self._handle_quantity_mismatch(
                stockpile=stockpile, detected_quantities=detected_quantities
            )
            return

        # Assign quantities to items
        for i, item in enumerate(stockpile.items):
            item.quantity = detected_quantities[i]

    async def _handle_quantity_mismatch(
        self, stockpile: Stockpile, detected_quantities: list
    ) -> None:
        """Handle the case where detected quantities don't match the number of items.

        Args:
            stockpile (Stockpile): The stockpile to update
            detected_quantities (list): List of detected quantities
        """
        self._logger.error(
            "%s: Detected %d quantities but %d items",
            stockpile.name,
            len(detected_quantities),
            len(stockpile.items),
        )

        quantities_str = " ".join([str(item) for item in detected_quantities])
        self._logger.error("Quantities: %s", quantities_str)

        # Clear items when quantities don't match
        stockpile.items = []

    async def get_save_image_prefix(
        self, file_name: str, image: Any, stockpile: Stockpile | None = None
    ) -> str:
        """Get the prefix for the image to save.

        Args:
            file_name (str): Name of the file
            image (Any): Image to save
            stockpile (Stockpile | None): Stockpile detected

        Returns:
            str: Prefix for the image to save
        """
        if not any(
            [
                self._settings.developer.save_image,
                self._settings.developer.save_name_image,
                self._settings.developer.save_type_image,
            ]
        ):
            return ""

        if stockpile:
            s_name = stockpile.name
            s_type = stockpile.type.value
            date_now = stockpile.timestamp
            resolution = stockpile.resolution
        else:
            s_name = "undefined"
            s_type = "undefined"
            date_now = datetime.now()
            resolution = f"{image.shape[1]}x{image.shape[0]}"

        date_str = date_now.strftime("%Y-%m-%d")
        time_str = date_now.strftime("%H-%M-%S")

        directory = f"{self._settings.developer.backup_path}/{date_str}/"
        if not os.path.exists(directory):
            os.makedirs(directory)

        return f"{directory}{time_str}-{s_type}-{s_name}-{resolution}-{file_name}"

    async def save_image(
        self,
        file_name: str,
        image: Any,
        name_image: Any = None,
        type_image: Any = None,
    ) -> None:
        """Save the image to the configured path.

        Args:
            file_name (str): Name of the file
            image (Any): Image to save
            name_image (Any): Image with the name detected
            type_image (Any): Image with the type detected
        """
        if not file_name:
            return

        if image is not None and self._settings.developer.save_image:
            cv2.imwrite(f"{file_name}.png", image)

        if name_image is not None and self._settings.developer.save_name_image:
            cv2.imwrite(f"{file_name}_name.png", name_image)

        if type_image is not None and self._settings.developer.save_type_image:
            cv2.imwrite(f"{file_name}_type.png", type_image)

    async def create_quantitites_image(
        self,
        original_image: cv2.typing.MatLike,
        quantity_coords: list[tuple[int, int, int, int]],
        padding: int = 0,
    ) -> numpy.ndarray:
        """Create a composite image from a list of quantity images.

        Args:
            original_image (cv2.typing.MatLike): Original image
            quantity_coords (list[tuple[int, int, int, int]]): Coordinates of the quantities
            padding (int): Padding between images

        Returns:
            numpy.ndarray: Composite image
        """
        gray_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
        quantity_images = self._extract_and_normalize_quantity_images(gray_image, quantity_coords)
        composite = self._create_composite_image(quantity_images, padding)
        return composite

    def _extract_and_normalize_quantity_images(
        self, gray_image: numpy.ndarray, quantity_coords: list[tuple[int, int, int, int]]
    ) -> list[numpy.ndarray]:
        """Extract and normalize quantity images.

        Args:
            gray_image (numpy.ndarray): Grayscale image
            quantity_coords (list[tuple[int, int, int, int]]): Coordinates of the quantities

        Returns:
            list[numpy.ndarray]: List of normalized quantity images
        """
        quantity_images = []
        target_height = 100
        for x, y, w, h in quantity_coords:
            aspect_ratio = w / h
            target_width = int(target_height * aspect_ratio)
            quantity_image = cv2.resize(
                gray_image[y : y + h, x : x + w],
                (target_width, target_height),
                interpolation=cv2.INTER_LANCZOS4,
            )
            quantity_images.append(quantity_image)
        return quantity_images

    def _create_composite_image(
        self, quantity_images: list[numpy.ndarray], padding: int
    ) -> numpy.ndarray:
        """Create a composite image from a list of quantity images.

        Args:
            quantity_images (list[numpy.ndarray]): List of quantity images
            padding (int): Padding between images

        Returns:
            numpy.ndarray: Composite image
        """
        total_width = sum(img.shape[1] for img in quantity_images) + padding * (
            len(quantity_images) - 1
        )
        max_height = max(img.shape[0] for img in quantity_images)

        # Create a blank canvas
        composite = numpy.ones((max_height, total_width), dtype=numpy.uint8) * 255

        # Place normalized images on canvas
        x_offset = 0
        for img in quantity_images:
            h, w = img.shape[:2]
            # Step 1: Apply binary inverse threshold to make the numbers white on black background
            thresh_img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)[1]
            # Step 2: Dilate the image to thicken the numbers
            kernel = numpy.ones((1, 1), numpy.uint8)
            dilated_img = cv2.dilate(thresh_img, kernel, iterations=2)
            composite[0:h, x_offset : x_offset + w] = dilated_img
            x_offset += w + padding

        return composite

    async def process_quantities(self, image: numpy.ndarray) -> list[int]:
        """Process the quantities detected in the image.

        Args:
            image (numpy.ndarray): Image to process
        """
        # Use Tesseract with custom configuration
        custom_config = r'--psm 7 -c tessedit_char_whitelist="0123456789k+ "'
        text = pytesseract.image_to_string(image, config=custom_config, lang="rennernumbers")

        numbers = []
        # Check if the quantity is a number or a Thousand (k+)
        for item in text.split():
            multiplier = 1
            if "k+" in item:
                multiplier = 1000
                item = item.replace("k+", "")

            try:
                ret_val = int(item) * multiplier
            except ValueError:
                ret_val = -1

            numbers.append(ret_val)

        return numbers
