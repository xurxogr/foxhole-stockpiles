import cv2
from easyocr import Reader
import numpy

class VerificationService():

    def __init__(self):
        self.reader = Reader(lang_list=['en'])

    async def verify_pictures(self, pictures: list[bytes]) -> dict:
        """
        Verifies the pictures
        :param pictures: list[bytes] = List of pictures to verify
        :returns: dict = Result of the verification
        """

        if len(pictures) != 2:
            return {"error": "Invalid number of pictures {}".format(len(pictures))}
        
        images = []
        for picture in pictures:
            bytes_as_np_array = numpy.frombuffer(picture, dtype=numpy.uint8)
            image = cv2.imdecode(buf=bytes_as_np_array, flags=cv2.IMREAD_COLOR)
            images.append(image)
        
        regiment_info = await self.find_user_info(image=images[0])
        if regiment_info.get('name') is None:
            regiment_info = await self.find_user_info(image=images[1])
            regiment_info['shard'] = await self.get_shard(image=images[0])
        else:
            regiment_info['shard'] = await self.get_shard(image=images[1])

        if regiment_info.get('name') is None:
            return {"error": "No name found in any of the images"}

        return regiment_info

    async def find_user_info(self, image: cv2.typing.MatLike) -> dict:
        """
        Finds the name of the picture
        :param image: bytes = Picture to find the name, level and regiment from
        :returns: str = Username information
        """
        height, width, _ = image.shape
        py = height/5
        px = width/5

        data = { 
            "name": None,
            "level": None,
            "regiment": None
        }

        # Extract username and level
        username = image[int(0.63*py):int(0.77*py), int(1.6*px):int(3*px)]
        ocr_text = self.reader.readtext(username)

        try:
            data['name'] = ocr_text[0][1].replace('Name: ', '')
        except:
            pass

        # No name found. Either the image is too small of this is a map image
        if data.get('name') is None:
            return data

        try:    
            data['level'] = ocr_text[1][1].replace('Level: ', '')
        except:
            pass

        # Extract Regiment
        regiment = image[int(1.4*py):int(1.5*py), :]
        ocr_text = self.reader.readtext(regiment)
        count = sum(1 for i in ocr_text if i[1] == 'Name')
        if count == 0:
            data.update({ "regiment": None })
        else:
            data.update({ "regiment": count == 2})

        return data

    async def get_shard(self, image: cv2.typing.MatLike) -> str:
        """
        Finds the shard of the picture
        :param image: Picture to find the shard from
        :returns: str = Shard information
        """
        # Read the image
        height, width, _ = image.shape
        py = height/5
        px = width/5


        # Extract shard
        shard_image = image[int(4.63*py):int(4.7*py), 0:int(px)]
        ocr_text = self.reader.readtext(shard_image)
        try:
            return ocr_text[0][1]
        except:
            return None
