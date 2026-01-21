"""
Main.py not used yet.
"""
from display import Display
from menu import Menu, Buttons
from cube_bot import CubeBot

def load_cube(display, buttons: Buttons, bot: CubeBot) -> None:
    """Load cube into CubeBot"""
    bot.arms['l'].open()
    bot.arms['r'].open()
    display.draw_message("Load Cube", ['', "Up: close  Down: open", "Select: exit"])

    while True:
        if buttons.wait(timeout=0.05):
            for ev in buttons.read_events():
                if ev.edge != "PRESS":
                    continue
                if ev.btn == "up":
                    for arm in bot.arms.values():
                        servo = arm.servos['open']
                        current_qus = servo.qus
                        servo.set_qus(current_qus + 4, wait=True)
                elif ev.btn == "down":
                    for arm in bot.arms.values():
                        servo = arm.servos['open']
                        current_qus = servo.qus
                        servo.set_qus(current_qus - 4, wait=True)
                elif ev.btn == "select":
                    display.draw_message("Load Cube", ["Exit"])
                    return

                display.draw_message("Load Cube", ['', "Up: close  Down: open", "Select: exit"])

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
