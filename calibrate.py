"""
Script to calibrate CubeBot servos.
"""

import sys
import termios
import tty
import signal
from typing import Tuple, Optional
import logging

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align

from cube_bot import CubeBot
from maestro import Servo
from arm import Arm

logging.basicConfig(level=logging.INFO, filename="calibrate.log")
logger = logging.getLogger("calibrate")
logger.setLevel(logging.DEBUG)

# Keys: l/r to select arm. Arrow keys:
#  - UP/DOWN    => adjust OPEN servo QUS (+/-)
#  - LEFT/RIGHT => adjust ROTATE servo QUS (-/+)
# Other keys: s = save config, q = quit, [ / ] = step -/+

ARM_KEYS = ["l", "r"]

# Rotation angle buckets (degrees) selectable via number keys
ROT_BUCKET_KEYS = {
    "0": "0",
    "9": "90",
    "1": "180",
    "2": "270",
}

IN_OUT_KEYS = {
    "o": "open",
    "c": "close",
}

# Key codes for arrows
KEY_UP = "KEY_UP"
KEY_DOWN = "KEY_DOWN"
KEY_LEFT = "KEY_LEFT"
KEY_RIGHT = "KEY_RIGHT"

MOVEMENTS = {
    KEY_UP: {"servo_key": "open", "direction": -1},
    KEY_DOWN: {"servo_key": "open", "direction": +1},
    KEY_LEFT: {"servo_key": "rotate", "direction": +1},
    KEY_RIGHT: {"servo_key": "rotate", "direction": -1},
}


def read_key() -> str:
    """Read a single keypress (including arrows) in raw mode and return a token.
    Returns plain characters for normal keys (e.g., 'q', '[', ']').
    Returns KEY_* tokens for arrow keys.
    """
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch1 = sys.stdin.read(1)
        if ch1 == "\x1b":
            # Escape sequence
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                if ch3 == "A":
                    return KEY_UP
                if ch3 == "B":
                    return KEY_DOWN
                if ch3 == "C":
                    return KEY_RIGHT
                if ch3 == "D":
                    return KEY_LEFT
            return "\x1b"
        return ch1
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# Helpers to access arm and config paths


def get_arm(bot: CubeBot, arm_key: str):
    """
    Return the arm object for the given key if present on the CubeBot, else None.
    """
    if hasattr(bot, "arms") and arm_key in getattr(bot, "arms"):
        return bot.arms[arm_key]
    return None


def ensurecfg_qus_path(bot: CubeBot, arm_key: str):
    """
    Ensure and return the configuration dict for `bot.cfg['arms'][arm_key]['qus']`.
    Creates intermediate dicts as needed.
    """
    if not hasattr(bot, "cfg") or bot.cfg is None:
        bot.cfg = {}
    arms = bot.cfg.setdefault("arms", {})
    armcfg = arms.setdefault(arm_key, {})
    quscfg = armcfg.setdefault("qus", {})
    return quscfg


def qus_limits(servo) -> Tuple[int, int]:
    """Return (min_qus, max_qus) derived from servo.limits which are in microseconds."""
    try:
        lo_us, hi_us, _ = servo.limits
    except (AttributeError, ValueError, TypeError, IndexError):
        # Fallback sane-ish defaults if limits missing (500–2500 µs)
        lo_us, hi_us = 500, 2500
    return int(lo_us * 4), int(hi_us * 4)


def clamp(v: int, lo: int, hi: int) -> int:
    """
    Clamp integer `v` to the inclusive range [`lo`, `hi`].
    """
    return max(lo, min(hi, v))


def resolve_servos(bot: CubeBot, arm_key: str) -> dict:
    """
    Try to find the open and rotate servos for the given arm key.
    We support a few layouts to be resilient to internal structure differences.
    Returns (servos['open'], servos['rotate']).
    """
    logger.debug("Resolving servos for arm: %s, bot: %s", arm_key, bot)
    logger.debug("Bot arms: %s", getattr(bot, "arms", None))
    logger.debug(
        "Bot arm %s servos: %s", arm_key, getattr(bot.arms[arm_key], "servos", None)
    )
    if not (hasattr(bot, "arms") and arm_key in getattr(bot, "arms")):
        raise ValueError(f"Arm '{arm_key}' not found on bot")
    return bot.arms[arm_key].servos


