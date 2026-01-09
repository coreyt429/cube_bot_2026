"""
Module to simulate a cube puzzle of nxn size.
This module provides a class `Cube` that represents a cube puzzle of size n x n.
It includes methods to rotate the cube, check if it is solved, and print its current state.
The cube is initialized with a solved state, and the user can perform rotations on the cube.
This module only handles cube movements, and does not include any solving algorithms.

Notes:
  add these that we haven't supported before:
    M = Middle slice between L and R
    E = Equator slice between U and D
    S = Standing slice between F and B (not easily visualized in 2D)

"""

# --- Standard imports ---
import logging
from random import choice

# --- Move emission system ---
from dataclasses import dataclass
from typing import Callable, List


logger = logging.getLogger("cube")


@dataclass(frozen=True)
class Move:
    """Represents a single move on the cube."""

    kind: str  # 'face' | 'slice' | 'cube'
    target: str  # face letter, slice letter, or axis letter
    clockwise: bool


# from visualize import print_color_cube

FACES = ["U", "D", "L", "R", "F", "B"]
COLORS = ["W", "Y", "G", "B", "R", "O"]
FACE_COLORS = dict(zip(FACES, COLORS))
CORNERS = ["UFL", "UFR", "UBR", "UBL", "DFL", "DFR", "DBR", "DBL"]
EDGES = ["UF", "UR", "UB", "UL", "DF", "DR", "DB", "DL", "FL", "FR", "BL", "BR"]
CORNER_FACE_ORDER = {
    "UFR": ("U", "R", "F"),
    "UFL": ("U", "F", "L"),
    "UBL": ("U", "L", "B"),
    "UBR": ("U", "B", "R"),  # WOB
    "DFR": ("R", "D", "F"),
    "DFL": ("F", "D", "L"),
    "DBL": ("L", "D", "B"),
    "DBR": ("B", "D", "R"),  # WOB
}

SLICE_AXIS = {
    "M": "x",
    "E": "y",
    "S": "z",
}

SLICE_POSITIONS = {
    "M": [
        "UF",
        "U",
        "UB",
        "B",
        "DB",
        "D",
        "DF",
        "F",
    ],
    "E": [
        "FL",
        "F",
        "FR",
        "R",
        "BR",
        "B",
        "BL",
        "L",
    ],
    "S": [
        "UL",
        "U",
        "UR",
        "R",
        "DR",
        "D",
        "DL",
        "L",
    ],
}

FACE_POSITIONS = {
    "U": {
        0: "UBL",
        1: "UB",
        2: "UBR",
        3: "UL",
        4: "U",
        5: "UR",
        6: "UFL",
        7: "UF",
        8: "UFR",
    },
    "D": {
        0: "DFL",
        1: "DF",
        2: "DFR",
        3: "DL",
        4: "D",
        5: "DR",
        6: "DBL",
        7: "DB",
        8: "DBR",
    },
    "L": {
        0: "UBL",
        1: "UL",
        2: "UFL",
        3: "BL",
        4: "L",
        5: "FL",
        6: "DBL",
        7: "DL",
        8: "DFL",
    },
    "R": {
        0: "UFR",
        1: "UR",
        2: "UBR",
        3: "FR",
        4: "R",
        5: "BR",
        6: "DFR",
        7: "DR",
        8: "DBR",
    },
    "F": {
        0: "UFL",
        1: "UF",
        2: "UFR",
        3: "FL",
        4: "F",
        5: "FR",
        6: "DFL",
        7: "DF",
        8: "DFR",
    },
    "B": {
        0: "UBR",
        1: "UB",
        2: "UBL",
        3: "BR",
        4: "B",
        5: "BL",
        6: "DBR",
        7: "DB",
        8: "DBL",
    },
}

FACE_ROTATIONS = {
    # (axis, clockwise)
    "U": ("y", True),
    "D": ("y", False),
    "L": ("x", False),
    "R": ("x", True),
    "F": ("z", True),
    "B": ("z", False),
}

