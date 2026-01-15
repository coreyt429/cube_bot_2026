import gpiod
from gpiod.line import Direction, Edge
import time
from dataclasses import dataclass
from typing import List, Optional
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
import logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
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

# Helper to robustly detect falling edge events across gpiod versions.
def _is_falling_event(ev) -> bool:
    """Return True if this edge event represents a falling edge.

    libgpiod's Python bindings have had a few enum naming variants across versions,
    so we detect falling edges defensively.
    """
    et = getattr(ev, "event_type", None)

    # Newer variants: gpiod.LineEvent.Type.FALLING_EDGE / RISING_EDGE
    try:
        le = getattr(gpiod, "LineEvent", None)
        t = getattr(le, "Type", None) if le else None
        if t is not None:
            if hasattr(t, "FALLING_EDGE") and et == t.FALLING_EDGE:
                return True
            if hasattr(t, "FALLING") and et == t.FALLING:
                return True
    except Exception:
        pass

    # Fallback: enum name or string contains "FALL"
    name = getattr(et, "name", "")
    if isinstance(name, str) and name:
        return "FALL" in name.upper()

    return "FALL" in str(et).upper()



# OLED setup
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, width=128, height=64)
font = ImageFont.load_default()

@dataclass
class MenuItem:
    label: str
    children: Optional[List["MenuItem"]] = None


def _menu(label: str, children: Optional[List["MenuItem"]] = None) -> MenuItem:
    return MenuItem(label=label, children=children)


root_menu = _menu(
    "CubeBot",
    children=[
        _menu("load"),
        _menu("status"),
        _menu(
            "calibrate",
            children=[
                _menu(
                    "left",
                    children=[
                        _menu("rotate"),
                        _menu("gripper"),
                    ],
                ),
                _menu(
                    "right",
                    children=[
                        _menu("rotate"),
                        _menu("gripper"),
                    ],
                ),
            ],
        ),
        _menu("test1"),
        _menu("test2"),
        _menu("test3"),
        _menu("test4"),
        _menu("test5"),
    ],
)


def _menu_path(stack: List[MenuItem]) -> str:
    if len(stack) <= 1:
        return "CubeBot"
    return " > ".join(item.label for item in stack[1:])


def _menu_items(menu: MenuItem) -> List[MenuItem]:
    items = menu.children or []
    if menu is root_menu:
        return items
    return [_menu(".. (back)")] + items


def _is_back_item(item: MenuItem) -> bool:
    return item.label.startswith("..")


menu_stack = [root_menu]
menu_index = 0
menu_message = ""
menu_has_interacted = True

last_button = "(none)"
last_edge = ""
last_ts_ns = 0
last_press_ns = {name: 0 for name in buttons}
DEBOUNCE_NS = 200_000_000  # 200ms

with gpiod.request_lines(
    CHIP,
    consumer="cubebot",
    config={line: settings for line in LINES},
) as req:
    logger.info("Monitoring GPIO lines: %s (edge=both). Ctrl-C to stop.", LINES)

    next_draw = 0.0
    draw_interval = 0.2

    while True:
        now = time.monotonic()

        # Wait briefly for edge events so we can also refresh the OLED.
        # If no event arrives within the timeout, we still update the display.
        if req.wait_edge_events(timeout=0.05):
            for ev in req.read_edge_events():
                btn = line_to_button.get(ev.line_offset, f"GPIO{ev.line_offset}")
                edge = "PRESS" if _is_falling_event(ev) else "RELEASE"

                last_button = btn
                last_edge = edge
                last_ts_ns = ev.timestamp_ns

                logger.info("%s %s @ %sns", btn, edge, ev.timestamp_ns)

                if edge == "PRESS":
                    prev_ns = last_press_ns.get(btn, 0)
                    if ev.timestamp_ns - prev_ns < DEBOUNCE_NS:
                        logger.debug("Debounce press ignored: %s", btn)
                        continue
                    last_press_ns[btn] = ev.timestamp_ns

                    current_menu = menu_stack[-1]
                    items = _menu_items(current_menu)
                    if btn == "up":
                        menu_index = (menu_index - 1) % max(1, len(items))
                        menu_has_interacted = True
                        logger.info(
                            "Menu move up: index=%s label=%s",
                            menu_index,
                            items[menu_index].label if items else "",
                        )
                    elif btn == "down":
                        menu_index = (menu_index + 1) % max(1, len(items))
                        menu_has_interacted = True
                        logger.info(
                            "Menu move down: index=%s label=%s",
                            menu_index,
                            items[menu_index].label if items else "",
                        )
                    elif btn == "select" and items:
                        menu_has_interacted = True
                        selected = items[menu_index]
                        if _is_back_item(selected):
                            if len(menu_stack) > 1:
                                menu_stack.pop()
                                menu_index = 0
                                menu_message = "Back"
                                logger.info(
                                    "Menu back: path=%s", _menu_path(menu_stack)
                                )
                        elif selected.children:
                            menu_stack.append(selected)
                            menu_index = 0
                            menu_message = selected.label
                            logger.info(
                                "Menu enter: %s path=%s",
                                selected.label,
                                _menu_path(menu_stack),
                            )
                        else:
                            menu_message = f"Selected {selected.label}"
                            logger.info(
                                "Menu select: %s path=%s",
                                selected.label,
                                _menu_path(menu_stack),
                            )

        # Throttle OLED refresh rate
        if now >= next_draw:
            next_draw = now + draw_interval

            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="white", fill="black")
                draw.text((2, 0), _menu_path(menu_stack), fill="white", font=font)

                items = _menu_items(menu_stack[-1])
                line_height = 10
                menu_top_y = 16
                footer_height = 10
                available_height = device.height - menu_top_y - footer_height
                items_per_page = max(1, available_height // line_height)
                page = menu_index // items_per_page
                start = page * items_per_page
                end = min(len(items), start + items_per_page)

                y = menu_top_y
                for idx in range(start, end):
                    item = items[idx]
                    is_selected = idx == menu_index
                    if is_selected and menu_has_interacted:
                        draw.rectangle((0, y + 1, device.width - 1, y + 10), fill="white")
                        draw.text((2, y), item.label, fill="black", font=font)
                    else:
                        draw.text((2, y), item.label, fill="white", font=font)
                    y += line_height

                footer = menu_message or f"{last_button} {last_edge}".strip()
                if footer:
                    draw.text((2, device.height - 10), footer[:18], fill="white", font=font)