def render_table(bot: CubeBot, current_arm: str):
    """Render data table"""
    table = Table(
        title="Arms",
        title_style="bold",
        expand=False,
        collapse_padding=True,
        pad_edge=False,
    )

    table.add_column("Arm")
    table.add_column("OPEN qus")
    table.add_column("OPEN deg")
    table.add_column("Saved open")
    table.add_column("Saved close")
    table.add_column("State")
    table.add_column("ROT qus")
    table.add_column("ROT deg")
    table.add_column("Saved 0")
    table.add_column("Saved 90")
    table.add_column("Saved 180")
    table.add_column("Saved 270")

    for arm_key in ARM_KEYS:
        try:
            servos = resolve_servos(bot, arm_key)
        except (IndexError, KeyError, AttributeError, TypeError) as e:
            table.add_row(
                arm_key.upper(),
                f"ERR: {e}",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
            )
            continue

        marker = "➡ " if arm_key == current_arm else "  "

        saved = ensurecfg_qus_path(bot, arm_key)

        try:
            ext_qus = int(getattr(servos["open"], "qus", 0) or 0)
        except (ValueError, TypeError, AttributeError):
            ext_qus = 0
        try:
            ext_deg = float(getattr(servos["open"], "deg", 0.0) or 0.0)
        except (ValueError, TypeError, AttributeError):
            ext_deg = 0.0

        try:
            rot_qus = int(getattr(servos["rotate"], "qus", 0) or 0)
        except (ValueError, TypeError, AttributeError):
            rot_qus = 0
        try:
            rot_deg = float(getattr(servos["rotate"], "deg", 0.0) or 0.0)
        except (ValueError, TypeError, AttributeError):
            rot_deg = 0.0

        table.add_row(
            f"{marker}{arm_key.upper()}",
            f"{ext_qus}",
            f"{ext_deg:0.2f}",
            f"{saved.get('open') if saved.get('open') is not None else '-'}",
            f"{saved.get('closed') if saved.get('closed') is not None else '-'}",
            saved.get("state", ""),
            f"{rot_qus}",
            f"{rot_deg:0.2f}",
            f"{saved.get('0') if saved.get('0') is not None else '-'}",
            f"{saved.get('90') if saved.get('90') is not None else '-'}",
            f"{saved.get('180') if saved.get('180') is not None else '-'}",
            f"{saved.get('270') if saved.get('270') is not None else '-'}",
        )
    return table


