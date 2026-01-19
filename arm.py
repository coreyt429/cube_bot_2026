"""
Module for controlling CubeBot Arms
"""

from dataclasses import dataclass, field
import logging
from maestro import Maestro, Servo, ServoConfig


logger = logging.getLogger("arm")


@dataclass
class ArmConfig:
    """Configuration for robot arm"""

    port: str = "/dev/ttyACM0"
    open_channel: int = 4
    rotate_channel: int = 0
    open_limit: int = 110
    qus: dict = field(default_factory=dict)
    key: str = "l"


class Arm:
    """Class for robot arm"""

    def __init__(
        self, controller: Maestro = None, cfg: ArmConfig = None, parent: object = None
    ):
        logger.debug(
            "__init__(port=%s, open_channel=%s, rotate_channel=%s, open_limit=%s, qus=%s)",
            cfg.port,
            cfg.open_channel,
            cfg.rotate_channel,
            cfg.open_limit,
            cfg.qus,
        )
        self.parent = parent
        self.cfg = cfg
        if self.cfg is None:
            self.cfg = ArmConfig()
        self.controller = controller
        if self.controller is None:
            self.controller = Maestro(port=self.cfg.port)
        self.extended = True
        self.deg = 90
        self.servos = {
            "open": Servo(
                controller=self.controller,
                channel=self.cfg.open_channel,
                config=ServoConfig(span_deg=180),
            ),
            "rotate": Servo(
                controller=self.controller,
                channel=self.cfg.rotate_channel,
                config=ServoConfig(span_deg=270, initial_deg=self.deg),
            ),
        }

    def __str__(self) -> str:
        key = getattr(self.cfg, "key", "?")
        open_ch = getattr(self.cfg, "open_channel", "?")
        rotate_ch = getattr(self.cfg, "rotate_channel", "?")
        return f"Arm(key={key}, open_ch={open_ch}, rotate_ch={rotate_ch})"

    def close(self, wait=True):
        """Close the gripper"""
        logger.debug("close(wait=%s)", wait)
        self.set_speed(75)
        target = self.cfg.qus.get("closed", self.cfg.qus.get("retracted", 10000))
        self.servos["open"].set_qus(target, wait=wait)
        self.extended = False
        self.set_speed(0)

    def open(self, wait=True):
        """Open the gripper"""
        logger.debug("open(wait=%s)", wait)
        self.set_speed(75)
        target = self.cfg.qus.get("open", self.cfg.qus.get("extended", 6888))
        self.servos["open"].set_qus(target, wait=wait)
        self.extended = True
        self.set_speed(0)

    def retract(self, wait=True):
        """Backward-compatible alias for close()"""
        self.close(wait=wait)

    def extend(self, wait=True):
        """Backward-compatible alias for open()"""
        self.open(wait=wait)

    def set_speed(self, speed: int = 75):
        """Set the speed for the arm"""
        logger.debug("set_speed(speed=%d)", speed)
        speed = max(0, min(75, speed))
        for servo in self.servos.values():
            servo.set_speed(speed)
        
    def set_degrees(self, degrees, wait=True):
        """Set the arm to a specific angle. 0 is straight out, 180 is straight back"""
        logger.debug("set_degrees(degrees=%s, wait=%s)", degrees, wait)
        self.deg = degrees
        self.servos["rotate"].set_qus(self.cfg.qus.get(str(degrees), 10000), wait=wait)

    def rotate(self, degrees, wait=True):
        """Rotate the arm to a specific angle. + clockwise, - counter-clockwise"""
        logger.debug("rotate(degrees=%s, wait=%s)", degrees, wait)
        initial_state = self.extended
        self.set_speed(75)
        # counter-clockwise rotation
        if degrees < 0:
            # rotate out full spans
            while degrees < -270:
                self.reset(degrees=270, wait=wait)
                self.set_degrees(degrees=0, wait=wait)
                degrees += 270
            # rotate, remaining degrees
            self.reset(degrees=270, wait=wait)
            self.set_degrees(degrees=self.deg - degrees, wait=wait)
            return
        if not initial_state:
            self.close()
        # clockwise rotation
        while degrees > 270:
            self.reset(degrees=0, wait=wait)
            self.set_degrees(degrees=270, wait=wait)
            degrees -= 270
        # rotate, remaining degrees
        if self.deg + degrees > 270:
            self.reset(degrees=0, wait=wait)
        self.set_degrees(degrees=self.deg + degrees, wait=wait)
        if not initial_state:
            self.close()
        else:
            self.wiggle()
        self.set_speed(0)
        return

    def wiggle(self):
        """
        Wiggle the rotate servo to settle the cube
        """
        current_qus = self.servos["rotate"].qus
        wiggles = [350, 250, 150]
        for wiggle_room in wiggles:
            qus = [
                current_qus + wiggle_room,
                current_qus - wiggle_room,
                current_qus,
            ]
            for q in qus:
                logging.debug("Setting qu to %s", q)
                self.servos["rotate"].set_qus(q, wait=True)

    def reset(self, degrees=90, wait=True):
        """Reset the arm to a known position"""
        logger.debug("reset(degrees=%s, wait=%s)", degrees, wait)
        self.open(wait=wait)
        self.servos["rotate"].set_degrees(deg=degrees, wait=wait)
        self.deg = degrees
        self.close(wait=wait)

    def wait(self):
        """Wait for the controller to finish all movements."""
        logger.debug("wait()")
        self.controller.wait()


if __name__ == "__main__":
    arm = Arm()
    arm.servos["open"].set_degrees(0)
    arm.servos["rotate"].set_degrees(0)
