import logging
import signal
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import gpiod
from gpiod.line import Direction, Edge
from luma.core.render import canvas

logger = logging.getLogger(__name__)

DEFAULT_BUTTONS = {
    "up": 22,
    "down": 27,
    "select": 17,
}


def _is_falling_event(ev) -> bool:
    """Return True if this edge event represents a falling edge."""
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

    name = getattr(et, "name", "")
    if isinstance(name, str) and name:
        return "FALL" in name.upper()

    return "FALL" in str(et).upper()


def _draw_message(display, header: str, messages: List[str]) -> None:
    if hasattr(display, "draw_message"):
        display.draw_message(header, messages)
        return
    device = getattr(display, "device", None)
    font = getattr(display, "font", None)
    if device is None or font is None:
        raise ValueError("display must provide draw_message() or device/font")
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((2, 0), header, fill="white", font=font)
        y = 16
        line_height = 10
        for msg in messages:
            draw.text((2, y), msg, fill="white", font=font)
            y += line_height


@dataclass
class MenuItem:
    label: str
    children: Optional[List["MenuItem"]] = None
    action: Optional[Callable[..., None]] = None
    parameters: Optional[List[object]] = None


@dataclass
class ButtonEvent:
    btn: str
    edge: str  # "PRESS" or "RELEASE"
    timestamp_ns: int
    line_offset: int


class Buttons:
    """Owns the gpiod line request and exposes button events to whoever is active."""

    def __init__(
        self,
        button_pins: dict,
        chip: str = "/dev/gpiochip0",
        debounce_ns: int = 200_000_000,
        consumer: str = "cubebot",
    ) -> None:
        self.button_pins = dict(button_pins)
        self.line_to_button = {v: k for k, v in self.button_pins.items()}
        self.chip = chip
        self.debounce_ns = debounce_ns
        self.consumer = consumer

        self._req = None
        self._last_press_ns = {name: 0 for name in self.button_pins}

        self.settings = gpiod.LineSettings(
            direction=Direction.INPUT,
            edge_detection=Edge.BOTH,
            bias=gpiod.line.Bias.PULL_UP,
        )

    def open(self):
        lines = list(self.line_to_button.keys())
        self._req = gpiod.request_lines(
            self.chip,
            consumer=self.consumer,
            config={line: self.settings for line in lines},
        )
        return self

    def close(self) -> None:
        if self._req is not None:
            try:
                self._req.close()
            finally:
                self._req = None

    def __enter__(self):
        return self.open()

    def __exit__(self, _exc_type, _exc, _tb):
        self.close()

    def wait(self, timeout: float = 0.05) -> bool:
        if self._req is None:
            raise RuntimeError("Buttons not opened; use as a context manager")
        return self._req.wait_edge_events(timeout=timeout)

    def read_events(self) -> List[ButtonEvent]:
        if self._req is None:
            raise RuntimeError("Buttons not opened; use as a context manager")

        out: List[ButtonEvent] = []
        for ev in self._req.read_edge_events():
            btn = self.line_to_button.get(ev.line_offset, f"GPIO{ev.line_offset}")
            edge = "PRESS" if _is_falling_event(ev) else "RELEASE"

            # Debounce presses only
            if edge == "PRESS":
                prev_ns = self._last_press_ns.get(btn, 0)
                if ev.timestamp_ns - prev_ns < self.debounce_ns:
                    logger.debug("Debounce press ignored: %s", btn)
                    continue
                self._last_press_ns[btn] = ev.timestamp_ns

            out.append(
                ButtonEvent(
                    btn=btn,
                    edge=edge,
                    timestamp_ns=ev.timestamp_ns,
                    line_offset=ev.line_offset,
                )
            )
        return out


