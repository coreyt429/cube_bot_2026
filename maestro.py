"""
Module for controlling the Maestro servo controller
"""

# maestro.py
import time
import logging
from typing import Optional
from dataclasses import dataclass
import serial

logger = logging.getLogger("maestro")


def us_to_qus(us: int) -> int:
    """
    Convert microseconds to quarter-microseconds.
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("us_to_qus called with us=%d", us)
    return int(us) * 4


# --- Servo config dataclass ---
@dataclass
class ServoConfig:
    """Configuration for a servo motor."""

    limits: Optional[list[int]] = None
    speed: int = 75
    accel: int = 0
    initial_deg: Optional[int] = None
    span_deg: int = 270


class Maestro:
    """
    Talk to a Pololu Maestro over the USB 'Command Port' using the Compact Protocol.
    Targets are in quarter-microseconds (e.g., 1500 µs => 6000).
    """

    def __init__(self, port: str, baud: int = 9600, timeout: float = 0.1):
        logger.debug(
            "Maestro.__init__(port=%s, baud=%s, timeout=%s)", port, baud, timeout
        )
        # For USB Command Port, the baud setting is ignored but must be valid.
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)

    def close(self):
        """
        Close the serial connection.
        """
        logger.debug("Maestro.close called")
        self.ser.close()

    # ---- Core commands (Compact Protocol) ----
    def set_target_qus(self, channel: int, target_qus: int):
        """
        Set servo pulse. Example: 1500µs -> 1500*4 = 6000.
        """
        logger.debug("set_target_qus(channel=%s, target_qus=%s)", channel, target_qus)
        # Set servo pulse. Example: 1500µs -> 1500*4 = 6000
        if not 0 <= channel <= 23:
            raise ValueError("channel must be 0–23")
        if not 0 <= target_qus <= 16383:
            raise ValueError("target_qus must be 0–16383 (14-bit)")
        cmd = bytes([0x84, channel, target_qus & 0x7F, (target_qus >> 7) & 0x7F])
        self.ser.write(cmd)

    def set_speed(self, channel: int, value: int):
        """Limit speed (0 = unlimited). Units: (quarter-µs)/(10 ms)."""
        logger.debug("set_speed(channel=%s, value=%s)", channel, value)
        cmd = bytes([0x87, channel, value & 0x7F, (value >> 7) & 0x7F])
        self.ser.write(cmd)

    def set_accel(self, channel: int, value: int):
        """Limit acceleration (0 = unlimited). Units: (quarter-µs)/(10 ms)^2."""
        logger.debug("set_accel(channel=%s, value=%s)", channel, value)
        cmd = bytes([0x89, channel, value & 0x7F, (value >> 7) & 0x7F])
        self.ser.write(cmd)

    def get_position(self, channel: int) -> Optional[int]:
        """Returns target in quarter-µs, or None on timeout."""
        logger.debug("get_position(channel=%s)", channel)
        self.ser.write(bytes([0x90, channel]))
        resp = self.ser.read(2)
        if len(resp) != 2:
            return None
        return resp[0] + 256 * resp[1]

    def is_moving(self) -> bool:
        """True if any servo is still moving toward its target."""
        logger.debug("is_moving()")
        self.ser.write(bytes([0x93]))
        resp = self.ser.read(1)
        return bool(resp and resp[0])

    def go_home(self):
        """Send the 'go home' command to the Maestro."""
        logger.debug("go_home()")
        self.ser.write(bytes([0xA2]))

    # Per-channel soft limits (μs). Change per your servo if needed.
    _limits = {}  # ch -> (min_us, max_us, neutral_us)

    def set_limits(
        self,
        channel: int,
        min_us: int = 1100,
        max_us: int = 1900,
        neutral_us: int = 1500,
    ):
        """
        Set per-channel soft limits.
        """
        logger.debug(
            "set_limits(channel=%s, min_us=%s, max_us=%s, neutral_us=%s)",
            channel,
            min_us,
            max_us,
            neutral_us,
        )
        if min_us >= max_us:
            raise ValueError("min_us must be < max_us")
        self._limits[channel] = (min_us, max_us, neutral_us)

    def _clamp_us(self, channel: int, us: int) -> int:
        """
        Clamp a microsecond value to the limits set for a channel.
        """
        logger.debug("_clamp_us(channel=%s, us=%s)", channel, us)
        lo, hi, _ = self._limits.get(channel, (1100, 1900, 1500))
        return max(lo, min(hi, int(us)))

    # Already had set_target_qus; add μs & degrees conveniences:
    def set_us(self, channel: int, us: int):
        """
        Set the target position for a servo channel in microseconds.
        """
        logger.debug("set_us(channel=%s, us=%s)", channel, us)
        us = self._clamp_us(channel, us)
        self.set_target_qus(channel, us_to_qus(us))

    def wait(self):
        """Wait until all servos are no longer moving."""
        logger.debug("wait()")
        while self.is_moving():
            time.sleep(0.15)

    def set_degrees(self, channel: int, deg: float, span_deg: float = 180.0):
        """
        Map degrees to μs within this channel's [min,max].
        span_deg is the mechanical travel you're targeting (commonly ~180).
        """
        logger.debug(
            "set_degrees(channel=%s, deg=%s, span_deg=%s)", channel, deg, span_deg
        )
        lo, hi, _ = self._limits.get(channel, (1100, 1900, 1500))
        # Map 0..span_deg to lo..hi (linear)
        deg = max(0.0, min(span_deg, float(deg)))
        us = lo + (hi - lo) * (deg / span_deg)
        self.set_us(channel, int(us))

    def center(self, channel: int):
        """
        Center the servo on the specified channel.
        """
        logger.debug("center(channel=%s)", channel)
        _, _, neu = self._limits.get(channel, (1100, 1900, 1500))
        self.set_us(channel, neu)

    def tame(self, channel: int, speed: int = 10, accel: int = 5):
        """
        Set the speed and acceleration for a servo channel.
        """
        logger.debug("tame(channel=%s, speed=%s, accel=%s)", channel, speed, accel)
        self.set_speed(channel, speed)
        self.set_accel(channel, accel)


# def gentle_calibrate(
#     m: Maestro, channel: int = 0, start=(500, 2500), step=20, pause=0.15
# ):
#     logger.debug(
#         f"gentle_calibrate called with channel={channel},
# start={start}, step={step}, pause={pause}"
#     )
#     lo, hi = start
#     m.set_limits(channel, lo, hi)
#     m.tame(channel, speed=10, accel=5)
#     m.center(channel)

#     # Nudge lower bound down a bit
#     for trial_lo in range(lo, 900, -step):
#         m.set_limits(channel, trial_lo, hi)
#         m.set_us(channel, trial_lo)
#         time.sleep(pause)
#         # If you hear buzzing/strain, bump back up and stop
#         # (No sensor here—this is human-in-the-loop safety.)
#         # Press Ctrl+C if it sounds angry.
#     m.center(channel)

#     # Nudge upper bound up a bit
#     for trial_hi in range(hi, 2100, step):
#         m.set_limits(channel, m._limits[channel][0], trial_hi)
#         m.set_us(channel, trial_hi)
#         time.sleep(pause)
#     m.center(channel)


# # Helper: sweep on a single channel
# def demo_sweep(port: str, channel: int = 0):
#     logger.debug(f"demo_sweep called with port={port}, channel={channel}")
#     m = Maestro(port)
#     try:
#         # Typical hobby servo range ~1000–2000 µs (adjust for your servo)
#         MIN = 500 * 4  # 1000 µs
#         MID = 1500 * 4  # 1500 µs
#         MAX = 2500 * 4  # 2000 µs

#         m.set_speed(channel, 10)  # gentle
#         m.set_accel(channel, 5)

#         for _ in range(3):
#             for tgt in (MIN, MAX):
#                 m.set_target_qus(channel, tgt)
#                 # Wait until it gets close (or just sleep a fixed time)
#                 time.sleep(5)
#         # park at center
#         m.set_target_qus(channel, MID)
#     finally:
#         m.close()


# def random_moves(m: Maestro, count: int = 10):
#     logger.debug(f"random_moves called with count={count}")
#     for _ in range(count):
#         step = choice(steps)
#         print("Moving to ", step)
#         m.set_degrees(channel=0, deg=step, span_deg=270)
#         time.sleep(0.15)
#         print(m.is_moving())
#         while m.is_moving():
#             time.sleep(0.15)


# def run_pattern(m: Maestro, channel: int = 0):
#     logger.debug(f"run_pattern called with channel={channel}")
#     for deg in [0, 270, 0, 270, 0, 270, 0]:
#         m.set_degrees(channel=channel, deg=deg, span_deg=270)
#         while m.is_moving():
#             time.sleep(0.15)
#         print(f"at {deg}")
#         time.sleep(0.15)


# def find_speed(m: Maestro, channel: int = 0, start: int = 50, step: int = 10):
#     logger.debug(
#         f"find_speed called with channel={channel}, start={start}, step={step}"
#     )
#     current = start
#     last = 0
#     already_tried = set()
#     while current not in already_tried and step > 0:
#         already_tried.add(current)
#         print(f"Testing speed {current}")
#         m.set_speed(channel=channel, value=current)
#         run_pattern(m, channel=channel)
#         print("Did the pattern complete correctly?")
#         response = input("Enter 'y' for yes, 'n' for no: ")
#         if response == "y":
#             print(f"Speed {current} is correct")
#             last = current
#             current += step
#         elif response == "?":
#             print(f"retry {current}")
#         else:
#             print(f"Speed {current} is incorrect")
#             current = last
#             step = int(step / 2)
#             current += step
#     print(f"Finished testing speeds. Last speed was {last}")


class Servo:
    """
    Control a servo motor.
    """

    __slots__ = (
        "_controller",
        "channel",
        "limits",
        "speed",
        "accel",
        "span_deg",
        "qus",
    )

    def __init__(
        self,
        controller: Maestro,
        channel: int,
        config: Optional[ServoConfig] = None,
    ):
        if config is None:
            config = ServoConfig()
        self._controller = controller
        self.channel = channel
        # Avoid mutable default pitfalls; copy user-provided list
        if config.limits is None:
            self.limits = [500, 2500, 1500]
        else:
            self.limits = list(config.limits)
        self.speed = config.speed
        self.accel = config.accel
        self.span_deg = config.span_deg
        # Initialize QUS directly; do not emit a movement during __init__
        if config.initial_deg is not None:
            lo, hi, _ = self.limits
            v = max(0.0, min(self.span_deg, float(config.initial_deg)))
            us = lo + (hi - lo) * (v / self.span_deg)
            self.qus = int(us * 4)
        else:
            neu = self.limits[2]
            self.qus = int(neu * 4)
        self.set_limits()
        self.set_speed()
        self.set_accel()

    @property
    def deg(self) -> float:
        """Get the current angle of the servo in degrees."""
        lo, hi, neu = self.limits
        us = (self.qus / 4.0) if self.qus is not None else neu
        return max(0.0, min(self.span_deg, (us - lo) * self.span_deg / (hi - lo)))

    @deg.setter
    def deg(self, value: float):
        """Set the angle of the servo in degrees."""
        lo, hi, _ = self.limits
        v = max(0.0, min(self.span_deg, float(value)))
        us = lo + (hi - lo) * (v / self.span_deg)
        self.qus = int(us * 4)
        self._controller.set_target_qus(channel=self.channel, target_qus=self.qus)

    def set_speed(self, speed: Optional[int] = None):
        """
        Set the speed of the servo.
        """
        logger.debug("Servo.set_speed(speed=%s)", speed)
        if speed is not None:
            self.speed = speed
        self._controller.set_speed(channel=self.channel, value=self.speed)

    def set_accel(self, accel: Optional[int] = None):
        """
        Set the acceleration of the servo.
        """
        logger.debug("Servo.set_accel(accel=%s)", accel)
        if accel is not None:
            self.accel = accel
        self._controller.set_accel(channel=self.channel, value=self.accel)

    def set_degrees(
        self,
        deg: Optional[int] = None,
        span_deg: Optional[float] = None,
        wait: bool = False,
    ):
        """
        Set the degrees of the servo.
        """
        logger.debug(
            "Servo.set_degrees(deg=%s, span_deg=%s, wait=%s)", deg, span_deg, wait
        )
        if span_deg is not None:
            self.span_deg = span_deg
        if deg is not None:
            self.deg = deg  # sends exactly once via the property setter
        if wait:
            self.wait()

    def set_qus(self, qus: int, wait: bool = False):
        """
        Set the qus of the servo.
        """
        logger.debug("Servo.set_qus(qus=%s, wait=%s)", qus, wait)
        self.qus = int(qus)
        self._controller.set_target_qus(channel=self.channel, target_qus=self.qus)
        if wait:
            self.wait()

    def set_limits(
        self,
        limits: Optional[list[int]] = None,
        min_us: Optional[int] = None,
        max_us: Optional[int] = None,
        neutral_us: Optional[int] = None,
    ):
        """
        Set the limits of the servo.
        """
        logger.debug(
            "Servo.set_limits(limits=%s, min_us=%s, max_us=%s, neutral_us=%s)",
            limits,
            min_us,
            max_us,
            neutral_us,
        )
        if limits is not None:
            self.limits = limits
        if min_us is not None:
            self.limits[0] = min_us
        if max_us is not None:
            self.limits[1] = max_us
        if neutral_us is not None:
            self.limits[2] = neutral_us
        self._controller.set_limits(
            channel=self.channel,
            min_us=self.limits[0],
            max_us=self.limits[1],
            neutral_us=self.limits[2],
        )

    def wait(self):
        """Wait for the servo to reach its target position."""
        logger.debug("Servo.wait()")
        self._controller.wait()

    def is_moving(self) -> bool:
        """Check if the servo is currently moving."""
        logger.debug("Servo.is_moving()")
        return self._controller.is_moving()


# if __name__ == "__main__":
#     m = Maestro(port="/dev/ttyACM0")
#     rotate_servos = {
#         "u": Servo(
#             maestro=m,
#             channel=0,
#             limits=[500, 2500, 1500],
#             speed=75,
#             accel=0,
#             span_deg=270,
#         ),
#         "d": Servo(
#             maestro=m,
#             channel=1,
#             limits=[500, 2500, 1500],
#             speed=75,
#             accel=0,
#             span_deg=270,
#         ),
#         "l": Servo(
#             maestro=m,
#             channel=2,
#             limits=[500, 2500, 1500],
#             speed=75,
#             accel=0,
#             span_deg=270,
#         ),
#         "r": Servo(
#             maestro=m,
#             channel=3,
#             limits=[500, 2500, 1500],
#             speed=75,
#             accel=0,
#             span_deg=270,
#         ),
#     }
#     engage_servos = {
#         "u": Servo(
#             maestro=m,
#             channel=4,
#             limits=[500, 2500, 1500],
#             speed=75,
#             accel=0,
#             span_deg=180,
#         ),
#         "d": Servo(
#             maestro=m,
#             channel=5,
#             limits=[500, 2500, 1500],
#             speed=75,
#             accel=0,
#             span_deg=180,
#         ),
#         "l": Servo(
#             maestro=m,
#             channel=6,
#             limits=[500, 2500, 1500],
#             speed=75,
#             accel=0,
#             span_deg=180,
#         ),
#         "r": Servo(
#             maestro=m,
#             channel=7,
#             limits=[500, 2500, 1500],
#             speed=75,
#             accel=0,
#             span_deg=180,
#         ),
#     }

#     for key, servo in rotate_servos.items():
#         print(f"Testing {key}")
#         for deg in [0, 90, 180, 270]:
#             servo.set_degrees(deg=deg)
#             while servo.is_moving():
#                 time.sleep(0.15)
#             print(f"i. at {servo.deg}")
#             time.sleep(0.15)

#     for key, servo in engage_servos.items():
#         print(f"Testing {key}")
#         for deg in [0, 90, 180]:
#             servo.set_degrees(deg=deg)
#             while servo.is_moving():
#                 time.sleep(0.15)
#             print(f"i. at {servo.deg}")
#             time.sleep(0.15)