ROTATION_MAP = {
    "x": {
        "UFR": "UBR",
        "UF": "UB",
        "UFL": "UBL",
        "UL": "BL",
        "U": "B",
        "UR": "BR",
        "UBL": "DBL",
        "UB": "DB",
        "UBR": "DBR",
        "DFR": "UFR",
        "DF": "UF",
        "DFL": "UFL",
        "DL": "FL",
        "D": "F",
        "DR": "FR",
        "DBL": "DFL",
        "DB": "DF",
        "DBR": "DFR",
        "FL": "UL",
        "F": "U",
        "FR": "UR",
        "L": "L",
        "R": "R",
        "BL": "DL",
        "B": "D",
        "BR": "DR",
    },
    "y": {
        "UFR": "UFL",
        "UF": "UL",
        "UFL": "UBL",
        "UL": "UB",
        "U": "U",
        "UR": "UF",
        "UBL": "UBR",
        "UB": "UR",
        "UBR": "UFR",
        "DFR": "DFL",
        "DF": "DL",
        "DFL": "DBL",
        "DL": "DB",
        "D": "D",
        "DR": "DF",
        "DBL": "DBR",
        "DB": "DR",
        "DBR": "DFR",
        "FL": "BL",
        "F": "L",
        "FR": "FL",
        "L": "B",
        "R": "F",
        "BL": "BR",
        "B": "R",
        "BR": "FR",
    },
    "z": {
        "UFR": "DFR",
        "UF": "FR",
        "UFL": "UFR",
        "UL": "UR",
        "U": "R",
        "UR": "DR",
        "UBL": "UBR",
        "UB": "BR",
        "UBR": "DBR",
        "DFR": "DFL",
        "DF": "FL",
        "DFL": "UFL",
        "DL": "UL",
        "D": "L",
        "DR": "DL",
        "DBL": "UBL",
        "DB": "BL",
        "DBR": "DBL",
        "FL": "UF",
        "F": "F",
        "FR": "DF",
        "L": "U",
        "R": "D",
        "BL": "UB",
        "B": "B",
        "BR": "DB",
    },
}

ROTATION_MAP_INVERSE = {
    "x": {value: key for key, value in ROTATION_MAP["x"].items()},
    "y": {value: key for key, value in ROTATION_MAP["y"].items()},
    "z": {value: key for key, value in ROTATION_MAP["z"].items()},
}


def get_axis_map(axis, clockwise=True):
    """
    Get the axis map for the cubie.
    The axis can be 'x', 'y', or 'z'.
    """
    if clockwise:
        return ROTATION_MAP[axis]
    return ROTATION_MAP_INVERSE[axis]


