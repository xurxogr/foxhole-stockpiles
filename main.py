import cv2
import glob
import logging

from foxhole_stockpiles.models.singleton.stockpiles import Stockpiles


def main():
    logger = logging.getLogger(__name__)
    stockpiles = Stockpiles()
    debug = stockpiles.get_debug()

    for file_name in glob.glob("images/*.*"):
        stockpile = stockpiles.extract_stockpile_from_file(file_name=file_name)
        if stockpile is None:
            logger.warning("No stockpile found in file '{}'".format(file_name))
            continue

        error = False
        for item in stockpile.items:
            if item.quantity == -1:
                error = True

        if error:
            cv2.imshow(file_name, stockpile.image.image)
        #logger.info("file_name: {} Type: {}, name: {}".format(file_name, stockpile.type.value, stockpile.name))

        if debug:
            cv2.imshow(file_name, stockpile.image.image)

    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
