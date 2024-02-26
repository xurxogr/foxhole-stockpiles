import glob
import os.path

import cv2
import easyocr
import numpy

from foxhole_stockpiles.models.item import Item


class EasyocrOCR():
    def __init__(self, path: str):
        self.__items = []
        self.__load_items(path=path)
        self.__ocrreader = easyocr.Reader(lang_list=['en'])

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

    def extract_item_from_image(self, image: cv2.typing.MatLike) -> tuple[str, int]:
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

    def extract_quantity_from_image(self, image: cv2.typing.MatLike) -> int:
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
        for scale in [2.2]:
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

    def extract_text_from_image(self, image: cv2.typing.MatLike) -> str:
        """
        Extracts text from an image
        :param image: Image to extract text from
        :returns str: Text found
        """
        if image is None:
            return None

        text = ""
        scale_used = 0

        # FIXME - Find a better way to find the text. In many cases it didn't detected "-"
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