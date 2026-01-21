from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont


class Display():
    def __init__(self, width=128, height=64, i2c_port=1, i2c_address=0x3C):
        serial = i2c(port=i2c_port, address=i2c_address)
        self.device = ssd1306(serial, width=width, height=height)
        self.font = ImageFont.load_default()
        self.device.cleanup = self.do_nothing

    def do_nothing(self) -> None:
        pass

    def draw_message(self, header: str, messages: list[str]) -> None:
        with canvas(self.device) as draw:
            draw.rectangle(self.device.bounding_box, outline="white", fill="black")
            draw.text((2, 0), header, fill="white", font=self.font)

            y = 16
            line_height = 10
            for msg in messages:
                draw.text((2, y), msg, fill="white", font=self.font)
                y += line_height
    
def test() -> None:
    test_message = [
        "Line 1: Hello, World!",
        "Line 2: OLED Display",
        "Line 3: Testing 1, 2, 3",
        "Line 4: Goodbye!",
    ]
    display = Display()
    display.draw_message("Display Test", test_message)


if __name__ == "__main__":
    test()
