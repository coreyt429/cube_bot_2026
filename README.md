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
- Left gripper: assembled and tested, mounted
- Right gripper: assembled, tested, mounted
- Camera: mounted and tested
- buttons and screen: affixed to PCB and tested
- final assembly: complete

Software
- Pi Zero: 
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


Updates
20260113
  - Testing hardware now.  I can move to final assembly once I have a longer camera cable.
  - Testing motion, a lot of my previous work will translate. I'm finding that the claws
    are a danger to each other with or without the cube. Bot will need to be aware of
    and orchestrate arms to avoid disaster.  I may also need to use the camera to detect
    bad cube alignment.
  - baseplate redesigned again to allow more headroom for wiring.
  - Next steps:
    - final assembly
    - cube loading process
    - basic cube moves U, D, L, R, F, B

20260119
  - Hardware assembled.
  - scrapped uv for pi side python.  Too many issues working with buttons and cam, and the OS python seems sufficient.
  - calibration and rudimentary tests for display, buttons, and cam passed
  - Next Steps:
    - cube loading process:
      - use buttons and display
      - user experience:
        - select load menu
        - grippers open then close slightly to approximate cube size
        - user uses up and down buttons to adjust grip
        - user presses select to continue
    - calibration:
      - menu tree:
        - Left/Right:
          - Gripper:
             - Open
             - Close
          - Rotation:
            - 0
            - 90
            - 180
            - 270
      - user experience:
        - user navigates the menu to select the postion that need adjusting
        - user uses up and down buttons to adjust position
        - user uses select button to save and go back to the menu
    - basic cube moves U, D, L, R, F, B      

