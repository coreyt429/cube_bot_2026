Cube Solver Bot (2026)

This repo tracks my 2026 rebuild of a Rubik's cube solving robot. In 2025 I built
https://www.rcr3d.com as an ROS2 learning project. The mechanics worked and the
solver logic was in place, but I stalled on computer vision. After a rough fall
shattered that robot, I started over with fresh parts and a new mechanical
layout.

Origins
- Base design: https://www.printables.com/model/17306-rubik-cube-solver-robot-v-shape
- Salvaged parts: Pololu Maestro Mini 12 + servos from the first cube_bot
- Replacement parts: https://www.thingiverse.com/thing:2800244
- New build: spare Raspberry Pi, new 3D printer, lots of filament

I redesigned the baseplate to fit my electronics and replaced a few missing
parts from the original project.

Status
Hardware
- Left gripper: assembled and tested, not mounted
- Right gripper: assembled, tested, mounted
- Camera: dry fit; waiting on a longer cable

Software
- Pi Zero: ground zero
- Pololu Maestro 12: validated previous configuration and tools
  - https://www.pololu.com/docs/0J40/3.b
- cube_bot.py: updated for new claw configuration; tested with calibrate.py
- arm.py: updated for new claw configuration; tested with calibrate.py
- calibrate.py: updated for new cube_bot.py and arm.py
- cube.py: unchanged
- maestro.py: unchanged
- solver.py: unchanged
- visualize.py: unchanged

Notes and Direction
The original project used a "human-like" solve approach. It was too slow on a
physical cube, so I added Kociemba for faster solutions. The old system kept
the physical cube and logical cube in sync via signal emits, so the on-screen
cube matched the real cube.

For this iteration, I am leaning toward a web-based interface for:
- Live camera view
- Manual arm control and calibration
- Cube motion control

This build also adds buttons and a small LCD for more hands-on control and
learning.
