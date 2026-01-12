import gpiod
from gpiod.line import Direction, Edge
import time

buttons = {
    "up": 22,
    "down": 27,
    "select": 17,
}

line_to_button = {v: k for k, v in buttons.items()}

CHIP = "/dev/gpiochip0"
LINES = list(line_to_button.keys())

settings = gpiod.LineSettings(
    direction=Direction.INPUT,
    edge_detection=Edge.BOTH,
    # If your libgpiod build supports it, uncomment to use internal pull-ups:
    # bias=gpiod.line.Bias.PULL_UP,
)

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

# OLED setup
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, width=128, height=64)
font = ImageFont.load_default()

last_button = "(none)"
last_edge = ""
last_ts_ns = 0

with gpiod.request_lines(
    CHIP,
    consumer="cubebot",
    config={line: settings for line in LINES},
) as req:
    print(f"Monitoring GPIO lines: {LINES} (edge=both). Ctrl-C to stop.")

    next_draw = 0.0
    draw_interval = 0.2

    while True:
        now = time.monotonic()

        # Wait briefly for edge events so we can also refresh the OLED.
        # If no event arrives within the timeout, we still update the display.
        if req.wait_edge_events(timeout=0.05):
            for ev in req.read_edge_events():
                btn = line_to_button.get(ev.line_offset, f"GPIO{ev.line_offset}")
                edge = "PRESS" if ev.event_type == Edge.FALLING_EDGE else "RELEASE"

                last_button = btn
                last_edge = edge
                last_ts_ns = ev.timestamp_ns

                print(f"{btn} {edge} @ {ev.timestamp_ns}ns")

        # Throttle OLED refresh rate
        if now >= next_draw:
            next_draw = now + draw_interval

            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="white", fill="black")
                draw.text((4, 4), "CubeBot OLED", fill="white", font=font)
                draw.text((4, 16), "I2C addr: 0x3C", fill="white", font=font)
                draw.text((4, 28), time.strftime("%H:%M:%S"), fill="white", font=font)
                draw.text((4, 40), f"Last: {last_button}", fill="white", font=font)
                if last_edge:
                    draw.text((4, 52), f"{last_edge} {last_ts_ns}ns", fill="white", font=font)