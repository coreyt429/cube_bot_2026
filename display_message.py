import argparse
import time

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont


def do_nothing() -> None:
    pass


def draw_message(device, font, header: str, messages) -> None:
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((2, 0), header, fill="white", font=font)

        y = 16
        line_height = 10
        for msg in messages:
            draw.text((2, y), msg, fill="white", font=font)
            y += line_height


def main() -> None:
    parser = argparse.ArgumentParser(description="Display a message on the OLED.")
    parser.add_argument("header", help="Header text")
    parser.add_argument("messages", nargs="*", help="Message lines")
    args = parser.parse_args()

    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial, width=128, height=64)
    device.cleanup = do_nothing
    font = ImageFont.load_default()

    draw_message(device, font, args.header, args.messages)
    time.sleep(0.1)


if __name__ == "__main__":
    main()
