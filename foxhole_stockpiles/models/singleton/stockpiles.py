import glob
import logging
import os.path

import cv2
import easyocr
import numpy

from foxhole_stockpiles.config.settings import Settings
from foxhole_stockpiles.models.enums.stockpile_type import stockpile_type
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.models.image import Image
from foxhole_stockpiles.models.item import Item
from foxhole_stockpiles.models.singleton.singletonmeta import SingletonMeta
from foxhole_stockpiles.models.stockpile import Stockpile


class Stockpiles(metaclass=SingletonMeta):
    def __init__(self):
        settings = Settings()
        self.__logger = logging.getLogger(__name__)
        self.__item_min_width = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_MIN_WIDTH))
        self.__item_max_width = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_MAX_WIDTH))
        self.__item_min_ratio = float(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_MIN_WH_RATIO))
        self.__item_max_ratio = float(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_MAX_WH_RATIO))
        self.__item_spacing_height = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_SPACING_HEIGHT))
        self.__item_spacing_width = int(settings.get(section=Settings.SECTION_OCR, option=Settings.OPTION_OCR_ITEM_SPACING_WIDTH))
        self.__debug = int(settings.get(section=Settings.SECTION_GENERAL, option=Settings.OPTION_DEBUG))
        path = settings.get(section=Settings.SECTION_GENERAL, option=Settings.OPTION_ICONS_PATH)
        self.__items = None
        self.__load_items(path=path)
        self.__ocrreader = easyocr.Reader(lang_list=['en'])

    def get_debug(self) -> bool:
        return self.__debug == 1

    def __load_items(self, path: str):
        """
        Loads the db items
        :param path: str = Path to load the icons from
        """

        if not path:
            raise Exception("Icons path not defined")

        self.__items = []
        for file_name in glob.glob("{}/*.*".format(path)):
            image = cv2.imread(filename=file_name, flags=cv2.IMREAD_GRAYSCALE)
            item = Item(
                id=os.path.splitext(os.path.basename(file_name))[0],
                image=image
            )
            self.__items.append(item)

        if not self.__items:
            message = "No icons found in the icons folder: {}".format(path)
            self.__logger.error(message)
            raise Exception(message)

    def extract_stockpile_from_file(self, file_name: str, flags: int = cv2.IMREAD_COLOR) -> Stockpile | None:
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
        return self.__extract_stockpile_from_image(image=image, file_name=file_name)

    def extract_stockpile_from_buffer(self, buffer, flags: int = cv2.IMREAD_COLOR) -> cv2.typing.MatLike:
        """
        Reads an image from an existing buffer
        :param buffer: Buffer to read the image from
        :param flags: cv2 read flags. Defaults to cv2.IMREAD_COLOR
        :returns cv2.typing.MatLike: decoded image
        """
        bytes_as_np_array = numpy.frombuffer(buffer.read(), dtype=numpy.uint8)
        image = cv2.imdecode(bytes_as_np_array, flags)
        return self.__extract_stockpile_from_image(image=image)

    def __resize_image(self, image: cv2.typing.MatLike, scale: float = 4.4) -> cv2.typing.MatLike:
        """
        Resizes an image keeping the aspect ratio
        :param image: Image to rescale
        :param scale: Scale to resize
        :returns cv2.typing.MatLike: Rescaled image
        """
        if image is None:
            return None

        if scale == 1:
            return image

        return cv2.resize(image, None, fx=scale, fy=scale)

    def __extract_text_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Extracts text from an image
        :param image: Image to extract text from
        :returns str: Text found
        """
        if image is None:
            return None

        text = ""
        scale_used = 0

        # FIXME - Find a better way to find the text. It many cases it didn't detected "-"
        # Depending on the resolution the scale 11 or 18 is needed
        for scale in [4, 11, 18]:
            resized_image = self.__resize_image(image=image, scale=scale)
            text_found = ""
            try:
                ocr_text = self.__ocrreader.readtext(image=resized_image)
                if ocr_text:
                    text_found = ocr_text[0][1]
            except:
                continue

            if len(text) < len(text_found):
                text = text_found
                scale_used = scale

        #self.__logger.warning("Text found: {}. Scale: {}".format(text, scale_used))

        return text

    def __extract_quantity_from_image(self, image: cv2.typing.MatLike) -> int:
        """
        Extract the quantity from an image
        Image: [ "Number" ]
        The number could contain k to indicate 1000+

        :param image: Image to detect the type and name from
        :returns int: Quantity detected
        """

        if image is None:
            return None

        # most of the values are detected with the first scale.
        # The rest of the scales have been proved to detect other numbers depending on the resolution of the image
        for scale in [2.2, 4,4, 8, 20]:
            resized_image = self.__resize_image(image=image, scale=scale)
            ocr_text = None
            try:
                ocr_text = self.__ocrreader.readtext(image=resized_image, allowlist='0123456789k')
            except Exception as ex:
                self.__logger.error("Error processing text from an image: {}".format(str(ex)))

            if ocr_text:
                text = ocr_text[0][1]
                number = -1
                try:
                    if 'k' in text:
                        number = int(text.replace('k', ''))*1000
                    else:
                        number = int(text)
                except:
                    pass

                return number

        return -1

    def __extract_item_from_image(self, image: cv2.typing.MatLike) -> tuple[str, int]:
        """
        Given an image extracts the id of the identified item

        :param image: cv2.typing.MatLike = Image to detect the item from
        :returns tuple[str, int]: item id and threshold
        """
        id = None
        item_threshold = 0

        # Cache the rescaled image to fit the different icons size
        # TODO: Check if this resize is really needed...
        rescaled_images = {}
        for item in self.__items:
            icon_image = item.image
            dims = (icon_image.shape[1], icon_image.shape[0])
            if dims not in rescaled_images:
                rescaled_images[dims] = cv2.resize(image, dims)

            rescaled_image = rescaled_images[dims]
            res = cv2.matchTemplate(rescaled_image, icon_image, cv2.TM_CCOEFF_NORMED)
            threshold = numpy.amax(res)

            if threshold > item_threshold:
                id = item.id
                item_threshold = threshold

        return id, item_threshold

    def __extract_stockpile_from_image(self, image: cv2.typing.MatLike, file_name: str = "Buffer") -> Stockpile:
        """
        Given an image extracts the portion that contains the stockpile and information about the location of the items.
        This method does not returns the items themselves but the location in the image

        :param image: cv2.typing.MatLike = Image to read the stockpile from
        :returns Stockpile: Stockpile information
        """

        if image is None:
            return None

        # Values have been configured for a resolution of 1440. Reshape the min-max width accordingly
        # Detection tested with vertical resolutions: 2156, 1440, 1200, 1080, 1050, 1024, 992, 664
        width = image.shape[1]
        height = image.shape[0]
        image_ratio = height / 1440

        items = []
        item_min_width = int(self.__item_min_width * image_ratio)
        item_max_width = int(self.__item_max_width * image_ratio)

        if self.__debug:
            self.__logger.info("Parsing image {}. width: {}, height: {}, ratio: {}. Item min-max width: [{}-{}]".format(
                file_name, width, height, image_ratio, item_min_width, item_max_width))

        # TODO: Find a better way to know if the image is color or gray
        original_image = image
        if len(image.shape) > 2:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        thresh = cv2.threshold(image,50,255,0)[1]
        # FIXME - Replace ints with proper cv2 variables
        contours, _ = cv2.findContours(image=thresh, mode=1, method=2)

        # Find the rectangles with the correct width, height size and aspect ratio
        mx1 = 10000
        my1 = 10000
        mx2 = 0
        my2 = 0
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

            item_spacing_width = int(image_ratio * self.__item_spacing_width)
            item_spacing_height = int(image_ratio * self.__item_spacing_height)

            # [Icon][Spacing][Quantity]. Icon should be square and we know the height
            # x contains the quantity, rest the icon width (w == h) + the spacing adapted to the image resolution
            x1 = x - h - item_spacing_width
            y1 = y
            x2 = x + w
            y2 = y + h

            # Detect quantity
            quantity_image = image[y:y2, x:x2]
            quantity = self.__extract_quantity_from_image(image=quantity_image)

            # Detect icon
            icon_image = image[y:y2, x1:x1+h]
            item_id, threshold = self.__extract_item_from_image(image=icon_image)

            # Add item to the list
            item = StockpileItem(
                id=item_id,
                image=icon_image,
                quantity=quantity,
                threshold=threshold
            )
            items.append(item)

            # Build a rectangle that contains all other rectangles (Stockpile contents)
            # It will be used to detect the position of the title
            if x1 < mx1:
                mx1 = x1

            if y1 < my1:
                my1 = y1

            if x2 > mx2:
                mx2 = x2

            if y2 > my2:
                my2 = y2

            if self.__debug:
                # draw a rectangle for quantity. In different colour if it wasn't detected
                if quantity == -1:
                    color = (0, 0, 255)
                else:
                    color = (0, 255, 0)
                cv2.rectangle(original_image, (x, y), (x + w, y + h), color, 2)

                # draw a rectangle where the icon was found
                color = (255, 0, 255)
                cv2.rectangle(original_image, (x1, y), (x1 + h, y2), color, 2)



        # Include the title in the cropped image
        # [title] <-- same height that the items (detected_item_height)
        # [spacing] <--- config h spacing adapted to the image resolution (item_spacing_height)
        # [first item of the stockpile = shirts] <-- my1
        my1 -= detected_item_height + item_spacing_height
        mx1 -= item_spacing_width

        # Min width = 6 * [icon][spacing][item] + 5*[spacing]
        min_width = (detected_item_height + item_spacing_width + detected_item_width) * 6 + item_spacing_width * 5
        if mx2 < mx1 + min_width:
            mx2 = mx1 + min_width
        else:
            mx2 += item_spacing_width

        # Title: [type]              [name][tab]
        # Using 3*item width for rectangle crop
        # name is shifted to the left one item width
        tx1 = mx1
        tx2 = mx1 + 3 * detected_item_width
        nx1 = mx2 - 4 * detected_item_width
        nx2 = mx2 - 1 * detected_item_width
        ty1 = my1
        ty2 = my1 + detected_item_height
        ny1 = my1
        ny2 = ty2

        stockpile_type_image = image[ty1:ty2, tx1:tx2]
        stockpile_name_image = image[ny1:ny2, nx1:nx2]
        if self.__debug:
            # Add rectangles over the title and name
            cv2.rectangle(original_image, (tx1, my1), (tx2, ty2), (255, 0, 255), 2)
            cv2.rectangle(original_image, (nx1, ny1), (nx2, ny2), (255, 0, 255), 2)

        type_text = self.__extract_text_from_image(image=stockpile_type_image)
        try:
            type_ = stockpile_type(type_text)
        except:
            type_ = stockpile_type.UNDEFINED

        name = ""
        if type_ in [stockpile_type.SEAPORT, stockpile_type.STORAGE_DEPOT]:
            name = self.__extract_text_from_image(image=stockpile_name_image)

        # Crop the image to store only the stockpile with the title and the items
        cropped_image = original_image[my1:my2, mx1:mx2]

        return Stockpile(name=name, type=type_, image=Image(name=file_name, image=cropped_image), items=items)