class Cubie:
    """
    Class representing a single cubie in the cube.
    Each cubie has a color and an index.
    """

    def _rotate_corner_x(self, clockwise, new_position):
        """Rotate on the x axis"""
        if clockwise:
            if new_position in ["DBR", "UFL"]:
                pass
            else:
                if "R" in new_position:
                    # rotate the orientation of the cubie
                    self.orientation = (self.orientation - 1) % len(self.color)
                if "L" in new_position:
                    # rotate the orientation of the cubie
                    self.orientation = (self.orientation + 1) % len(self.color)
        else:
            if new_position in ["UBR", "DFL"]:
                pass
                # self.orientation = (self.orientation - 1) % len(self.color)
            else:
                if "R" in new_position:
                    # rotate the orientation of the cubie
                    self.orientation = (self.orientation + 1) % len(self.color)
                if "L" in new_position:
                    # rotate the orientation of the cubie
                    self.orientation = (self.orientation - 1) % len(self.color)

    def _rotate_edge_x(self, clockwise, new_position):
        """Rotate the edge cubie on the x axis"""
        if new_position in ["DF", "UF", "UB", "DB"]:
            if clockwise:
                # rotate the orientation of the cubie
                self.orientation = (self.orientation + 1) % len(self.color)
            else:
                self.orientation = (self.orientation - 1) % len(self.color)

    def _rotate_edge_y(self, clockwise, new_position):
        """Rotate the edge cubie on the y axis"""
        if new_position in ["FL", "FR", "BL", "BR"]:
            if clockwise:
                # rotate the orientation of the cubie
                self.orientation = (self.orientation - 1) % len(self.color)
            else:
                self.orientation = (self.orientation + 1) % len(self.color)

    def _rotate_corner_z(self, clockwise, new_position):
        """Rotate a corner cubie on the z axis"""

        if new_position in ["DFR", "UBL"] and clockwise:
            return

        if new_position in ["DBL", "UFR"] and not clockwise:
            return

        if new_position in ["DBL", "DFR"]:
            self.orientation = (self.orientation + 1) % len(self.color)
        elif new_position in ["UBL", "UFR"]:
            # rotate the orientation of the cubie
            self.orientation = (self.orientation - 1) % len(self.color)
        elif new_position in ["UBR", "DBR"]:
            if clockwise:
                # rotate the orientation of the cubie
                self.orientation = (self.orientation + 1) % len(self.color)
            else:
                self.orientation = (self.orientation - 1) % len(self.color)
        else:
            if clockwise:
                self.orientation = (self.orientation - 1) % len(self.color)
            else:
                self.orientation = (self.orientation + 1) % len(self.color)
        return

    def _rotate_edge_z(self, clockwise, new_position):
        """Rotate the cubie on the z axis"""
        if new_position in ["UF", "DF", "UB", "DB", "FL", "FR", "BL", "BR"]:
            if clockwise:
                # rotate the orientation of the cubie
                self.orientation = (self.orientation + 1) % len(self.color)
            else:
                self.orientation = (self.orientation - 1) % len(self.color)

    def rotate(self, axis, clockwise, axis_map=None):
        """
        Rotate the cubie around a specified face.
        The face can be 'U', 'D', 'L', 'R', 'F', or 'B'.
        face=W specifies whole cube
        FIXME:
            cube.py:265:4: R0912: Too many branches (47/12) (too-many-branches)
            cube.py:265:4: R0915: Too many statements (81/50) (too-many-statements)
        """
        logger.debug("Cubie.rotate: %s %s", axis, clockwise)
        if axis_map is None:
            axis_map = get_axis_map(axis, clockwise)
        # rotate the cubie
        new_position = axis_map[self.position]
        logger.debug("Cubie.rotate: %s %s", self.position, new_position)
        self.position = new_position
        # rotate the cubie orientation
        if axis == "x" and len(self.color) == 3:  # corner
            self._rotate_corner_x(clockwise, new_position)
        if axis == "x" and len(self.color) == 2:  # edge
            self._rotate_edge_x(clockwise, new_position)
        if axis == "y" and len(self.color) == 2:  # edge
            self._rotate_edge_y(clockwise, new_position)
        if axis == "z" and len(self.color) == 3:  # corner
            self._rotate_corner_z(clockwise, new_position)
        if axis == "z" and len(self.color) == 2:  # edge
            self._rotate_edge_z(clockwise, new_position)
            # if new_position in ["UL", "UR", "DL", "DR"]:
            #     if clockwise:
            #         # rotate the orientation of the cubie
            #         self.orientation = (self.orientation + 1) % len(self.color)
            #     else:
            #         self.orientation = (self.orientation - 1) % len(self.color)
            # if new_position in ["UF", "DF", "UB", "DB", "FL", "FR", "BL", "BR"]:
            #     # These edges flip when moved in F/B rotation
            #     if clockwise:
            #         self.orientation = (self.orientation + 1) % len(self.color)
            #     else:
            #         self.orientation = (self.orientation - 1) % len(self.color)

    def __init__(self, cube, position, color, orientation):
        self.cube = cube
        self.position = position
        self.color = color
        self.orientation = orientation

    def __repr__(self):
        return (
            f"Cubie(color={self.color}, "
            + f"position={self.position}, "
            + f"orientation={self.orientation})"
        )

    def __str__(self):
        return f"{self.color} {self.position} {self.orientation}"

    def alignment(self):
        """
        Get the count of faces that are correct.
        This does not take orientation into account.
        """
        count = 0
        for face in self.position:
            if self.cube.face_color(face) in self.color:
                count += 1
        return count

    def get_colors(self, color_filter=""):
        """
        Get the colors of the cubie.
        This is useful for accessing the colors of the cubie.
        """
        if color_filter:
            return [color for color in self.color if color not in color_filter]
        return self.color

    def to_dict(self):
        """
        dict representation of the cubie
        """
        return {
            "position": self.position,
            "color": self.color,
            "orientation": self.orientation,
        }


