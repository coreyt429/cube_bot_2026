"""Tests for the CubeBot arm."""

import unittest

from arm import Arm, ArmConfig


class FakeController:
    """Minimal Maestro replacement used by the arm and its servos."""

    def __init__(self):
        self.targets = []

    def set_limits(self, **_kwargs):
        pass

    def set_speed(self, **_kwargs):
        pass

    def set_accel(self, **_kwargs):
        pass

    def set_target_qus(self, **kwargs):
        self.targets.append(kwargs)

    def wait(self):
        pass


class ArmPositionTest(unittest.TestCase):
    def setUp(self):
        self.controller = FakeController()
        self.arm = Arm(controller=self.controller, cfg=ArmConfig())

    def test_gripper_position_tracks_open_and_close(self):
        self.assertEqual(self.arm.gripper_position, "open")

        self.arm.close(wait=False)
        self.assertEqual(self.arm.gripper_position, "close")

        self.arm.open(wait=False)
        self.assertEqual(self.arm.gripper_position, "open")

    def test_rotation_position_rounds_servo_degrees_to_nearest_90(self):
        positions = {
            0: 0,
            44: 0,
            46: 90,
            134: 90,
            136: 180,
            224: 180,
            226: 270,
            270: 270,
        }
        for servo_degrees, expected in positions.items():
            with self.subTest(servo_degrees=servo_degrees):
                self.arm.servos["rotate"].deg = servo_degrees
                self.assertEqual(self.arm.rotation_position, expected)

    def test_set_degrees_skips_move_when_already_at_position(self):
        self.arm.servos["rotate"].deg = 91
        self.controller.targets.clear()

        self.arm.set_degrees(90)

        self.assertEqual(self.controller.targets, [])

    def test_reset_skips_moves_when_already_closed_at_position(self):
        self.arm.servos["rotate"].deg = 179
        self.arm.extended = False
        self.controller.targets.clear()

        self.arm.reset(degrees=180)

        self.assertEqual(self.controller.targets, [])

    def test_reset_only_closes_when_open_at_desired_position(self):
        self.arm.servos["rotate"].deg = 179
        self.controller.targets.clear()

        self.arm.reset(degrees=180, wait=False)

        self.assertEqual(len(self.controller.targets), 1)
        self.assertEqual(
            self.controller.targets[0]["channel"], self.arm.cfg.open_channel
        )
        self.assertEqual(self.arm.gripper_position, "close")

    def test_reset_does_not_reopen_an_open_gripper(self):
        self.arm.servos["rotate"].deg = 0
        self.controller.targets.clear()

        self.arm.reset(degrees=180, wait=False)

        target_channels = [target["channel"] for target in self.controller.targets]
        self.assertEqual(
            target_channels,
            [self.arm.cfg.rotate_channel, self.arm.cfg.open_channel],
        )


if __name__ == "__main__":
    unittest.main()
