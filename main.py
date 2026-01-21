"""
Main.py not used yet.
"""
from display import Display
from menu import Menu, MenuItem
from cube_bot import CubeBot

def load_cube(bot: CubeBot) -> None:
    """Load cube into CubeBot"""
    bot.arms['l'].open()
    bot.arms['r'].open()
    input("Place the cube in the holder and press Enter to continue...")
    bot.arms['l'].close()
    bot.arms['r'].close()


def main():
    """Main logic"""
    bot = CubeBot("calibration")
    menu_definition = [
        {
            "load cube": {
                "action": load_cube,
                "parameters": [bot],
            }
        },
    ]

    display = Display()
    menu = Menu(display=display, menu_definition=menu_definition, title="CubeBot")
    menu.run()



if __name__ == "__main__":
    main()