@dataclass
class CubeConfig:
    """Configuration for the cube."""

    size: int = 3
    state: str = ""
    debug: bool = False


class Cube:  # pylint: disable=too-many-public-methods
    """
    Class representing a cube puzzle of size n x n.
    The cube is initialized with a solved state, and the user can perform rotations on the cube.
    """

    def __init__(self, **kwargs):
        """
        Initialize the cube with size n x n.
        Parameters:
        - size: The size of the cube (default is 3 for a 3x3 cube).
        - state: A state string representing the cube's current state (optional).
        - debug: A boolean flag to enable debug logging (default is False).
        """
        self.cfg = CubeConfig(
            size=kwargs.get("size", 3),
            state=kwargs.get("state", ""),
            debug=kwargs.get("debug", False),
        )
        if self.cfg.size < 2 or self.cfg.size > 3:
            raise ValueError(f"Invalid cube size {self.cfg.size}: int({self.cfg.size})")
        self.cfg.debug = kwargs.get("debug", False)
        # init cube in solved state
        self.cube = {}
        self.cubies = []
        if "cubies" in kwargs:
            self.cubies = kwargs["cubies"]
        elif "state" in kwargs:
            self.load(kwargs["state"])
        else:
            self.reset()
        self.solved_state = self._solved_state()

        # --- Move emission support ---
        self._listeners: List[Callable[[Move], None]] = []
        self._record_moves: bool = False
        self._move_log: list[Move] = []

    def loglevel(self, level=logging.INFO):
        """
        Set the logging level for the cube.
        This is useful for debugging and logging cube operations.
        """
        logger.setLevel(level)

    def add_listener(self, fn: Callable[[Move], None]):
        """Subscribe to move events; fn will be called with Move(kind,target,clockwise)."""
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[Move], None]):
        """Unsubscribe a previously added listener."""
        try:
            self._listeners.remove(fn)
        except ValueError:
            pass

    def set_recording(self, enabled: bool = True):
        """Enable/disable move recording to an internal log (clears when toggled on)."""
        self._record_moves = enabled
        if enabled:
            self._move_log.clear()

    def get_move_log(self) -> list[Move]:
        """Return a copy of the recorded move log (if recording was enabled)."""
        return list(self._move_log)

    def _emit(self, move: Move):
        """Internal: deliver move to listeners and optional recorder."""
        if self._record_moves:
            self._move_log.append(move)
        for fn in list(self._listeners):
            fn(move)

    def reset(self):
        """
        Reset the cube to its solved state.
        This method is useful for resetting the cube after scrambling or solving.
        """
        self.cubies = []
        for corner in CORNERS:
            self.cubies.append(
                Cubie(
                    cube=self,
                    position=corner,
                    color=tuple(
                        COLORS[FACES.index(face)] for face in CORNER_FACE_ORDER[corner]
                    ),
                    orientation=0,
                )
            )
        if self.cfg.size == 3:
            for edge in EDGES:
                self.cubies.append(
                    Cubie(
                        cube=self,
                        position=edge,
                        color=tuple(COLORS[FACES.index(face)] for face in edge),
                        orientation=0,
                    )
                )
            for center in FACES:
                self.cubies.append(
                    Cubie(
                        cube=self,
                        position=center,
                        color=tuple(COLORS[FACES.index(face)] for face in center),
                        orientation=0,
                    )
                )

    def centers(self, color_filter=None):
        """
        Get the center cubies of the cube.
        This is useful for accessing the center cubies on the cube.
        """
        centers = []
        for cubie in self:
            if color_filter and not any(color in cubie.color for color in color_filter):
                continue
            if len(cubie.color) == 1:
                centers.append(cubie)
        return centers

    def edges(self, color_filter=None):
        """
        Get the edge cubies of the cube.
        This is useful for accessing the edge cubies on the cube.
        """
        edges = []
        for cubie in self:
            if color_filter and not any(color in cubie.color for color in color_filter):
                continue
            if len(cubie.color) == 2:
                edges.append(cubie)
        return edges

    def face_by_color(self, color):
        """
        Get the face of the cube by color.
        This is useful for accessing the face of the cube by its color.
        """
        if color not in COLORS:
            raise ValueError(f"Invalid color {color}: {COLORS}")
        for face in FACES:
            if color == self.get_sticker(face, 4):
                return face
        return None

    def face_color(self, face):
        """
        Get the color of a specific face.
        This is useful for accessing the color of a specific face on the cube.
        """
        if face not in FACES:
            raise ValueError(f"Invalid face {face}: {FACES}")
        return self.get_sticker(face, 4)

    def corners(self, color_filter=None):
        """
        Get the corner cubies of the cube.
        This is useful for accessing the corner cubies on the cube.
        """
        corners = []
        for cubie in self:
            if color_filter and not any(color in cubie.color for color in color_filter):
                continue
            if len(cubie.color) == 3:
                corners.append(cubie)
        return corners

    def load(self, state):
        """
        Load a cube state from a string representation.
        The string should be 6 * n^2 characters long,
        representing the colors of the stickers on each face.
        Note, while this will load a debug string or normal string,
        a debug string is preffered for loading.
        """
        logger.debug("load: %s", state)
        # load non_debug string
        states = [char for char in state.upper() if char in COLORS]
        self.cfg.size = int((len(state) / 6) ** 0.5)
        logger.debug("size: %s", self.cfg.size)
        if self.cfg.size < 2:
            raise ValueError(
                f"Invalid cube size {self.cfg.size}: int({len(states)} / 6)"
            )
        if len(states) != 6 * self.cfg.size**2:
            raise ValueError(
                f"Invalid cube state length {len(states)} for size {self.cfg.size}"
            )
        self.reset()
        valid_cubies = set(cubie.color for cubie in self.get_cubies())
        for face in FACES:
            for idx in range(self.cfg.size**2):
                color = states.pop(0)
                self.set_sticker(face, idx, color)
        # adjust cubies to their positions
        for cubie in self.get_cubies():
            while cubie.color not in valid_cubies:
                cubie.color = cubie.color[1:] + cubie.color[:1]
                cubie.orientation = (cubie.orientation - 1) % len(cubie.color)

    def _solved_state(self):
        """
        Calculate the solved state of the cube.
        The solved state is a hash of the cube's current state.
        """
        solve_state = ""
        for color in COLORS:
            for _ in range(self.cfg.size**2):
                solve_state += color
        logger.debug("solved_state: %s %s", solve_state, hash(solve_state))
        return hash(solve_state)

    def scramble(self, moves=20):
        """
        Scramble the cube by performing a series of random rotations.
        The number of moves can be specified (default is 20).
        """
        for _ in range(moves):
            face = choice(FACES)
            self.rotate_face(face, clockwise=choice([True, False]))

    def is_solved(self):
        """
        Check if the cube is in the solved state.
        The cube is considered solved if all stickers on each face are the same color.
        """
        logger.debug("is_solved: %s == %s", self.solved_state, hash(self))
        return self.solved_state == hash(self)

    def get_sticker(self, face, index=None, cubie=None):
        """
        Get the sticker at a specific face and index.
        This is useful for accessing specific stickers on the cube.
        """
        if cubie is None:
            if index is None:
                raise ValueError("Index must be specified if cubie is not provided")
            logger.debug("get_sticker: %s %s", face, index)
            position = FACE_POSITIONS[face][index]
            if self.cfg.size == 2:
                while len(position) < 3:
                    index += 1
                    position = FACE_POSITIONS[face][index]
            logger.debug("position: %s", position)
            cubie = self.get_cubie(position)
        else:
            position = cubie.position
        if cubie is None:
            raise ValueError(f"Invalid cubie position {position}")
        logger.debug("cubie.color: %s", cubie.color)
        logger.debug("cubie.position: %s", cubie.position)
        logger.debug("cubie.orientation: %s", cubie.orientation)
        try:
            logger.debug("position.index(face): %s", position.index(face))
        except ValueError as exc:
            logger.error("Invalid face %s in position %s", face, position)
            raise ValueError(f"Invalid face {face} in position {position}") from exc
        if len(cubie.color) == 3:
            return cubie.color[
                (CORNER_FACE_ORDER[position].index(face) + cubie.orientation)
                % len(cubie.color)
            ]
        logger.debug(
            "get edge sticker: %s %s %s %s",
            face,
            position.index(face),
            cubie.position,
            cubie.color,
        )
        return cubie.color[
            (position.index(face) + cubie.orientation) % len(cubie.color)
        ]

    def set_sticker(self, face, index, color):
        """
        Set the sticker at a specific face and index.
        This is useful for accessing specific stickers on the cube.
        """
        logger.debug("set_sticker: %s %s %s", face, index, color)
        position = FACE_POSITIONS[face][index]
        if self.cfg.size == 2:
            while len(position) < 3:
                index += 1
                position = FACE_POSITIONS[face][index]
        logger.debug("position: %s", position)
        cubie = self.get_cubie(position)
        if cubie is None:
            raise ValueError(f"Invalid cubie position {position}")
        logger.debug("cubie.color: %s", cubie.color)
        logger.debug("cubie.position: %s", cubie.position)
        logger.debug("cubie.orientation: %s", cubie.orientation)
        logger.debug("position.index(face): %s", position.index(face))
        # assume center to start
        color_index = 0
        # corner
        if len(cubie.color) == 3:
            color_index = (
                CORNER_FACE_ORDER[position].index(face) + cubie.orientation
            ) % len(cubie.color)
        # edge
        if len(cubie.color) == 2:
            color_index = (position.index(face) + cubie.orientation) % len(cubie.color)
        color_list = list(cubie.color)
        color_list[color_index] = color
        cubie.color = tuple(color_list)

    def get_cubie(self, position):
        """
        Get the cubie at a specific position.
        This is useful for accessing specific cubies on the cube.
        """
        for cubie in self.cubies:
            if cubie.position == position:
                return cubie
        return None

    def get_cubies(self, face_filter=None, color_filter=None, position_filter=None):
        """
        Get a list of cubies that match the specified filters.
        The filters can be face_filter (a list of faces) or color_filter (a list of colors).
        """
        cubies = []
        for cubie in self:
            if face_filter and not any(face in cubie.position for face in face_filter):
                continue
            if color_filter and not any(color in cubie.color for color in color_filter):
                continue
            if position_filter and not cubie.position in position_filter:
                continue
            cubies.append(cubie)
        return cubies

    @property
    def state(self):
        """
        Get the current state of the cube.
        """
        return str(self)

    @property
    def kociemba_state(self):
        """
        Get the Kociemba state representation of the cube.
        """
        my_state = str(self)
        faces = {
            "U": my_state[0:9],
            "D": my_state[9:18],
            "L": my_state[18:27],
            "R": my_state[27:36],
            "F": my_state[36:45],
            "B": my_state[45:54],
        }

        # New order: U, R, F, D, L, B
        kociemba_state = (
            faces["U"] + faces["R"] + faces["F"] + faces["D"] + faces["L"] + faces["B"]
        )
        # convert colors to faces
        kociemba_state = kociemba_state.replace("W", "U")
        kociemba_state = kociemba_state.replace("Y", "D")
        kociemba_state = kociemba_state.replace("R", "F")
        kociemba_state = kociemba_state.replace("B", "R")
        kociemba_state = kociemba_state.replace("G", "L")
        kociemba_state = kociemba_state.replace("O", "B")
        return kociemba_state

    def __hash__(self):
        """
        Return a hash of the cube's current state.
        This is useful for comparing cube states or storing them in sets/dictionaries.
        """
        debug = self.cfg.debug
        self.cfg.debug = True
        cube_str = str(self)
        logger.debug("cube_str: %s", {cube_str})
        self.cfg.debug = debug
        return hash(str(cube_str))

    def __str__(self):
        """
        String representation of the cube.
        This is useful for printing the cube's current state.
        """
        return self.as_string()

    def as_string(self):
        """
        Return a string representation of the cube for printing.
        """
        state_string = ""
        for face in FACES:
            for idx in range(self.cfg.size**2):
                state_string += self.get_sticker(face, idx)
        return state_string

    def __repr__(self):
        """
        String representation of the cube.
        """
        debug = self.cfg.debug
        self.cfg.debug = True
        # cube_str = str(self)
        self.cfg.debug = debug

        return (
            f"Cube(size={self.cfg.size}, "
            f"debug={self.cfg.debug}, cubies={[repr(cubie) for cubie in self.cubies]})"
        )

    def rotate_cube(self, clockwise=True, axis="Y"):
        """
        Rotate the cube around a specified axis.
        The axis can be 'X', 'Y', or 'Z'.
        """
        logger.debug("rotate_cube: %s %s", axis, clockwise)
        requested_clockwise = clockwise
        axis = axis.lower()
        axis_map = get_axis_map(axis, clockwise)
        for cubie in self.cubies:
            cubie.rotate(axis, clockwise, axis_map)
        self._emit(
            Move(kind="cube", target=axis.upper(), clockwise=requested_clockwise)
        )

    def rotate_slice(self, cube_slice, clockwise=True):
        """
        Rotate a slice of the cube along M, E, S.
        """
        logger.debug("_rotate_slice: %s %s", cube_slice, clockwise)
        requested_clockwise = clockwise
        axis = SLICE_AXIS[cube_slice.upper()]
        axis_map = get_axis_map(axis, clockwise)
        for cubie in self.get_cubies(
            position_filter=SLICE_POSITIONS[cube_slice.upper()]
        ):
            cubie.rotate(axis, clockwise, axis_map)
        self._emit(
            Move(kind="slice", target=cube_slice.upper(), clockwise=requested_clockwise)
        )

    def rotate_face(self, face, clockwise=True):
        """
        Rotate a face of the cube.
        """
        logger.debug("rotate_face: %s clockwise: %s", face, clockwise)
        requested_clockwise = clockwise
        (axis, mod_clockwise) = FACE_ROTATIONS[face]
        if not mod_clockwise:
            clockwise = not clockwise
        axis_map = get_axis_map(axis, clockwise)

        for cubie in self.get_cubies(face_filter=[face]):
            cubie.rotate(axis, clockwise, axis_map)
        self._emit(
            Move(kind="face", target=face.upper(), clockwise=requested_clockwise)
        )

    def sequence(self, sequence):
        """
        Apply a sequence of rotations to the cube.
        The sequence should be a string of face rotations (e.g., "U, D, L, R, F, B).
        """
        logger.debug("sequence: %s", sequence)
        sequence = sequence.replace("(", "").replace(")", "")
        sequence = sequence.replace("[", "").replace("]", "")
        sequence = sequence.replace("{", "").replace("}", "")
        sequence = sequence.replace(" ", ",")
        sequence = sequence.replace(",,", ",")
        logger.debug("adjusted sequence: %s", sequence)
        moves = sequence.split(",")
        moves = [move.strip() for move in moves if move.strip()]
        for move in moves:
            logger.debug("move: %s", move)
            target = move[0]
            count = 1
            if "2" in move:
                count = 2
            clockwise = True
            if "'" in move:
                clockwise = False
            for _ in range(count):
                if target in FACES:
                    self.rotate_face(target, clockwise=clockwise)
                    continue
                if target in SLICE_AXIS:
                    self.rotate_slice(target, clockwise=clockwise)
                    continue
                if target.upper() in ["X", "Y", "Z"]:
                    self.rotate_cube(axis=target.upper(), clockwise=clockwise)
                    continue
                if target in ["d", "u"]:
                    self.rotate_face(target.upper(), clockwise=clockwise)
                    self.rotate_slice("E", clockwise=not clockwise)
                    continue
                if target in ["l", "r"]:
                    self.rotate_face(target.upper(), clockwise=clockwise)
                    self.rotate_slice("M", clockwise=not clockwise)
                    continue
                if target in ["f", "b"]:
                    self.rotate_face(target.upper(), clockwise=clockwise)
                    self.rotate_slice("S", clockwise=clockwise)
                    continue
                raise ValueError(f"Invalid move {move} in sequence {sequence}")

    def __iter__(self):
        """
        Return an iterator for the cubies in the cube.
        """
        return iter(self.cubies)
