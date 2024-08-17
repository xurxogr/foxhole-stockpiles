import cv2
from pytesseract import pytesseract
import numpy as np
import os

class VerificationService():

    def __init__(self):
        file_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(file_dir, 'colonial_icon.png')
        self.colonial_icon = cv2.imread(icon_path, cv2.IMREAD_COLOR)

    async def __extract_text_from_image(self, image: cv2.typing.MatLike, scale: bool = False) -> str:
        """
        Extracts text from an image

        Args:
            image (cv2.typing.MatLike): Image to extract text from
            scale (bool): Whether to scale the image before extracting text

        Returns:
            str: Extracted text
        """
        if image is None:
            return ""

        try:
            if scale:
                resized = cv2.resize(image, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            else:
                resized = image

            # Convert to grayscale
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

            # Enhance contrast using CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            inverted = cv2.bitwise_not(clahe.apply(gray))

            pytesseract_text = pytesseract.image_to_string(inverted, lang='eng+fra+deu+por+rus+chi_sim')
            text_found = pytesseract_text.replace('\n', '').replace('\r', '').strip()
        except:
            text_found = ""

        return text_found

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
            bytes_as_np_array = np.frombuffer(picture, dtype=np.uint8)
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
        username_image = image[int(0.63*py):int(0.77*py), int(1.6*px):int(3*px)]
        ocr_text = await self.__extract_text_from_image(image=username_image)
        try:
            data['name'] = ocr_text.split('Level')[0].strip()
        except:
            pass

        # No name found. Either the image is too small of this is a map image
        if data.get('name') is None:
            return data

        try:    
            data['level'] = ocr_text.split('Level: ')[1]
        except:
            pass

        data['colonial'] = await self.find_colonial_icon(image = username_image)

        # Extract Regiment
        regiment_image = image[int(1.4*py):int(1.5*py), :]
        ocr_text = await self.__extract_text_from_image(image=regiment_image)
        count = sum(1 for i in ocr_text.split(' ') if 'Name' in i)
        # 0 = None, 2 = True, 1 = False
        data.update({ "regiment": None if count == 0 else count == 2})

        return data

    async def find_colonial_icon(self, image: cv2.typing.MatLike):
        """
        Finds the colonial icon in the image
        :param image: Picture to find the colonial icon from
        :returns: bool = True if the colonial icon is found
        """

        # Calculate the scale to match the height of the image
        scale = image.shape[0] / self.colonial_icon.shape[0]

        # Resize the template according to the scale
        resized_template = cv2.resize(self.colonial_icon, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # Perform template matching
        res = cv2.matchTemplate(image, resized_template, cv2.TM_CCOEFF_NORMED)

        return cv2.minMaxLoc(res)[1] > 0.7

    async def get_shard(self, image: cv2.typing.MatLike) -> str:
        """
        Finds the shard of the picture
        :param image: Picture to find the shard from
        :returns: str = Shard information
        """
        # Read the image
        height, width, _ = image.shape
        py = height/5
        px = width/20

        # Extract shard
        shard_image = image[int(4.63*py):int(4.7*py), int(px/3):int(px)]
        return await self.__extract_text_from_image(image=shard_image, scale=True)