def render_ui(bot: CubeBot, state: dict):
    """
    Build and return a Rich renderable showing per-arm live values, saved targets,
    and footer state. `rot_bucket` is one of "0","90","180","270".
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=1),
    )

    title = Text(
        "CubeBot Calibration\narrows adjust QUS (open: ↑/↓, rotate: ←/→)\n"
        "[l/r] select arm   [o]=mark open  [c]=mark closed \n"
        "[0/9/1/2] rot bucket (0°,90°,180°,270°) — selecting moves to saved angle\n"
        "[s] save   [q] quit   [ [ ] step ]",
        style="bold",
        no_wrap=False,
        # overflow="ellipsis",
    )
    layout["header"].update(Align.center(title, vertical="middle"))

    table = render_table(bot, state["current_arm"])
    layout["body"].update(Panel(table, border_style="cyan"))

    footer = Text(
        (
            f"Current arm: {state['current_arm'].upper()}   Step: {state['step_qus']} qus"
            f"   Rot bucket: {state['rot_bucket']}"
        ),
        style="dim",
        no_wrap=True,
        overflow="ellipsis",
    )
    layout["footer"].update(Align.center(footer, vertical="middle"))

    return layout


def calc_default_qus(servo: Servo) -> int:
    """
    Calculate the default QUS for a servo based on its current state.
    """
    lo_us, hi_us, _ = servo.limits
    deg = float(getattr(servo, "deg", 0.0) or 0.0)
    span = float(getattr(servo, "span_deg", 180.0) or 180.0)
    us = lo_us + (hi_us - lo_us) * (deg / span)
    return int(us * 4)


def adjust_servo_qus(
    arm: Arm,
    role: str,
    servo: Servo,
    delta_qus: int = 8,
    rot_bucket: Optional[str] = None,
):
    """
    Increment a servo’s quarter‑microsecond target by `delta_qus`, send it, and
    persist to `bot.cfg`:
    - role "open": write current QUS into ['open'|'closed'] based on state
    - role "rotate": write current QUS into the selected rotation bucket
    calibrate.py:290:0: R0913: Too many arguments (6/5) (too-many-arguments)
    calibrate.py:290:0: R0917: Too many positional arguments (6/5) (too-many-positional-arguments)
    calibrate.py:290:0: R0914: Too many local variables (20/15) (too-many-locals)
    """
    logger.debug("Adjusting servo %s (role: %s) by %d QUS", servo, role, delta_qus)
    # Determine current QUS (fallback from deg if necessary)
    qus: Optional[int] = getattr(servo, "qus", None)
    if qus is None:
        # Try to derive from degrees if possible
        try:
            qus = calc_default_qus(servo)
        except (TypeError, ValueError, AttributeError):
            qus = 6000  # neutral-ish default

    new_qus = clamp(int(qus) + int(delta_qus), *qus_limits(servo))

    logger.info("Setting servo %s (role: %s) to %d QUS", servo, role, new_qus)
    # Use the Servo.set_qus API added earlier so deg stays in sync
    if hasattr(servo, "set_qus"):
        servo.set_qus(new_qus)
    else:
        # Fallback: call maestro directly if available
        if hasattr(servo, "maestro") and hasattr(servo.maestro, "set_target_qus"):
            servo.maestro.set_target_qus(channel=servo.channel, target_qus=new_qus)
        setattr(servo, "qus", new_qus)

    # Persist live edits into config for the open servo based on current state
    if role == "open":
        saved = ensurecfg_qus_path(arm.parent, arm.cfg.key)
        state_key = saved.get("state", "closed")
        if state_key in ("open", "closed"):
            try:
                curr_qus_persist = int(getattr(servo, "qus", 0) or 0)
            except (ValueError, TypeError, AttributeError):
                curr_qus_persist = 0
            saved[state_key] = curr_qus_persist

    if role == "rotate":
        saved = ensurecfg_qus_path(arm.parent, arm.cfg.key)
        try:
            curr_rot_qus = int(getattr(servo, "qus", 0) or 0)
        except (ValueError, TypeError, AttributeError):
            curr_rot_qus = 0
        bucket = rot_bucket or "180"
        saved[bucket] = curr_rot_qus


def do_open_or_close(bot: CubeBot, arm_key: str, action: str):
    """
    action in {"open", "close"}. Calls arm methods if present;
    always records the current open servo QUS into
    cfg['arms'][arm]['qus'][action] and sets 'state'.
    """
    servos = resolve_servos(bot, arm_key)
    arm = get_arm(bot, arm_key)
    logger.debug("Doing action '%s' on arm '%s'", action, arm_key)
    logger.debug("Arm object: %s", arm)
    for k, servo in servos.items():
        logger.debug("Servo: %s %s", k, servo)

    # Try method on arm first
    try:
        if arm is not None and hasattr(arm, action):
            getattr(arm, action)()
    except (TypeError, AttributeError):
        pass

    # Record current open servo qus into config and mark state
    try:
        curr_qus = int(getattr(servos["open"], "qus", 0) or 0)
    except (ValueError, TypeError, AttributeError):
        curr_qus = 0
    saved = ensurecfg_qus_path(bot, arm_key)
    if "state" not in saved:
        saved["state"] = "closed"
    key = "open" if action == "open" else "closed"
    saved[key] = curr_qus
    saved["state"] = key


def apply_saved(bot: CubeBot, arm_key: str, action: str):
    """
    Apply the saved open target for `action` ("open" or "close") to the arm’s
    open servo, if present in config.
    """
    servos = resolve_servos(bot, arm_key)
    saved = ensurecfg_qus_path(bot, arm_key)
    key = "open" if action == "open" else "closed"
    target_qus = saved.get(key)
    if target_qus is not None and hasattr(servos["open"], "set_qus"):
        try:
            servos["open"].set_qus(int(target_qus))
        except (ValueError, TypeError, AttributeError):
            pass


def apply_saved_rotate(bot: CubeBot, arm_key: str, bucket: str):
    """Apply saved rotate QUS for the given bucket ('0','90','180','270'), if present."""
    try:
        servos = resolve_servos(bot, arm_key)
    except (ValueError, TypeError, AttributeError):
        return
    saved = ensurecfg_qus_path(bot, arm_key)
    target_qus = saved.get(bucket)
    if target_qus is not None:
        if hasattr(servos["rotate"], "set_qus"):
            try:
                servos["rotate"].set_qus(int(target_qus))
            except (ValueError, TypeError, AttributeError):
                pass
        elif hasattr(servos["rotate"], "maestro") and hasattr(
            servos["rotate"].maestro, "set_target_qus"
        ):
            try:
                servos["rotate"].maestro.set_target_qus(
                    channel=servos["rotate"].channel, target_qus=int(target_qus)
                )
            except (ValueError, TypeError, AttributeError):
                pass


def _sigint_handler_factory(bot: CubeBot):
    def _handler(signum, frame):
        print(signum, frame)
        try:
            for arm in bot.arms.values():
                arm.open(wait=True)
        finally:
            print("\nInterrupted. Opened claws.")
            sys.exit(0)

    return _handler


def handle_key(bot: CubeBot, state: dict, key: str) -> bool:
    """function to handle captured keypresses"""
    if key == "q":
        return False
    if key == "s":
        bot.save_config()
    elif key in ("l", "r"):
        state["current_arm"] = key
    elif key == "[":
        state["step_qus"] = max(1, state["step_qus"] // 2)
    elif key == "]":
        state["step_qus"] = min(1024, state["step_qus"] * 2)
    elif key in ("0", "9", "1", "2"):
        state["rot_bucket"] = ROT_BUCKET_KEYS.get(key, state["rot_bucket"])
        apply_saved_rotate(bot, state["current_arm"], state["rot_bucket"])
    elif key in ["o", "c"]:
        logger.debug(
            "Doing open/close action '%s' on arm '%s'",
            key,
            state["current_arm"],
        )
        do_open_or_close(bot, state["current_arm"], IN_OUT_KEYS.get(key))
    else:
        servos = resolve_servos(bot, state["current_arm"])
        if not servos:
            return True
        if key in MOVEMENTS:
            movement = MOVEMENTS[key]
            adjust_servo_qus(
                bot.arms[state["current_arm"]],
                movement["servo_key"],
                servos[movement["servo_key"]],
                movement["direction"] * state["step_qus"],
                rot_bucket=state["rot_bucket"],
            )
    return True


def main():
    """
    Main Logic
    calibrate.py:433:0: R0912: Too many branches (18/12) (too-many-branches)
    calibrate.py:433:0: R0915: Too many statements (51/50) (too-many-statements)
    """
    state = {
        "current_arm": "l",
        "rot_bucket": "90",
        "step_qus": 8,
    }
    console = Console(
        force_terminal=True,  # ensure Rich treats this as an interactive TTY
    )
    bot = CubeBot("calibration")

    # Handle Ctrl+C cleanly
    signal.signal(signal.SIGINT, _sigint_handler_factory(bot))

    for arm in bot.arms.values():
        arm.reset()

    with Live(
        render_ui(bot, state),
        console=console,
        refresh_per_second=4,
        auto_refresh=False,
        screen=True,  # draw in an alternate screen buffer
        transient=True,  # leave the terminal clean on exit;
    ) as live:
        while True:
            if not handle_key(bot, state, read_key()):
                break
            # Update the live view after every key
            live.update(render_ui(bot, state), refresh=True)

    # Try to disengage on normal exit
    try:
        for arm in bot.arms.values():
            arm.open(wait=True)
    except (ValueError, TypeError, AttributeError):
        pass


if __name__ == "__main__":
    main()
