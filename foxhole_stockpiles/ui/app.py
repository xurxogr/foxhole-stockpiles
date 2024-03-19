from asyncio import run
from io import BytesIO

from async_tkinter_loop import async_handler
from async_tkinter_loop import async_mainloop
from mss import mss
from PIL import Image
from pynput import keyboard
import pywinctl
import ttkbootstrap as tb

from foxhole_stockpiles.config.settings import Settings
from foxhole_stockpiles.connectors.hermes import HermesConnector
from foxhole_stockpiles.models.keypress import KeyPress
from foxhole_stockpiles.models.singleton.ocr import OCR

class App(tb.Window):
    def __init__(self, title: str, width: int = 400, height: int = 600, theme: str = 'darkly'):
        if width is None or width < 0:
            raise ValueError("Width must be a valid positive integer")

        if height is None or height < 0:
            raise ValueError("Height must be a valid positive integer")

        super().__init__(themename=theme, title=title, minsize=(width, height), resizable=(False, False))

        # text of the entries. It will be used for storing config options
        self.__key_text = tb.StringVar()
        self.__url_text = tb.StringVar()
        self.__token_text = tb.StringVar()
        self.__capture_text = tb.StringVar()

        # Create UI
        options_frame = tb.Frame(self)

        # Key
        tb.Label(options_frame, text="Screenshot key").grid(row=0, column=0)
        self.__key_entry = tb.Entry(options_frame, name='keybind', textvariable=self.__key_text)
        self.__key_entry.config(state="disabled")
        self.__key_entry.grid(row=0, column=1, sticky=tb.E + tb.W)

        # Server URL
        tb.Label(options_frame, text="Server URL").grid(row=1, column=0)
        self.__url_entry = tb.Entry(options_frame, name='url', textvariable=self.__url_text)
        self.__url_entry.grid(row=1, column=1, sticky=tb.E + tb.W)

        # Server Token
        tb.Label(options_frame, text="Server Token").grid(row=2, column=0)
        self.__token_entry = tb.Entry(options_frame, name='token', textvariable=self.__token_text, width=50)
        self.__token_entry.grid(row=2, column=1, sticky=tb.E + tb.W)

        buttons_frame = tb.Frame(self)
        centered_frame = tb.Frame(self)

        self.__capture_text.set("Enable capture")
        tb.Button(centered_frame, textvariable=self.__capture_text, bootstyle = 'success', command=self.capture).grid(row=0, column=0, padx=10, sticky=tb.E + tb.W)
        tb.Button(centered_frame, text='save options', command=self.save_options).grid(row=0, column=1, padx=10, sticky=tb.E + tb.W)
        tb.Button(centered_frame, text='change keybind', command=self.change_key).grid(row=0, column=2, padx=10, sticky=tb.E + tb.W)

        options_frame.pack(fill='both', expand=True)
        buttons_frame.pack(fill='both', expand=True)
        centered_frame.place(in_=buttons_frame, anchor="c", relx=.5)

        # Fill the components with the values from config.ini
        self.__read_options()
        async_mainloop(self)

    @async_handler
    async def change_key(self):
        """
        "Change keybind" callback.
        Opens a new thread to capture a new keybind.
        """
        self.__key_text.set(value="Waiting for a new key...")
        from asyncio import sleep
        await sleep(0.5)
        k = KeyPress()
        key = k.read_key()

        if key is None:
            return

        self.__set_hotkey(key=key)

    def __set_hotkey(self, key: str):
        """
        Updates the UI with the defined keybind.
        If there is keybind or it's invalid to be used as global hotkey a message will be displayes
        """
        if not key:
            self.__hotkey = None
            text = "<No key defined>"
        else:
            try:
                k = KeyPress()
                self.__hotkey = k.prepare_for_global_hotkey(key)
                text = key
            except ValueError:
                self.__hotkey = None
                text = "invalid key detected: {}".format(key)
        self.__key_text.set(value=text)

    def __read_options(self):
        """
        Read the config.ini file options and update the appropriate UI fields
        """
        # Update values
        settings = Settings()
        config_url = settings.get(Settings.SECTION_SERVER, Settings.OPTION_URL)
        config_token = settings.get(Settings.SECTION_SERVER, Settings.OPTION_TOKEN)
        config_key = settings.get(Settings.SECTION_KEYBIND, Settings.OPTION_KEY)

        self.__set_hotkey(key=config_key)
        self.__token_text.set(config_token)
        self.__url_text.set(config_url)

    @async_handler
    async def save_options(self):
        """
        Save the options to config.ini
        """
        settings = Settings()
        settings.set(section=Settings.SECTION_SERVER, option=Settings.OPTION_URL, value=self.__url_text.get())
        settings.set(section=Settings.SECTION_SERVER, option=Settings.OPTION_TOKEN, value=self.__token_text.get())
        settings.set(section=Settings.SECTION_KEYBIND, option=Settings.OPTION_KEY, value=self.__key_text.get())
        settings.save()

    @async_handler
    async def capture(self):
        """
        "Enable capture" callback. Used to enable or disable the global keypress to take screenshots of Foxhole
        """
        text = self.__capture_text.get()
        if text == "Enable capture":
            # Enable the capture if the hotkey is set
            if self.__hotkey:
                self.__capture_text.set('Capturing enabled')
                self.__thread = keyboard.GlobalHotKeys({self.__hotkey: lambda: run(self.screenshot())})
                self.__thread.start()
        else:
            self.__capture_text.set('Enable capture')
            if self.__thread:
                self.__thread.stop()
                self.__thread = None

    async def screenshot(self):
        img = await self.__screenshot()
        if not img:
            return
        
        import time
        ocr = OCR()
        stockpile = await ocr.extract_stockpile_from_buffer(img)
        end = time.time()
        print("Scanned image in {}".format(end - start))
        start = end
        if not stockpile:
            return { "message": "No stockpile found in the image" }

        hermes = HermesConnector()
        api_key = self.__token_text.get()

        # Open a new thread to avoid blocking the execution
        return hermes.send_stockpile_to_hermes(stockpile=stockpile, api_key=api_key)

    async def __screenshot(self):
        """
        Take an screeshot of Foxhole
        """
        try:
            foxhole = pywinctl.getWindowsWithTitle(title="War", condition=pywinctl.Re.STARTSWITH)[0]
        except Exception:
            print("Foxhole is not running")
            return None

        if foxhole.isMinimized:
            print("Foxhole is minimized")
            return None

        if not foxhole.isActive:
            print("Foxhole should be the active window")
            return None

        img = None
        with mss() as sct:
            sct_img = sct.grab(foxhole.getClientFrame())
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            byte_io = BytesIO()
            img.save(byte_io, 'png')
            byte_io.seek(0)
            print("Screenshot taken")

            #to_png(sct_img.rgb, sct_img.size, output="screenshot.png")

        return byte_io
