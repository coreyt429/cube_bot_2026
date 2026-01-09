"""
Module to solve a rubiks cube puzzle
"""

import logging
import kociemba

# from random import choice, randint
from cube import Cube


class Solver:
    """
    Class to solve a rubiks cube puzzle
    """

    def __init__(self, cube=None):
        """
        Initialize the solver with a cube
        """
        if cube is None:
            cube = Cube(size=3)
        if not isinstance(cube, Cube):
            raise TypeError("cube must be a Cube")
        self.cube = cube

    def orient_cube(self):
        """
        Orient the cube to a standard position
        """
        move_map = {
            "W": {
                "U": (),
                "L": ({"axis": "z", "clockwise": True},),
                "R": ({"axis": "z", "clockwise": False},),
                "F": ({"axis": "x", "clockwise": True},),
                "B": ({"axis": "x", "clockwise": False},),
                "D": (
                    {"axis": "x", "clockwise": True},
                    {"axis": "x", "clockwise": True},
                ),
            },
            "R": {
                "U": (),
                "L": ({"axis": "y", "clockwise": False},),
                "R": ({"axis": "y", "clockwise": True},),
                "F": (),
                "B": (
                    {"axis": "y", "clockwise": True},
                    {"axis": "y", "clockwise": True},
                ),
                "D": (),
            },
        }

        # Find the white center and orient it to the top
        for color in ["W", "R"]:
            center = self.cube.centers(color_filter=[color])[0]
            start_position = center.position
            for move in move_map[color][start_position]:
                self.cube.rotate_cube(**move)

    def kociemba(self):
        """
        Get the Kociemba state representation of the cube.
        """
        kociemba_solution = kociemba.solve(self.cube.kociemba_state)
        logging.info("Kociemba solution found: %s", kociemba_solution)
        self.cube.sequence(kociemba_solution)

    def invert_cube(self):
        """
        Flip the cube upside down (yellow up)
        """
        logging.debug("Inverting the cube")
        self.orient_cube()
        self.cube.rotate_cube(axis="x", clockwise=True)
        self.cube.rotate_cube(axis="x", clockwise=True)

    def count_edge_faces(self, edges):
        """
        Count the number of edges with a specific color
        """
        counts = {
            "U": 0,
            "D": 0,
            "L": 0,
            "R": 0,
            "F": 0,
            "B": 0,
        }
        for edge in edges:
            counts[edge.position[edge.orientation]] += 1
        return counts

    def solve(self):
        """
        Solve the cube
        """
        # Implement the solving algorithm here
        self.kociemba()


if __name__ == "__main__":
    print("Run test_solver.py to test the solver")
