import logging
from time import sleep

from cube_bot import CubeBot
from maestro import Servo
from arm import Arm

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("calibrate")
logger.setLevel(logging.DEBUG)

def up(bot, clockwise=True):
    """Move up surface clockwise"""
    bot.arms['r'].open()
    bot.arms['l'].rotate(180)
    bot.arms['r'].close()
    if clockwise:
        bot.arms['r'].rotate(90)
    else:
        bot.arms['r'].rotate(-90)
    bot.arms['r'].open()
    bot.arms['l'].rotate(-180)


if __name__ == "__main__":
    bot = CubeBot("calibration")
    up(bot)
    sleep(10)
    up(bot, clockwise=False)   