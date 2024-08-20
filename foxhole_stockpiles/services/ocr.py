from datetime import datetime
import json
import logging
import os.path

import cv2
from keras.models import load_model
import numpy
from pydantic import TypeAdapter
from pytesseract import pytesseract

from foxhole_stockpiles.core.config import settings
from foxhole_stockpiles.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.catalog_item import CatalogItem
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.singletonmeta import SingletonMeta


class OCR(metaclass=SingletonMeta):
    def __init__(self):
        self.__logger = logging.getLogger(__name__)

        # Models and classes. Initialized on first use
        self.__icons_model = None
        self.__icons_classes = None
        self.__quantity_model = None
        self.__quantity_classes = None
        self.__catalog_items = None

    async def __init_models(self):
        # Load models and item catalog
        self.__icons_model, self.__icons_classes = await self.__load_model(path=settings.models.icons_path)
        self.__quantity_model, self.__quantity_classes = await self.__load_model(path=settings.models.quantities_path)
        self.__catalog_items = await self.__load_catalog(path=settings.models.catalog_items_path)

    async def __load_catalog(self, path: str) -> dict:
        """
        Loads the item catalog
        :param path: str = Path of the file to read the catalog from
        """
        catalog = None
        try:
            with open(path) as file:
                catalog = json.load(file)

            catalog = TypeAdapter(list[CatalogItem]).validate_python(catalog)
        except Exception as ex:
            raise Exception("Couldn't load the items catalog. Error: {}".format(str(ex)))

        return catalog

    async def __load_model(self, path: str) -> tuple:
        model = None
        classes = None
        try:
            model = load_model("{}.keras".format(path))
            with open("{}.json".format(path)) as file:
                classes = json.load(file)
        except Exception as ex:
            raise Exception(f"Couldn't load the models. Error: ({type(ex).__name__}: {str(ex)})") from None

        return model, classes

    async def get_catalog(self) -> list[CatalogItem]:
        """
        Returns the items catalog
        """
        if not self.__catalog_items:
            await self.__init_models()

        return self.__catalog_items

    async def __extract_item_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Given an image extracts the id of the identified item

        :param image: cv2.typing.MatLike = Image to detect the item from
        :returns str: code of the item detected
        """

        if image is None or not settings.developer.detect_icons:
            return ""

        resized_image = cv2.resize(image, (32, 32))
        expanded_imagen = numpy.expand_dims(resized_image, axis=0)

        prediction = self.__icons_model.predict(expanded_imagen, verbose=0)
        item = self.__icons_classes[numpy.argmax(prediction)]
        return item

    async def __extract_quantity_from_image(self, image: cv2.typing.MatLike) -> int:
        """
        Extract the quantity from an image
        Image: [ "Number" ]
        The number could contain k+ to indicate thousands of the number

        :param image: Image to detect the type and name from
        :returns int: Quantity detected
        """

        if image is None or not settings.developer.detect_quantities:
            return -1

        # Threshold the image to create a binary image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        thresh1 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        # Find non-zero pixels
        non_zero = cv2.findNonZero(thresh1)

        if non_zero is None:
            self.__logger.info("Error: No white pixels found in the image")
            return -1

        # Get the bounding rectangle of all non-zero pixels
        x, y, w, h = cv2.boundingRect(non_zero)

        # Convert to black numbers with white background and resize to 32x32 to match the model
        cropped_image = cv2.threshold(image[y:y+h, x:x+w], 127, 255, cv2.THRESH_BINARY_INV)[1]
        resized_image = cv2.resize(cropped_image, (32, 32))
        expanded_imagen = numpy.expand_dims(resized_image, axis=0)

        prediction = self.__quantity_model.predict(expanded_imagen, verbose=0)
        item = self.__quantity_classes[numpy.argmax(prediction)]

        multiplier = 1
        if 'k+' in item:
            multiplier = 1000
            item = item.replace('k+', '')

        try:
            ret_val = int(item) * multiplier
        except:
            print(f"Error converting quantity '{item}' to int")
            ret_val = -1

        return ret_val

    async def __extract_text_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Extracts text from an image

        Args:
            image (cv2.typing.MatLike): Image to extract text from

        Returns:
            str: Extracted text
        """
        if image is None:
            return ""

        try:
            scale=4
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            image[image<170] = 0

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Enhance contrast using CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            inverted = cv2.bitwise_not(clahe.apply(gray))

            config = '--psm 7'
            lang = 'eng+fra+deu+por+rus+chi_sim'
            pytesseract_text = pytesseract.image_to_string(inverted, config=config, lang=lang)
            text_found = pytesseract_text.replace('\n', '').replace('\r', '').strip()
        except:
            text_found = ""

        return text_found

    async def __extract_stockpile_type_from_image(self, image: cv2.typing.MatLike) -> stockpile_type:
        """
        Extracts the stockpile type from an image

        Args:
            image (cv2.typing.MatLike): Image to extract the type from

        Returns:
            stockpile_type: Type of the stockpile
        """

        if image is None or not settings.developer.detect_stockpile_type:
            return stockpile_type.UNDEFINED

        name = await self.__extract_text_from_image(image=image)
        return await self.__extract_stockpile_type_from_name(name=name)

    async def __extract_stockpile_type_from_name(self, name: str) -> stockpile_type:
        """
        Extracts the stockpile type from the name

        Args:
            name (str): Name of the stockpile

        Returns:
            stockpile_type: Type of the stockpile
        """
            # TODO - Get this out of the enum and move it to the service. Translations should be read from the ini file

        _translations = {
            # English, Chinese, French, German, Portuguese, Russian
            'Encampment': settings.stockpile_types.encampment,
            'Keep': settings.stockpile_types.keep,
            'Safe House': settings.stockpile_types.safe_house,
            'Relic Base': settings.stockpile_types.relic_base,
            'Bunker Base': settings.stockpile_types.bunker_base,
            'Border Base': settings.stockpile_types.border_base,
            'Town Base': settings.stockpile_types.town_base,
            'BMS - Longhook': settings.stockpile_types.bms_longhook,
            'Storage Depot': settings.stockpile_types.storage_depot,
            'Seaport': settings.stockpile_types.seaport,
            'Undefined': settings.stockpile_types.undefined
        }

        for item_type, translations in _translations.items():
            if name in translations:
                try:
                    return stockpile_type(item_type)
                except ValueError:
                    break

        self.__logger.info(f"Undetected stockpile type '{name}'")
        return stockpile_type.UNDEFINED

    async def __extract_stockpile_name_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Extracts the stockpile name from an image
        :param image: Image to extract text from
        :returns str: Text found
        """

        if image is None or not settings.developer.detect_stockpile_name:
            return ""

        return await self.__extract_text_from_image(image=image)

    async def extract_stockpile_from_file(self, file_name: str) -> Stockpile | None:
        """
        Extract the stockfile information from a file.
        :param file_name: str = File name to extract the information from
        :returns Stockpile: Returns the information of the Stockpile or None if nothing is detected
        """

        # Checking if the file exists before trying to read it to avoid warning log message from cv2
        if not file_name or not os.path.isfile(file_name):
            self.__logger.warning("Can't open/read file: {}".format(file_name))
            return None

        image = cv2.imread(filename=file_name, flags=cv2.IMREAD_COLOR)
        return await self.__extract_stockpile_from_image(image=image, file_name=file_name)

    async def extract_stockpile_from_buffer(self, buffer, image_prefix: str) -> Stockpile | None:
        """
        Reads an image from an existing buffer
        :param buffer: Buffer to read the image from
        :param image_prefix: str = Prefix to use to save the images if the option is enabled
        :returns Stockpile: Returns the information of the Stockpile or None if nothing is detected
        """
        bytes_as_np_array = numpy.frombuffer(await buffer.read(), dtype=numpy.uint8)
        image = cv2.imdecode(buf=bytes_as_np_array, flags=cv2.IMREAD_COLOR)
        return await self.__extract_stockpile_from_image(image=image, file_name=image_prefix)

    async def __extract_stockpile_from_image(self, image: cv2.typing.MatLike, file_name: str = "Buffer") -> Stockpile:
        """
        Given an image extracts the portion that contains the stockpile and information about the location of the items.
        This method does not returns the items themselves but the location in the image

        :param image: cv2.typing.MatLike = Image to read the stockpile from
        :returns Stockpile: Stockpile information
        """

        if image is None:
            return None

        # Lazy initialization.
        if not self.__icons_model:
            await self.__init_models()

        # Values have been configured for a resolution of 1440. Reshape the min-max width accordingly
        # Detection tested with vertical resolutions: 2160, 1440, 1200, 1080, 1050, 1024, 992, 664
        width = image.shape[1]
        height = image.shape[0]
        image_ratio = height / 1440

        items = []
        item_min_width = int(settings.ocr.item_min_w * image_ratio)
        item_max_width = int(settings.ocr.item_max_w * image_ratio)

        item_spacing_width = int(image_ratio * settings.ocr.item_spacing_width)
        item_spacing_height = int(image_ratio * settings.ocr.item_spacing_height)

        self.__logger.debug("Parsing image {}. width: {}, height: {}, ratio: {}. Item min-max width: [{}-{}]".format(
            file_name, width, height, image_ratio, item_min_width, item_max_width))

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

        for cnt in contours:
            approx = cv2.approxPolyDP(cnt, 0.01*cv2.arcLength(cnt, True), True)
            if len(approx) != 4:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            # Find rectangles with the correct aspect ratio
            ratio = round(w / h, 2)
            if ratio < settings.ocr.item_min_ratio or settings.ocr.item_max_ratio < ratio or w < item_min_width or item_max_width < w:
                #self.__logger.debug("x: {}, y: {}, w: {}, h: {}, ratio: {}".format(x, y, w, h, ratio))
                continue

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

            # Detect quantity
            quantity_image = image[quantity_y1:quantity_y2, quantity_x1:quantity_x2]
            quantity = await self.__extract_quantity_from_image(image=quantity_image)

            # Detect icon
            icon_image = image[icon_y1:icon_y2, icon_x1:icon_x2]
            item_id = await self.__extract_item_from_image(image=icon_image)

            # Add item to the list
            crated = False
            if "crated" in item_id:
                crated = True
                item_id = item_id.replace('-crated', '')

            item = StockpileItem(
                code=item_id,
                quantity=quantity,
                crated=crated,
                icon_image=icon_image,
                quantity_image=quantity_image
            )
            items.append(item)

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

            if settings.developer.draw_rectangles:
                # draw a rectangle for quantity. In different colour if it wasn't detected
                cv2.rectangle(image, (quantity_x1, quantity_y1), (quantity_x2, quantity_y2), (0, 0, 255), 2)
                # draw the quantity detected
                cv2.putText(image, str(quantity), (int(x + w/2), y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                # draw a rectangle where the icon was found
                cv2.rectangle(image, (icon_x1, icon_y1), (icon_x2, icon_y2), (255, 0, 255), 2)

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
        type_x1 = min_x + item_spacing_width - 2
        type_x2 = min_x + 3 * detected_item_width
        name_x1 = max_x - 4 * detected_item_width
        name_x2 = max_x - 1 * detected_item_width + int(item_spacing_height/2)
        type_y1 = min_y + item_spacing_height
        type_y2 = min_y + detected_item_height - item_spacing_height
        name_y1 = type_y1
        name_y2 = type_y2

        stockpile_type_image = image[type_y1:type_y2, type_x1:type_x2]
        stockpile_name_image = image[name_y1:name_y2, name_x1:name_x2]

        if settings.developer.draw_rectangles:
            # Add rectangles over the stockpile type and name
            cv2.rectangle(image, (type_x1, type_y1), (type_x2, type_y2), (255, 0, 255), 2)
            cv2.rectangle(image, (name_x1, name_y1), (name_x2, name_y2), (255, 0, 255), 2)

        type_ = await self.__extract_stockpile_type_from_image(image=stockpile_type_image)
        name = await self.__extract_stockpile_name_from_image(image=stockpile_name_image)

        # Crop the image to store only the stockpile with the type, name and the items
        cropped_image = image[min_y:max_y, min_x:max_x]
        stockpile = Stockpile(name=name, type=type_, image=cropped_image, items=items)
        await self.save_image(stockpile=stockpile, file_name=file_name, image=image, name_image=stockpile_name_image, type_image=stockpile_type_image, stockpile_image=cropped_image)
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
        if not any([settings.developer.save_image, settings.developer.save_stockpile, settings.developer.save_name, settings.developer.save_type]):
            return

        if stockpile:
            s_name = stockpile.name
            s_type = stockpile.type
        else:
            s_name = "undefined"
            s_type = "undefined"

        date_now = datetime.now()
        date_str = date_now.strftime("%Y-%m-%d")
        time_str = date_now.strftime("%H-%M-%S")
        directory = "{}/{}/".format(settings.developer.backup_path or ".", date_str)
        if not os.path.exists(directory):
            os.makedirs(directory)

        file_name = "{}{}-{}-{}-{}".format(directory, time_str, s_type, s_name, file_name)
        if image is not None and settings.developer.save_image:
            cv2.imwrite("{}.png".format(file_name), image)
        if name_image is not None and settings.developer.save_name:
            cv2.imwrite("{}_name.png".format(file_name), name_image)
        if type_image is not None and settings.developer.save_type:
            cv2.imwrite("{}_type.png".format(file_name), type_image)
        if stockpile_image is not None and settings.developer.save_stockpile:
            cv2.imwrite("{}_stockpile.png".format(file_name), stockpile_image)
