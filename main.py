"""
Main.py not used yet.
"""

from display import Display
from menu import Menu, Buttons
from cube_bot import CubeBot


def calibrate(display, buttons: Buttons, bot: CubeBot, arm_key: str, servo_key: str, position) -> None:
    """calibrate servo"""
    arm = bot.arms[arm_key]
    servo = arm.servos[servo_key]
    display.draw_message(
        "Calibrate",
        [
            f"Arm: {arm_key}",
            f"Servo: {servo_key}",
            f"Position: {position}",
            "",
            "Up: move -100 qus",
            "Down: move +100 qus",
            "Select: set position",
        ],
    )
    if servo_key == "rotate":
        arm.rotate(position)
    elif servo_key == "gripper":
        if position == "open":
            arm.open()
        elif position == "close":
            arm.close()
    while True:
        if buttons.wait(timeout=0.05):
            for ev in buttons.read_events():
                if ev.edge != "PRESS":
                    continue
                if ev.btn == "up":
                    current_qus = servo.qus
                    servo.set_qus(current_qus - 100, wait=True)
                elif ev.btn == "down":
                    current_qus = servo.qus
                    servo.set_qus(current_qus + 100, wait=True)
                elif ev.btn == "select":
                    calibrated_qus = int(getattr(servo, "qus", 0) or 0)
                    arm.cfg.qus[str(position)] = calibrated_qus
                    arm_cfg = bot.cfg.setdefault("arms", {}).setdefault(
                        arm.cfg.key, {}
                    )
                    arm_cfg.setdefault("qus", {})[str(position)] = calibrated_qus
                    arm_cfg["qus"]["state"] = str(position)
                    bot.save_config()
                    display.draw_message("Calibrate", ["Position set", "Exit"])
                    return
                display.draw_message(
                    "Calibrate",
                    [
                        f"Arm: {arm_key}",
                        f"Servo: {servo_key}",
                        f"Position: {position}",
                        f"Current qus: {servo.qus}",
                        "",
                        "Up: move -100 qus",
                        "Down: move +100 qus",
                        "Select: set position",
                    ],
                )

def load_cube(display, buttons: Buttons, bot: CubeBot) -> None:
    """Load cube into CubeBot"""
    bot.arms["l"].open()
    bot.arms["r"].open()
    display.draw_message("Load Cube", ["", "Up: close  Down: open", "Select: exit"])
    positions = []
    for arm in bot.arms.values():
        servo = arm.servos["open"]
        servo.set_qus(8000, wait=True)
        positions.append(servo.qus)
    while True:
        if buttons.wait(timeout=0.05):
            for ev in buttons.read_events():
                if ev.edge != "PRESS":
                    continue
                if ev.btn == "up":
                    positions.clear()
                    for arm in bot.arms.values():
                        servo = arm.servos["open"]
                        current_qus = servo.qus
                        servo.set_qus(current_qus - 100, wait=True)
                        positions.append(servo.qus)
                elif ev.btn == "down":
                    positions.clear()
                    for arm in bot.arms.values():
                        servo = arm.servos["open"]
                        current_qus = servo.qus
                        servo.set_qus(current_qus + 100, wait=True)
                        positions.append(servo.qus)
                elif ev.btn == "select":
                    for arm in bot.arms.values():
                        servo = arm.servos["open"]
                        closed_qus = int(getattr(servo, "qus", 0) or 0)
                        arm.cfg.qus["closed"] = closed_qus
                        arm_cfg = bot.cfg.setdefault("arms", {}).setdefault(
                            arm.cfg.key, {}
                        )
                        arm_cfg.setdefault("qus", {})["closed"] = closed_qus
                        arm_cfg["qus"]["state"] = "closed"
                    bot.save_config()
                    display.draw_message("Load Cube", ["Exit"])
                    return
                display.draw_message(
                    "Load Cube",
                    [str(positions), "Up: close  Down: open", "Select: exit"],
                )


def unload_cube(display, buttons: Buttons, bot: CubeBot) -> None:
    """Unload cube from CubeBot"""
    bot.arms["l"].open()
    bot.arms["r"].open()
    display.draw_message("Unload Cube", [""])


def main():
    """Main logic"""
    bot = CubeBot("calibration")
    menu_definition = [
        {
            "cube": {
                "load cube": {
                    "action": load_cube,
                    "parameters": [bot],
                },
                "unload cube": {
                    "action": unload_cube,
                    "parameters": [bot],
                },
            },
            "calibrate": {
                "left": {
                    "gripper": {
                        "open": {
                            "action": calibrate,
                            "parameters": [bot, "left", "gripper", "open"],
                        },
                        "close": {
                            "action": calibrate,
                            "parameters": [bot, "left", "gripper", "close"],
                        },
                    },
                    "rotate": {
                        "0 deg": {
                            "action": calibrate,
                            "parameters": [bot, "left", "rotate", 0],
                        },
                        "90 deg": {
                            "action": calibrate,
                            "parameters": [bot, "left", "rotate", 90],
                        },
                        "180 deg": {
                            "action": calibrate,
                            "parameters": [bot, "left", "rotate", 180],
                        },
                        "270 deg": {
                            "action": calibrate,
                            "parameters": [bot, "left", "rotate", 270],
                        },
                    },
                },
                "right": {
                    "gripper": {
                        "open": {
                            "action": calibrate,
                            "parameters": [bot, "right", "gripper", "open"],
                        },
                        "close": {
                            "action": calibrate,
                            "parameters": [bot, "right", "gripper", "close"],
                        },
                    },
                    "rotate": {
                        "0 deg": {
                            "action": calibrate,
                            "parameters": [bot, "right", "rotate", 0],
                        },
                        "90 deg": {
                            "action": calibrate,
                            "parameters": [bot, "right", "rotate", 90],
                        },
                        "180 deg": {
                            "action": calibrate,
                            "parameters": [bot, "right", "rotate", 180],
                        },
                        "270 deg": {
                            "action": calibrate,
                            "parameters": [bot, "right", "rotate", 270],
                        },
                    },
                },
            },
        }
    ]

    display = Display()
    menu = Menu(display=display, menu_definition=menu_definition, title="CubeBot")
    menu.run()


if __name__ == "__main__":
    main()
