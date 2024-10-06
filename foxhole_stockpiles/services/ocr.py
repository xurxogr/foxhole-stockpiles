from datetime import datetime
import json
import logging
import os.path

import cv2
from keras.models import load_model
import numpy
from pytesseract import pytesseract

from foxhole_stockpiles.core.config import settings
from foxhole_stockpiles.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.singletonmeta import SingletonMeta


class OCR(metaclass=SingletonMeta):
    def __init__(self):
        self.__logger = logging.getLogger(__name__)

        # Models and classes.
        self.__icons_model, self.__icons_classes = self.__load_model(path=settings.models.icons_path)

    def __load_model(self, path: str) -> tuple:
        """
        Loads a model and its classes

        Args:
            path (str): Path of the model to load

        Returns:
            tuple: Model and classes loaded
        """

        model = None
        classes = None
        try:
            model = load_model("{}.keras".format(path))
            with open("{}.json".format(path)) as file:
                classes = json.load(file)
        except Exception as ex:
            raise Exception(f"Couldn't load the models. Error: ({type(ex).__name__}: {str(ex)})") from None

        return model, classes

    async def __extract_item_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Given an image extracts the id of the identified item

        Args:
            image (cv2.typing.MatLike): Image to detect the type and name from

        Returns:
            str: Item detected. Empty string if not detected
        """

        # Resize the image to 32x32 to match the model
        resized_image = cv2.resize(image, (32, 32))
        expanded_imagen = numpy.expand_dims(resized_image, axis=0)

        prediction = self.__icons_model.predict(expanded_imagen, verbose=0)
        item = self.__icons_classes[numpy.argmax(prediction)]
        return item

    async def __extract_text_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Extracts text from an image

        Args:
            image (cv2.typing.MatLike): Image to extract text from

        Returns:
            str: Extracted text. Empty string if not detected
        """

        if image is None:
            return ""

        try:
            # Upscale the image to improve the OCR detection. Tesseract works better with larger images
            resized_image = cv2.resize(image, None, fx=settings.ocr.text_recognition_scale, fy=settings.ocr.text_recognition_scale, interpolation=cv2.INTER_CUBIC)
            resized_image[resized_image<170] = 0

            # Convert to black numbers with white background
            cropped_image = cv2.threshold(resized_image, 127, 255, cv2.THRESH_BINARY_INV)[1]

            config = '--psm 7'
            lang='custom+eng+fra+deu+por+rus+chi_sim'
            pytesseract_text = pytesseract.image_to_string(cropped_image, lang=lang, config=config)
            text_found = pytesseract_text.split('\n')[0]
        except:
            text_found = ""

        return text_found

    async def __extract_stockpile_type_from_image(self, image: cv2.typing.MatLike) -> stockpile_type:
        """
        Extracts the stockpile type from an image

        Args:
            image (cv2.typing.MatLike): Image to extract the type from

        Returns:
            stockpile_type: Type detected. UNDEFINED if not detected
        """

        name = await self.__extract_text_from_image(image=image)
        if not name:
            return stockpile_type.UNDEFINED

        type_found = None
        translations = settings.stockpile_types.model_dump()
        for valid_names in translations.values():
           if name in valid_names:
               type_found = valid_names[0]
               break

        try:
            return stockpile_type(type_found)
        except ValueError:
            self.__logger.error(f"Stockpile type not found: '{name}'")
            return stockpile_type.UNDEFINED

    async def extract_stockpile_from_image(self, image: cv2.typing.MatLike, file_name: str = "Buffer") -> Stockpile:
        """
        Extracts the stockpile from an image

        Args:
            image: cv2.typing.MatLike = Image to read the stockpile from
            file_name (str): Name of the file

        Returns:
            Stockpile: Stockpile detected
        Args:
            image (cv2.typing.MatLike): Image to extract the stockpile from
            file_name (str): Name of the file

        Returns:
            Stockpile: Stockpile detected. None if not detected
        """

        if image is None:
            return None

        # Values have been configured for a resolution of 1440. Reshape the min-max width accordingly
        # Detection tested with vertical resolutions: 2160, 1440, 1200, 1080, 1050, 1024, 992, 664
        width = image.shape[1]
        height = image.shape[0]
        image_ratio = height / settings.ocr.base_height

        items = []
        item_width = int(settings.ocr.item_width * image_ratio)
        item_height = int(settings.ocr.item_height * image_ratio)
        item_spacing_width = int(image_ratio * settings.ocr.item_spacing_width)
        item_spacing_height = int(image_ratio * settings.ocr.item_spacing_height)

        self.__logger.debug(f"Parsing image {file_name}. width: {width}, height: {height}, ratio: {image_ratio}. Item size: {item_width}x{item_height}, spacing: {item_spacing_width}x{item_spacing_height}")

        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray_image, 50, 255, cv2.THRESH_BINARY)[1]
        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        # Find the rectangles with the correct width, height size and aspect ratio
        min_x = 10000
        min_y = 10000
        max_x = 0
        max_y = 0
        min_quantity_x = 10000
        detected_item_height = 0
        detected_item_width = 0

        quantities = []
        for cnt in contours:
            approx = cv2.approxPolyDP(cnt, 0.01*cv2.arcLength(cnt, True), True)
            if len(approx) != 4:
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # Find rectangles with the correct aspect ratio
            pixel_error = 2
            if abs(w - item_width) > pixel_error or abs(h - item_height) > pixel_error:
                continue

            quantities.append((x, y, w, h))

            # Save the detected item height and width.
            if h > detected_item_height:
                detected_item_height = h

            if w > detected_item_width:
                detected_item_width = w

            # [Icon][Spacing][Quantity]. Icon should be square and we know the height
            # x contains the quantity, substract the icon width (w == h) and the spacing adapted to the image resolution
            icon_x2 = x - item_spacing_width
            icon_x1 = icon_x2 - h
            icon_y1 = y
            icon_y2 = y + h

            quantity_x1 = x
            quantity_y1 = y
            quantity_x2 = x + w
            quantity_y2 = y + h

            # Detect icon
            icon_image = image[icon_y1:icon_y2, icon_x1:icon_x2]
            item_id = await self.__extract_item_from_image(image=icon_image)

            # Add item to the list
            crated = False
            if "crated" in item_id:
                crated = True
                item_id = item_id.replace('-crated', '')

            items.append(StockpileItem(code=item_id, crated=crated))

            # Build a rectangle that contains all other rectangles (Stockpile contents)
            # It will be used to detect the position of the title
            if icon_x1 < min_x:
                min_x = icon_x1

            if icon_y1 < min_y:
                min_y = icon_y1

            if quantity_x2 > max_x:
                max_x = quantity_x2

            if quantity_y2 > max_y:
                max_y = quantity_y2

            if quantity_x2 < min_quantity_x:
                min_quantity_x = quantity_x2

        # If not items have been detected return None
        if not items:
            await self.save_image(stockpile=None, file_name=file_name, image=image)
            return None

        # Include the title in the cropped image
        # [title] <-- same height that the items (detected_item_height)
        # [spacing] <--- config h spacing adapted to the image resolution (item_spacing_height)
        # [first item of the stockpile = shirts] <-- min_y
        min_y -= detected_item_height + item_spacing_height
        min_x -= item_spacing_width

        max_x += item_spacing_width
        # Empty stockpiles have at least 2 items and the 3rd column is empty.
        min_width = 3 * (min_quantity_x - min_x) + min_x + item_spacing_height
        max_x = max(max_x, min_width)

        # Title: [type]              [name][tab]
        # Using 3*item width for rectangle crop
        # name is shifted to the left one item width
        type_x1 = min_x + item_spacing_width
        type_x2 = min_x + 4 * detected_item_width
        name_x1 = max_x - 3 * detected_item_width
        name_x2 = max_x - detected_item_width
        type_y1 = min_y + item_spacing_height
        type_y2 = min_y + detected_item_height - item_spacing_height
        name_y1 = type_y1
        name_y2 = type_y2

        stockpile_type_image = image[type_y1:type_y2, type_x1:type_x2]
        stockpile_name_image = image[name_y1:name_y2, name_x1:name_x2]

        type_ = await self.__extract_stockpile_type_from_image(image=stockpile_type_image)

        if type_ in [stockpile_type.SEAPORT, stockpile_type.STORAGE_DEPOT]:
            name = await self.__extract_text_from_image(image=stockpile_name_image)
        else:
            name = ""

        # Crop the image to store only the stockpile with the type, name and the items
        cropped_image = image[min_y:max_y, min_x:max_x]
        stockpile = Stockpile(name=name, type=type_, items=items, resolution=f"{width}x{height}")
        quantities_image = await self.create_quantitites_image(original_image=image, quantity_coords=quantities, padding=10)

        await self.save_image(
            stockpile=stockpile,
            file_name=file_name,
            image=image,
            name_image=stockpile_name_image,
            type_image=stockpile_type_image,
            stockpile_image=cropped_image
        )

        # Detect all the quantitites
        detected_quantities = await self.process_quantities(image=quantities_image)
        if len(detected_quantities) != len(stockpile.items):
            self.__logger.error(f"{stockpile.name}: Detected {len(detected_quantities)} quantities but {len(stockpile.items)} items")
            quantities_str = " ".join([str(item) for item in detected_quantities])
            self.__logger.error(f"Quantities: {quantities_str}")
            stockpile.items = []
            return stockpile

        for i, item in enumerate(stockpile.items):
            item.quantity = detected_quantities[i]

        return stockpile

    async def save_image(self, stockpile: Stockpile, file_name: str, image: any, name_image: any = None, type_image: any = None, stockpile_image: any = None):
        """
        Saves the image to the configured path

        Args:
            stockpile (Stockpile): Stockpile detected
            file_name (str): Name of the file
            image (any): Image to save
            name_image (any): Image with the name detected
            type_image (any): Image with the type detected
            stockpile_image (any): Image with the stockpile detected
        """

        if not any([settings.developer.save_image, settings.developer.save_name_image, settings.developer.save_type_image]):
            return

        if stockpile:
            s_name = stockpile.name
            s_type = stockpile.type
            date_now = stockpile.timestamp
            resolution = stockpile.resolution
        else:
            s_name = "undefined"
            s_type = "undefined"
            date_now = datetime.now()
            resolution = f"{image.shape[1]}x{image.shape[0]}"

        date_str = date_now.strftime("%Y-%m-%d")
        time_str = date_now.strftime("%H-%M-%S")

        directory = f"{settings.developer.backup_path}/{date_str}/"
        if not os.path.exists(directory):
            os.makedirs(directory)

        file_name = f"{directory}{time_str}-{s_type}-{s_name}-{resolution}-{file_name}"

        if image is not None and settings.developer.save_image:
            cv2.imwrite("{}.png".format(file_name), image)

        if name_image is not None and settings.developer.save_name_image:
            cv2.imwrite("{}_name.png".format(file_name), name_image)

        if type_image is not None and settings.developer.save_type_image:
            cv2.imwrite("{}_type.png".format(file_name), type_image)

    async def create_quantitites_image(self, original_image: cv2.typing.MatLike, quantity_coords: list[tuple[int, int, int, int]], padding: int=0) -> numpy.ndarray:
        """
        Create a composite image from a list of quantity images.

        Args:
            original_image (cv2.typing.MatLike): Original image
            quantity_coords (list[tuple[int, int, int, int]]): Coordinates of the quantities
            padding (int): Padding between images

        Returns:
            numpy.ndarray: Composite image
        """

        gray_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)

        # Extract and normalize quantity images

        quantity_images = []

        # Normalize all images to a standard height
        target_height = 100
        for x, y, w, h in quantity_coords:
            aspect_ratio = w / h
            target_width = int(target_height * aspect_ratio)
            quantity_image = cv2.resize(gray_image[y:y+h, x:x+w], (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
            quantity_images.append(quantity_image)

        # Calculate dimensions for the composite image
        total_width = sum(img.shape[1] for img in quantity_images) + padding * (len(quantity_images) - 1)
        max_height = max(img.shape[0] for img in quantity_images)

        # Create a blank canvas
        composite = numpy.ones((max_height, total_width), dtype=numpy.uint8) * 255

        hyphen_height = target_height // 2
        hyphen_width = 24
        # Place normalized images on canvas
        x_offset = 0
        for img in quantity_images:
            h, w = img.shape[:2]

            # Step 1: Apply binary inverse threshold to make the numbers white on black background
            thresh_img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)[1]
            # Step 2: Dilate the image to thicken the numbers
            kernel = numpy.ones((1, 1), numpy.uint8)
            dilated_img = cv2.dilate(thresh_img, kernel, iterations=2)
            composite[0:h, x_offset:x_offset+w] = dilated_img

            # Add a hyphen to separate the numbers. This is useful for tesseract to recognize numbers better
            # In some edge cases 56 was being recognized really badly
            hyphen_pos = x_offset + w + padding - hyphen_width // 2
            if hyphen_pos + hyphen_width < total_width:
                composite[hyphen_height-2:hyphen_height+2, hyphen_pos:hyphen_pos+hyphen_width] = 0

            x_offset += w + padding

        return composite

    async def process_quantities(self, image: numpy.ndarray) -> list[int]:
        """
        Process the quantities detected in the image.

        Args:
            image (numpy.ndarray): Image to process
        """

        # Use Tesseract with custom configuration
        custom_config = r'--psm 7 -c tessedit_char_whitelist="0123456789k+ "'
        text = pytesseract.image_to_string(image, config=custom_config, lang='rennernumbers')

        numbers = []
        # Check if the quantity is a number or a Thousand (k+)
        for item in text.split():
            multiplier = 1
            if 'k+' in item:
                multiplier = 1000
                item = item.replace('k+', '')

            try:
                ret_val = int(item) * multiplier
            except:
                ret_val = -1

            numbers.append(ret_val)

        return numbers
