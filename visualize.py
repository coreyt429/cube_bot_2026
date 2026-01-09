"""
module for visualizing puzzle cubes
"""

import logging

logger = logging.getLogger("visualize")

COLORS = {
    "K": "\033[0;30;40m",  # Black text on Black background (reset)
    "R": "\033[30;41m",  # Black text on Red background
    "Y": "\033[30;43m",  # Black text on Yellow background
    "G": "\033[30;42m",  # Black text on Green background
    "B": "\033[30;44m",  # Black text on Blue background
    "O": "\033[30;48;5;208m",  # Black text on Orange background
    "W": "\033[30;47m",  # Black text on White background
}
RESET = "\033[0m"
BLOCK = "  "


def state_string_to_cube(state_string):
    """
    utility function to convert a state string to a cube representation
    """
    if "0" in state_string:
        # states are two characters wide
        states = [state_string[i : i + 2] for i in range(0, len(state_string), 2)]
    else:
        # states are one character wide
        states = list(state_string)
    size = int((len(states) / 6) ** 0.5)
    cube = {}
    index = 0
    for face in "UDLRFB":
        cube[face] = {}
        for i in range(size):
            cube[face][i] = []
            for _ in range(size):
                cube[face][i].append(states[index])
                index += 1
    return cube


def state_string_to_rows(state_string):
    """
    utility function to convert a state string to a list of rows
    """
    if "0" in state_string:
        # states are two characters wide
        states = [state_string[i : i + 2] for i in range(0, len(state_string), 2)]
    else:
        # states are one character wide
        states = list(state_string)
    size = int((len(states) / 6) ** 0.5)
    cube = state_string_to_cube(state_string)
    blank = [["K0" for _ in range(size)] for _ in range(size)]
    rows = []
    for i in range(size):
        rows.append(blank[i] + cube["U"][i] + blank[i] + blank[i])
    for i in range(size):
        rows.append(cube["L"][i] + cube["F"][i] + cube["R"][i] + cube["B"][i])
    for i in range(size):
        rows.append(blank[i] + cube["D"][i] + blank[i] + blank[i])
    for row in rows:
        row_string = ""
        count = 0
        for square in row:
            count += 1
            color = COLORS[square[0]]
            if len(square) > 1:
                row_string += f"{color}{square}{RESET} "
            else:
                row_string += f"{color}{BLOCK}{RESET} "
            if count > 2:
                row_string += " "
                count = 0
    return rows


def color_cube(state_string):
    """
    Prints the cube in a formatted manner with colors.
    """
    if not isinstance(state_string, str):
        state_string = str(state_string)
    color_str = ""
    spacer = " " * 202
    for row in state_string_to_rows(state_string):
        row_string = ""
        count = 0
        for square in row:
            count += 1
            color = COLORS[square[0]]
            if len(square) > 1:
                row_string += f"{color}{square}{RESET} "
            else:
                row_string += f"{color}{BLOCK}{RESET} "
            if count > 2:
                row_string += " "
                count = 0
        logger.debug("Row Size: %d", len(row_string))
        color_str += row_string + f"\n{spacer}\n"
    return color_str


def print_color_cube(state_string):
    """
    Prints the cube in a formatted manner with colors.
    """
    print(color_cube(state_string))
