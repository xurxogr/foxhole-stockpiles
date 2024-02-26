import json
import logging
import os.path

import easyocr
import cv2
import numpy
from pydantic import TypeAdapter
from keras.models import load_model

from foxhole_stockpiles.config.settings import Settings
from foxhole_stockpiles.models.catalog_item import CatalogItem
from foxhole_stockpiles.models.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.singleton.singletonmeta import SingletonMeta
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem

class OCR(metaclass=SingletonMeta):
    def __init__(self):
        settings = Settings()
        self.__logger = logging.getLogger(__name__)

        self.__item_min_width = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_MIN_WIDTH))
        self.__item_max_width = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_MAX_WIDTH))
        self.__item_min_ratio = float(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_MIN_WH_RATIO))
        self.__item_max_ratio = float(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_MAX_WH_RATIO))
        self.__item_spacing_height = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_SPACING_HEIGHT))
        self.__item_spacing_width = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_SPACING_WIDTH))
        self.__stockpile_min_width = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_STOCKPILE_MIN_WIDTH))

        # Developer options
        self.__dev_dectect_stockpile_name = int(settings.get(section=Settings.SECTION_DEVELOPER, option=Settings.OPTION_DEV_DETECT_STOCKPILE_NAME))
        self.__dev_dectect_stockpile_type = int(settings.get(section=Settings.SECTION_DEVELOPER, option=Settings.OPTION_DEV_DETECT_STOCKPILE_TYPE))
        self.__dev_dectect_quantities = int(settings.get(section=Settings.SECTION_DEVELOPER, option=Settings.OPTION_DEV_DETECT_QUANTITIES))
        self.__dev_dectect_icons = int(settings.get(section=Settings.SECTION_DEVELOPER, option=Settings.OPTION_DEV_DETECT_ICONS))
        self.__dev_draw_rectangles = int(settings.get(section=Settings.SECTION_DEVELOPER, option=Settings.OPTION_DEV_DRAW_RECTANGLES))

        # Models and catalogs path
        self.__icons_path = settings.get(section=Settings.SECTION_MODELS, option=Settings.OPTION_ICONS_PATH)
        self.__quantity_path = settings.get(section=Settings.SECTION_MODELS, option=Settings.OPTION_QUANTITIES_PATH)
        self.__catalog_items_path = settings.get(section=Settings.SECTION_MODELS, option=Settings.OPTION_CATALOG_ITEMS_PATH)

        self.__icons_model = None
        self.__icons_classes = None
        self.__quantity_model = None
        self.__quantity_classes = None
        self.__catalog_items = None

        # Initalize ocr
        # TODO: Extend to other languages
        self.__ocrreader = easyocr.Reader(lang_list=['en', 'es'])

    async def __init_models(self):
        # Load models and item catalog
        self.__icons_model, self.__icons_classes = await self.__load_model(path=self.__icons_path)
        self.__quantity_model, self.__quantity_classes = await self.__load_model(path=self.__quantity_path)
        self.__catalog_items = await self.__load_catalog(path=self.__catalog_items_path)


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
            raise Exception("Couldn't load the models. Error: {}".format(str(ex))) from None

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

        if image is None or not self.__dev_dectect_icons:
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

        if image is None or not self.__dev_dectect_quantities:
            return -1

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Identify the individual characters
        thresh1 = cv2.threshold(gray, 0, 255,cv2.THRESH_OTSU|cv2.THRESH_BINARY)[1]
        rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        dilation = cv2.dilate(thresh1, rect_kernel, iterations = 1)
        contours, _ = cv2.findContours(dilation, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        characters = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            image = gray[y:y+h, x:x+w]
            resized_image = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA)
            resized_image = cv2.threshold(resized_image, 100, 255, cv2.THRESH_BINARY_INV)[1]
            expanded_imagen = numpy.expand_dims(resized_image, axis=0)
            prediction = self.__quantity_model.predict(expanded_imagen, verbose=0)
            characters.append(self.__quantity_classes[numpy.argmax(prediction)])

        item = "".join(characters[::-1])
        item.replace('k+', '000')
        #cv2.imshow("Imagen: {}".format(ret_val), gray)

        try:
            ret_val = int(item)
        except:
            ret_val = -1

        return ret_val

    async def __extract_text_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Extracts text from an image
        :param image: Image to extract text from
        :returns str: Text found
        """
        if image is None:
            return ""

        try:
            # FIXME: Find a better way. In some cases it doesn't detect - or mistakes 1 and 7
            th = image.copy()
            th[th<200] = 0
            scale=4
            th = cv2.resize(th, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            # crop the region of interest (ROI)
            bbox = numpy.where(th>0)
            roi = th[bbox[0].min():bbox[0].max(), bbox[1].min():bbox[1].max()]

            # Returns [coords(A, B, C, D), text, threshold]
            # A---B  | If Y coord of any point is < 0, it will return wrong order
            # D---C  | As we know the text is in the same line reorder texts using x coord of point A
            ocr_text = self.__ocrreader.readtext(image=roi)
            result = sorted(ocr_text, key=lambda x: x[0][0][0])
            text_found = " ".join([x[1] for x in result])
        except:
            return ""

        return text_found

    async def __extract_stockpile_type_from_image(self, image: cv2.typing.MatLike) -> stockpile_type:
        """
        Extracts the stockpile type from an image
        :param image: Image to extract text from
        :returns stockpile_type: type found
        """

        if image is None or not self.__dev_dectect_stockpile_type:
            return stockpile_type.UNDEFINED

        type_text = await self.__extract_text_from_image(image=image)

        try:
            type_ = stockpile_type(type_text)
        except Exception as ex:
            type_ = stockpile_type.UNDEFINED

        return type_

    async def __extract_stockpile_name_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Extracts the stockpile name from an image
        :param image: Image to extract text from
        :returns str: Text found
        """

        if image is None or not self.__dev_dectect_stockpile_name:
            return ""

        return await self.__extract_text_from_image(image=image)

    async def extract_stockpile_from_file(self, file_name: str, flags: int = cv2.IMREAD_COLOR) -> Stockpile | None:
        """
        Extract the stockfile information from a file.
        :param file_name: str = File name to extract the information from
        :param flags: cv2 read flags. Defaults to cv2.IMREAD_COLOR (Default value for imread)
        :returns Stockpile: Returns the information of the Stockpile or None if nothing is detected
        """

        # Checking if the file exists before trying to read it to avoid warning log message from cv2
        if not file_name or not os.path.isfile(file_name):
            self.__logger.warning("Can't open/read file: {}".format(file_name))
            return None

        image = cv2.imread(filename=file_name, flags=flags)
        return await self.__extract_stockpile_from_image(image=image, file_name=file_name)

    async def extract_stockpile_from_buffer(self, buffer, flags: int = cv2.IMREAD_COLOR) -> cv2.typing.MatLike:
        """
        Reads an image from an existing buffer
        :param buffer: Buffer to read the image from
        :param flags: cv2 read flags. Defaults to cv2.IMREAD_COLOR
        :returns cv2.typing.MatLike: decoded image
        """
        bytes_as_np_array = numpy.frombuffer(await buffer.read(), dtype=numpy.uint8)
        image = cv2.imdecode(bytes_as_np_array, flags)
        return await self.__extract_stockpile_from_image(image=image)

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
        item_min_width = int(self.__item_min_width * image_ratio)
        item_max_width = int(self.__item_max_width * image_ratio)

        item_spacing_width = int(image_ratio * self.__item_spacing_width)
        item_spacing_height = int(image_ratio * self.__item_spacing_height)

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
        detected_item_height = 0
        detected_item_width = 0

        for cnt in contours:
            approx = cv2.approxPolyDP(cnt, 0.01*cv2.arcLength(cnt, True), True)
            if len(approx) != 4:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            # Find rectangles with the correct aspect ratio
            ratio = round(w / h, 2)
            if ratio < self.__item_min_ratio or self.__item_max_ratio < ratio or w < item_min_width or item_max_width < w:
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

            if self.__dev_draw_rectangles:
                # draw a rectangle for quantity. In different colour if it wasn't detected
                cv2.rectangle(image, (quantity_x1, quantity_y1), (quantity_x2, quantity_y2), (0, 0, 255), 2)
                # draw the quantity detected
                cv2.putText(image, str(quantity), (int(x + w/2), y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                # draw a rectangle where the icon was found
                cv2.rectangle(image, (icon_x1, icon_y1), (icon_x2, icon_y2), (255, 0, 255), 2)

        # Include the title in the cropped image
        # [title] <-- same height that the items (detected_item_height)
        # [spacing] <--- config h spacing adapted to the image resolution (item_spacing_height)
        # [first item of the stockpile = shirts] <-- min_y
        min_y -= detected_item_height + item_spacing_height
        min_x -= item_spacing_width

        if max_x < min_x + self.__stockpile_min_width:
            max_x = min_x + self.__stockpile_min_width
        else:
            max_x += item_spacing_width

        # Title: [type]              [name][tab]
        # Using 3*item width for rectangle crop
        # name is shifted to the left one item width
        type_x1 = min_x
        type_x2 = min_x + 3 * detected_item_width
        name_x1 = max_x - 4 * detected_item_width
        name_x2 = max_x - 1 * detected_item_width + int(item_spacing_height/2)
        type_y1 = min_y
        type_y2 = min_y + detected_item_height
        name_y1 = min_y
        name_y2 = type_y2

        stockpile_type_image = image[type_y1:type_y2, type_x1:type_x2]
        stockpile_name_image = image[name_y1:name_y2, name_x1:name_x2]

        if self.__dev_draw_rectangles:
            # Add rectangles over the stockpile type and name
            cv2.rectangle(image, (type_x1, type_y1), (type_x2, type_y2), (255, 0, 255), 2)
            cv2.rectangle(image, (name_x1, name_y1), (name_x2, name_y2), (255, 0, 255), 2)

        type_ = await self.__extract_stockpile_type_from_image(image=stockpile_type_image)
        name = await self.__extract_stockpile_name_from_image(image=stockpile_name_image)

        # Crop the image to store only the stockpile with the type, name and the items
        cropped_image = image[min_y:max_y, min_x:max_x]

        return Stockpile(name=name, type=type_, image=cropped_image, items=items)