class Menu:
    def __init__(
        self,
        display,
        menu_definition,
        title: str = "CubeBot",
        buttons: Optional[dict] = None,
        chip: str = "/dev/gpiochip0",
        debounce_ns: int = 200_000_000,
        draw_interval: float = 0.2,
    ) -> None:
        self.display = display
        self.title = title
        self.button_pins = buttons or dict(DEFAULT_BUTTONS)
        self.line_to_button = {v: k for k, v in self.button_pins.items()}
        self.chip = chip
        self.debounce_ns = debounce_ns
        self.draw_interval = draw_interval

        self.root_menu = MenuItem(label=self.title, children=self._parse_menu(menu_definition))
        self.menu_stack = [self.root_menu]
        self.menu_index = 0
        self.menu_message = ""
        self.menu_has_interacted = True
        self.keep_running = True

        self.last_button = "(none)"
        self.last_edge = ""
        self.last_ts_ns = 0
        self.last_press_ns = {name: 0 for name in self.button_pins}

    def _parse_menu(self, definition) -> List[MenuItem]:
        items: List[MenuItem] = []
        if isinstance(definition, list):
            for entry in definition:
                if isinstance(entry, dict):
                    items.extend(self._parse_menu(entry))
            return items
        if not isinstance(definition, dict):
            return items

        if "action" in definition:
            action = definition.get("action")
            params = definition.get("parameters", [])
            if params is None:
                params = []
            return [MenuItem(label="(action)", action=action, parameters=list(params))]

        for label, node in definition.items():
            if isinstance(node, dict) and "action" in node:
                action = node.get("action")
                params = node.get("parameters", [])
                if params is None:
                    params = []
                items.append(MenuItem(label=label, action=action, parameters=list(params)))
            else:
                children = self._parse_menu(node)
                items.append(MenuItem(label=label, children=children))
        return items

    def _menu_path(self) -> str:
        if len(self.menu_stack) <= 1:
            return self.title
        return " > ".join(item.label for item in self.menu_stack[1:])

    def _menu_items(self, menu: MenuItem) -> List[MenuItem]:
        items = menu.children or []
        if menu is self.root_menu:
            return items
        return [MenuItem(label=".. (back)")] + items

    def _is_back_item(self, item: MenuItem) -> bool:
        return item.label.startswith("..")

    def _handle_sigint(self, _signum, _frame) -> None:
        self.keep_running = False

    def _execute_action(self, item: MenuItem) -> None:
        if not item.action:
            return
        params = item.parameters or []
        logger.info("Menu action: %s params=%s", item.label, params)
        try:
            item.action(self.display, self.buttons_service, *params)
        except Exception:
            logger.exception("Menu action failed: %s", item.label)
            self.menu_message = f"Failed: {item.label}"
        else:
            self.menu_message = f"Ran: {item.label}"

    def _handle_press(self, btn: str, ev_ts_ns: int) -> None:
        prev_ns = self.last_press_ns.get(btn, 0)
        if ev_ts_ns - prev_ns < self.debounce_ns:
            logger.debug("Debounce press ignored: %s", btn)
            return
        self.last_press_ns[btn] = ev_ts_ns

        current_menu = self.menu_stack[-1]
        items = self._menu_items(current_menu)

        if btn == "up":
            self.menu_index = (self.menu_index - 1) % max(1, len(items))
            self.menu_has_interacted = True
        elif btn == "down":
            self.menu_index = (self.menu_index + 1) % max(1, len(items))
            self.menu_has_interacted = True
        elif btn == "select" and items:
            self.menu_has_interacted = True
            selected = items[self.menu_index]
            if self._is_back_item(selected):
                if len(self.menu_stack) > 1:
                    self.menu_stack.pop()
                    self.menu_index = 0
                    self.menu_message = "Back"
            elif selected.children:
                self.menu_stack.append(selected)
                self.menu_index = 0
                self.menu_message = selected.label
            else:
                self.menu_message = f"Selected {selected.label}"
                self._execute_action(selected)

    def _draw(self) -> None:
        device = getattr(self.display, "device", None)
        font = getattr(self.display, "font", None)
        if device is None or font is None:
            raise ValueError("display must provide device/font for menu rendering")

        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((2, 0), self._menu_path(), fill="white", font=font)

            items = self._menu_items(self.menu_stack[-1])
            line_height = 10
            menu_top_y = 16
            footer_height = 10
            available_height = device.height - menu_top_y - footer_height
            items_per_page = max(1, available_height // line_height)
            page = self.menu_index // items_per_page
            start = page * items_per_page
            end = min(len(items), start + items_per_page)

            y = menu_top_y
            for idx in range(start, end):
                item = items[idx]
                is_selected = idx == self.menu_index
                if is_selected and self.menu_has_interacted:
                    draw.rectangle((0, y + 1, device.width - 1, y + 10), fill="white")
                    draw.text((2, y), item.label, fill="black", font=font)
                else:
                    draw.text((2, y), item.label, fill="white", font=font)
                y += line_height

            footer = self.menu_message or f"{self.last_button} {self.last_edge}".strip()
            if footer:
                draw.text((2, device.height - 10), footer[:18], fill="white", font=font)

    def run(self) -> None:
        with Buttons(
            button_pins=self.button_pins,
            chip=self.chip,
            debounce_ns=self.debounce_ns,
            consumer="cubebot",
        ) as buttons:
            # Expose to actions while they are active
            self.buttons_service = buttons

            lines = list(self.line_to_button.keys())
            logger.info(
                "Monitoring GPIO lines: %s (edge=both). Ctrl-C to stop.", lines
            )

            signal.signal(signal.SIGINT, self._handle_sigint)

            next_draw = 0.0
            while self.keep_running:
                now = time.monotonic()

                if buttons.wait(timeout=0.05):
                    for bev in buttons.read_events():
                        self.last_button = bev.btn
                        self.last_edge = bev.edge
                        self.last_ts_ns = bev.timestamp_ns

                        if bev.edge == "PRESS":
                            self._handle_press(bev.btn, bev.timestamp_ns)

                if now >= next_draw:
                    next_draw = now + self.draw_interval
                    self._draw()

        _draw_message(self.display, self.title, ["Stopped", time.strftime("%H:%M:%S")])


def count_down(display, buttons: Buttons, seconds: int) -> None:
    for remaining in range(int(seconds), -1, -1):
        _draw_message(display, "Countdown", [f"{remaining}..."])
        time.sleep(1)


def interactive_counter(display, buttons: Buttons) -> None:
    count = 0
    _draw_message(display, "Interactive", [str(count), "Up:+  Down:-", "Select: exit"])

    while True:
        if buttons.wait(timeout=0.05):
            for ev in buttons.read_events():
                if ev.edge != "PRESS":
                    continue
                if ev.btn == "up":
                    count += 1
                elif ev.btn == "down":
                    count -= 1
                elif ev.btn == "select":
                    _draw_message(display, "Interactive", ["Exit"])
                    return

                _draw_message(display, "Interactive", [str(count), "Up:+  Down:-", "Select: exit"])


def test_function() -> None:
    from display import Display

    menu_definition = [
        {
            "item 1": {
                "action": count_down,
                "parameters": [5],
            },
            "interactive": {
                "action": interactive_counter,
                "parameters": [],
            },
        },
        {
            "item 2": {
                "sub item 1": {
                    "action": count_down,
                    "parameters": [10],
                },
                "sub item 2": {
                    "action": count_down,
                    "parameters": [20],
                },
            }
        },
    ]

    display = Display()
    menu = Menu(display=display, menu_definition=menu_definition, title="CubeBot")
    menu.run()


if __name__ == "__main__":
    test_function()
