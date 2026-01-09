"""
Module for controlling the CubeBot
"""

import json
import logging
import requests
from cube import FACES
from maestro import Maestro
from arm import Arm, ArmConfig

logger = logging.getLogger("cube_bot")


class CubeBot:
    """
    CubeBot class for controlling the CubeBot
    """

    def __init__(self, name, port=None):
        logger.debug("__init__(name=%s, port=%s)", name, port)
        self.name = name
        self.cfg = {}
        self.cube_orientation = 0
        self.load_config(port=port)
        self._controller = Maestro(port=self.cfg.get("port", port or "/dev/ttyACM0"))

        self.arms = {}
        for arm_key in ("l", "r"):
            arm_cfg = self._normalize_arm_cfg(arm_key)
            self.arms[arm_key] = Arm(
                parent=self,
                controller=self._controller,
                cfg=ArmConfig(
                    open_channel=arm_cfg["open_channel"],
                    rotate_channel=arm_cfg["rotate_channel"],
                    qus=arm_cfg.get("qus", {}),
                    key=arm_key,
                ),
            )
        for arm in self.arms.values():
            arm.reset(wait=False)
            arm.close(wait=True)

    def set_speed(self, speed: int = 75):
        """Set the speed for all arms"""
        logger.debug("set_speed(speed=%d)", speed)
        speed = max(0, min(75, speed))
        for arm in self.arms.values():
            arm.set_speed(speed)

    def _normalize_arm_cfg(self, arm_key: str) -> dict:
        arms = self.cfg.setdefault("arms", {})
        if arm_key not in arms:
            fallback = "u" if arm_key == "l" else "d"
            if fallback in arms:
                arms[arm_key] = dict(arms[fallback])
        defaults = {
            "l": {"open_channel": 4, "rotate_channel": 0},
            "r": {"open_channel": 5, "rotate_channel": 1},
        }
        arm_cfg = arms.setdefault(arm_key, dict(defaults.get(arm_key, {})))
        if "open_channel" not in arm_cfg:
            arm_cfg["open_channel"] = arm_cfg.get(
                "extend_channel", defaults[arm_key]["open_channel"]
            )
        if "rotate_channel" not in arm_cfg:
            arm_cfg["rotate_channel"] = defaults[arm_key]["rotate_channel"]
        qus = arm_cfg.setdefault("qus", {})
        if "open" not in qus and "extended" in qus:
            qus["open"] = qus["extended"]
        if "closed" not in qus and "retracted" in qus:
            qus["closed"] = qus["retracted"]
        if qus.get("state") == "extended":
            qus["state"] = "open"
        elif qus.get("state") == "retracted":
            qus["state"] = "closed"
        return arm_cfg

    def _require_arms(self, arm_keys) -> bool:
        missing = [key for key in arm_keys if key not in self.arms]
        if missing:
            logger.warning("Missing arms for operation: %s", ", ".join(missing))
            return False
        return True

    def load_config(self, port=None):
        """
        Load configuration for the CubeBot
        """
        logger.debug("load_config(port=%s)", port)
        # Load configuration for the CubeBot
        try:
            with open(f"{self.name}.json", "r", encoding="utf-8") as f:
                self.cfg = json.load(f)
                logger.info("Config loaded")
        except FileNotFoundError as e:
            logger.warning("Config file not found: %s", e)
            # Use default configuration
            self.cfg = {
                "port": port or "/dev/ttyACM0",
                "arms": {
                    "l": {"open_channel": 4, "rotate_channel": 0},
                    "r": {"open_channel": 5, "rotate_channel": 1},
                },
            }
            logger.info("Using default config")
            self.save_config()
        for arm_key in ("l", "r"):
            self._normalize_arm_cfg(arm_key)
        logger.debug("Loaded configuration for %s: %s", self.name, self.cfg)

    # def load_cube(self):
    #     """
    #     Load the cube's state
    #     """
    #     logger.debug("load_cube()")
    #     for arm_name, arm in self.arms.items():
    #         arm.reset()
    #         arm.retract(wait=True)

    def save_config(self):
        """
        Save the configuration for the CubeBot
        """
        logger.debug("save_config()")
        with open(f"{self.name}.json", "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, indent=4)

    def _rotate_clockwise(self, arm: Arm, wait: bool = True):
        """
        Rotate the arm clockwise
        """
        logger.info("Rotating arm clockwise: %s", arm.cfg.key)
        arm.close(wait=True)
        arm.set_degrees(90, wait=True)
        arm.open(wait=True)
        logger.debug("Setting degrees to 180, current_qu=%s", arm.servos["rotate"].qus)
        arm.set_degrees(180, wait=wait)
        arm.wiggle()

    def _rotate_counterclockwise(self, arm: Arm, wait: bool = True):
        """
        Rotate the arm counter-clockwise
        """
        logger.info("Rotating arm counter-clockwise: %s", arm.cfg.key)
        arm.close(wait=True)
        arm.set_degrees(180, wait=True)
        arm.open(wait=True)
        logger.debug("Setting degrees to 90, current_qu=%s", arm.servos["rotate"].qus)
        arm.set_degrees(90, wait=wait)
        arm.wiggle()

    def orient_cube(self, target: int = 0):
        """
        Orient the cube to a specific orientation
        Red location:
            0 - front
            1 - left
            2 - back
            3 - right
        """
        if not self._require_arms(["u", "d", "l", "r"]):
            return
        while self.cube_orientation != target:
            # if one back hits it, go ccw
            if (self.cube_orientation - 1) % 4 == target:
                self._rotate_cube_y(clockwise=False)
                continue
            # else cw
            self._rotate_cube_y(clockwise=True)

    def _reset_arm(self, arm: Arm):
        """
        Reset the arm to its initial position
        """
        if arm.deg != 180:
            logger.info("Resetting arm")
            arm.close(wait=True)
            arm.set_degrees(180, wait=True)
        if arm.extended is False:
            arm.open(wait=True)

    def _turn(self, face: str, clockwise: bool = True, wait: bool = True):
        """
        Turn the specified face of the cube
        """
        if face not in self.arms:
            logger.warning("Arm %s not configured for turn", face)
            return
        arm = self.arms[face]
        if clockwise:
            self._rotate_clockwise(arm, wait=wait)
        else:
            self._rotate_counterclockwise(arm, wait=wait)
        self._reset_arm(arm)

    def up(self, clockwise: bool = True, wait: bool = True):
        """
        Turn the upper face of the cube
        """
        # self.orient_cube(target=0)
        self._turn("u", clockwise, wait=wait)

    def down(self, clockwise: bool = True, wait: bool = True):
        """
        Turn the lower face of the cube
        """
        # self.orient_cube(target=0)
        self._turn("d", clockwise, wait=wait)

    def left(self, clockwise: bool = True, wait: bool = True):
        """
        Turn the left face of the cube
        """
        self.orient_cube(target=0)
        self._turn("l", clockwise, wait=wait)

    def right(self, clockwise: bool = True, wait: bool = True):
        """
        Turn the right face of the cube
        """
        self.orient_cube(target=0)
        self._turn("r", clockwise, wait=wait)

    def engage(self):
        """
        Engage the arms of the CubeBot
        """
        logger.info("Engaging arm")
        self.disengage(wait=False)
        for arm in self.arms.values():
            arm.open(wait=True)

    def disengage(self, wait: bool = True):
        """
        Disengage the arms of the CubeBot
        """
        logger.info("Disengaging arm, wait: %s", wait)
        for arm in self.arms.values():
            arm.close(wait=wait)
        for arm in self.arms.values():
            arm.set_degrees(180, wait=wait)

    def rotate_cube(self, axis: str = "y", clockwise: bool = True):
        """
        Rotate the cube around the specified axis
        """
        if axis == "x":
            self._rotate_cube_x(clockwise=clockwise)
        elif axis == "y":
            self._rotate_cube_y(clockwise=clockwise)
        elif axis == "z":
            self._rotate_cube_z(clockwise=clockwise)

    def _rotate_cube_y(self, clockwise: bool = True):
        """
        Rotate the cube around the Y-axis
        """
        if not self._require_arms(["u", "d", "l", "r"]):
            return
        logger.info(
            "Rotating cube %s", "clockwise" if clockwise else "counter-clockwise"
        )
        for face in ["u", "d"]:
            self._reset_arm(self.arms[face])
        logger.debug("retracting arms")
        for face in ["l", "r"]:
            self.arms[face].close(wait=True)
        logger.debug("rotating cube")
        turns = [270, 90]
        if not clockwise:
            turns.reverse()
        self.arms["u"].set_degrees(turns[0], wait=False)
        self.arms["d"].set_degrees(turns[1], wait=True)
        logger.debug("extending arms")
        for face in ["l", "r"]:
            self.arms[face].open(wait=True)
        for face in ["u", "d"]:
            self._reset_arm(self.arms[face])
        if clockwise:
            self.cube_orientation = (self.cube_orientation + 1) % 4
        else:
            self.cube_orientation = (self.cube_orientation - 1) % 4

    def _rotate_cube_x(self, clockwise: bool = True):
        """
        Rotate the cube around the X-axis
        """
        if not self._require_arms(["u", "d", "l", "r"]):
            return
        logger.info(
            "Rotating cube %s", "clockwise" if clockwise else "counter-clockwise"
        )
        for face in ["l", "r"]:
            self._reset_arm(self.arms[face])
        logger.debug("retracting arms")
        for face in ["u", "d"]:
            self.arms[face].close(wait=True)
        logger.debug("rotating cube")
        turns = [90, 270]
        if not clockwise:
            turns.reverse()
        self.arms["l"].set_degrees(turns[0], wait=False)
        self.arms["r"].set_degrees(turns[1], wait=True)
        logger.debug("extending arms")
        for face in ["u", "d"]:
            self.arms[face].open(wait=True)
        for face in ["l", "r"]:
            self._reset_arm(self.arms[face])

    def _rotate_cube_z(self, clockwise: bool = True):
        """
        Rotate the cube around the Z-axis
        """
        if not self._require_arms(["u", "d", "l", "r"]):
            return
        logger.info(
            "Rotating cube %s", "clockwise" if clockwise else "counter-clockwise"
        )
        if clockwise:
            self._rotate_cube_x(clockwise=True)
            self._rotate_cube_y(clockwise=True)
            self._rotate_cube_x(clockwise=False)
        else:
            self._rotate_cube_x(clockwise=False)
            self._rotate_cube_y(clockwise=True)
            self._rotate_cube_x(clockwise=True)

    def middle(self, clockwise: bool = True):
        """rotate middle slice"""
        if not self._require_arms(["l", "r"]):
            return
        self.orient_cube(target=0)
        turns = [90, 270]
        if not clockwise:
            turns.reverse()
        self.arms["l"].set_degrees(turns[1], wait=False)
        self.arms["r"].set_degrees(turns[0], wait=True)
        # self.left(clockwise=clockwise, wait=False)
        # self.right(clockwise=not clockwise, wait=True)
        self.arms["l"].wiggle()
        self.arms["r"].wiggle()
        self._controller.wait()
        self._rotate_cube_x(clockwise=clockwise)

    def equator(self, clockwise: bool = True):
        """rotate equator slice"""
        if not self._require_arms(["u", "d"]):
            return
        self.orient_cube(target=0)
        turns = [90, 270]
        if not clockwise:
            turns.reverse()
        self.arms["u"].set_degrees(turns[0], wait=False)
        self.arms["d"].set_degrees(turns[1], wait=True)
        # self.left(clockwise=clockwise, wait=False)
        # self.right(clockwise=not clockwise, wait=True)
        self.arms["u"].wiggle()
        self.arms["d"].wiggle()
        self._controller.wait()
        self._rotate_cube_y(clockwise=clockwise)

    def z_slice(self, clockwise: bool = True):
        """rotate z slice"""
        if not self._require_arms(["l", "r"]):
            return
        logger.info(
            "Rotating z slice %s", "clockwise" if clockwise else "counter-clockwise"
        )
        logger.debug(
            "Rotating cube around Y axis %s",
            "counter-clockwise" if clockwise else "clockwise",
        )
        self.orient_cube(target=3)
        # self._rotate_cube_y(clockwise=not clockwise)
        if clockwise:
            logger.debug("Rotating middle slice clockwise")
            self.middle(clockwise=clockwise)
        else:
            logger.debug("Rotating middle slice counter-clockwise")
            self.middle(clockwise=not clockwise)
        for face, arm in self.arms.items():
            logger.debug("Resetting arm for face %s", face)
            arm.wiggle()
        logger.debug(
            "Rotating cube around Y axis %s",
            "clockwise" if clockwise else "counter-clockwise",
        )
        # self._rotate_cube_y(clockwise=clockwise)

    def front(self, clockwise: bool = True):
        """
        Turn the front face of the cube
        """
        self.orient_cube(target=1)
        # self.rotate_cube()
        self._turn("l", clockwise)
        # self.rotate_cube(clockwise=False)

    def back(self, clockwise: bool = True):
        """
        Turn the back face of the cube
        """
        self.orient_cube(target=1)
        # self.rotate_cube()
        self._turn("r", clockwise)
        # self.rotate_cube(clockwise=False)

    def run_command(self, command: str):
        """
        Run a command on the CubeBot
        """
        commands = {
            "u": self.up,
            "d": self.down,
            "l": self.left,
            "r": self.right,
            "f": self.front,
            "b": self.back,
            "x": self._rotate_cube_x,
            "y": self._rotate_cube_y,
            "z": self._rotate_cube_z,
            "m": self.middle,
            "e": self.equator,
            "s": self.z_slice,
        }
        command = command.strip().lower()
        clockwise = True
        if "'" in command:
            clockwise = False
        if command[0] in commands:
            commands[command[0]](clockwise=clockwise)
            if "2" in command:
                commands[command[0]](clockwise=clockwise)
        else:
            logger.warning("Unknown command: %s", command)

    def run_command_string(self, command_string: str):
        """
        Run a string of commands on the CubeBot
        """
        commands = command_string.replace(" ", ",").replace(",,", ",").split(",")
        for command in commands:
            logger.info("Running command: %s", command)
            self.run_command(command)

    def _get_face_state(self) -> str:
        """
        Get the current state of the face the camera is on
        """
        if not self._require_arms(["l", "r"]):
            return "XXXXXXXXX"
        self.frame_shot()

        response = requests.get("http://127.0.0.1:8088/face", timeout=5)
        face_string = "XXXXXXXXX"
        if response.status_code == 200:
            face_string = ""
            result = response.json()
            logging.info("Face detection result: %s", result.get("labels"))
            for color in result.get("labels", []):
                face_string += color[0].upper()
            logging.info("Face state: %s", face_string)
        for arm_key in ["l", "r"]:
            arm = self.arms[arm_key]
            arm.open()
        return face_string

    def frame_shot(self):
        """Move grippers out of the camera view"""
        if not self._require_arms(["l", "r"]):
            return
        for arm_key in ["l", "r"]:
            arm = self.arms[arm_key]
            arm.reset()
            arm.open()

        for arm_key in ["u", "d"]:
            if arm_key in self.arms:
                arm = self.arms[arm_key]
                arm.reset(degrees=90)

        for arm_key in ["l", "r"]:
            arm = self.arms[arm_key]
            arm.close()

    def scan_cube(self) -> str:
        """
        Scan the cube and return its current state
        """
        if not self._require_arms(["l", "r"]):
            return "X" * 54
        faces = {}
        for face in ["B", "L", "F", "R"]:
            faces[face] = self._get_face_state()
            self._rotate_cube_y(clockwise=True)
            for arm_key in ["l", "r"]:
                self.arms[arm_key].reset()
        self._rotate_cube_x(clockwise=False)
        for arm_key in ["u", "d"]:
            if arm_key in self.arms:
                self.arms[arm_key].reset()
        for face in ["D", "U"]:
            for arm_key in ["l", "r"]:
                self.arms[arm_key].reset()
            faces[face] = self._get_face_state()
            self._rotate_cube_y(clockwise=True)
            self._rotate_cube_y(clockwise=True)
        self._rotate_cube_x(clockwise=True)

        face_state = "".join(faces.get(face, "XXXXXXXXX") for face in FACES)
        logger.info("Current cube state:\n%s", face_state)
        return face_state


# YBRWGRBWY
# WBGOYRWOR
# WBWYORBWR
# WBWYORBWR
# WBWYORBWR
# WBWYORBWR

# BBBBBGYYY
# BBBBBGYYY
# BBBBBGYYY
# BBBBBGYYY
# BBBBBGYYY
# BBBBBGYYY
