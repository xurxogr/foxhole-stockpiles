import cv2
import glob
import json
import logging

from foxhole_stockpiles.models.singleton.stockpiles import Stockpiles

def main():
    logger = logging.getLogger(__name__)
    stockpiles = Stockpiles()
    catalog = stockpiles.get_catalog()

    for file_name in glob.glob("images/all/*m3.jpg"):
        stockpile = stockpiles.extract_stockpile_from_file(file_name=file_name)
        if stockpile is None:
            logger.warning("No stockpile found in file '{}'".format(file_name))
            continue

        for item in stockpile.items:
            catalog_item = next((x for x in catalog if x.code == item.code), None)
            if catalog_item:
                item.code = catalog_item.display

        print("file_name: {:35}, Name: {:15}, type: {}".format(file_name, stockpile.name, stockpile.type))
        #print(json.dumps(stockpile.model_dump(), indent=2))
        #cv2.imshow(file_name, stockpile.image)

    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
