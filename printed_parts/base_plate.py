"""
FreeCad script to create a base plate with a pocket and standoffs for a
Raspberry Pi Zero and Pololu Maestro mini 12-channel servo controller.

The base plate from the original project seemed to fit a full size Pi and
a different servo controller, so I created this one to better fit my
components.
"""

import FreeCAD as App
import FreeCADGui as Gui
import Part
import ScrewMaker  # from Fasteners WB

# ---- Parameters ----
W_OUT = 139.75  # outer width  (X)
H_OUT = 91.5  # outer height (Y)
T_OUT = 5.0  # plate thickness (Z)

W_IN = W_OUT - 24  # inner pocket width  (X)
H_IN = 55.0  # inner pocket height (Y)
DEPTH = 2.0  # pocket depth

DX = 12.0  # offset from outer upper-right in X
DY = 15.0  # offset from outer upper-right in Y

# Pi Zero (or your PCB) hole rectangle, relative to the first spacer
PCB_DX = 58.0  # X distance between left/right holes
PCB_DY = 23.0  # Y distance between top/bottom holes

# First spacer position on the pocket face (local XY of that face)
SPACER_X0 = 60.0
SPACER_Y0 = 65.0

SPACER_DIAM = "M2.5"
SPACER_LEN = "5"  # 5 mm tall standoff


SPACER_BODY_D = 5.0  # outer diameter of standoff (mm)
SPACER_HOLE_D = 2.5  # clearance/tap hole for M2.5 (tweak as needed)
SPACER_H = 5.0  # standoff height (mm) – same as SPACER_LEN logically

# Mounting screw parameters (M3 socket head coming from bottom)
SCREW_D = 3.5  # screw shank diameter
SCREW_HEAD_D = 6  # screw head diameter
SCREW_HEAD_H = 3.0  # screw head height (counterbore depth)

# ---- Derived positions for pocket box ----
x0 = W_OUT - DX - W_IN  # lower-left X of pocket box
y0 = H_OUT - DY - H_IN  # lower-left Y of pocket box
z0 = T_OUT - DEPTH  # lower Z of pocket box


# ---------------------------------------------------------------------------
# Helper: make a spacer (standoff) at a given XY, on the pocket floor
# ---------------------------------------------------------------------------
SPACER_Z = z0  # sit on the pocket floor


def make_spacer(name, x, y):
    # Outer cylinder
    outer = doc.addObject("Part::Cylinder", name + "_outer")
    outer.Radius = SPACER_BODY_D / 2.0
    outer.Height = SPACER_H
    outer.Placement = App.Placement(
        App.Vector(x, y, SPACER_Z), App.Rotation(0, 0, 0, 1)
    )

    # Inner cylinder (hole)
    inner = doc.addObject("Part::Cylinder", name + "_hole")
    inner.Radius = SPACER_HOLE_D / 2.0
    inner.Height = SPACER_H
    inner.Placement = App.Placement(
        App.Vector(x, y, SPACER_Z), App.Rotation(0, 0, 0, 1)
    )

    # Cut hole from body
    spacer = doc.addObject("Part::Cut", name)
    spacer.Base = outer
    spacer.Tool = inner

    # Hide construction solids
    outer.ViewObject.Visibility = False
    inner.ViewObject.Visibility = False

    return spacer


# ---------------------------------------------------------------------------
# Create geometry
# ---------------------------------------------------------------------------
doc = App.newDocument("BasePlatePocket")

# Outer plate as a box
outer = doc.addObject("Part::Box", "BasePlate")
outer.Length = W_OUT  # X
outer.Width = H_OUT  # Y
outer.Height = T_OUT  # Z
outer.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(0, 0, 0, 1))

# Pocket as a smaller box
pocket = doc.addObject("Part::Box", "Pocket")
pocket.Length = W_IN
pocket.Width = H_IN
pocket.Height = DEPTH
pocket.Placement = App.Placement(App.Vector(x0, y0, z0), App.Rotation(0, 0, 0, 1))

# Cut the pocket out of the plate
cut = doc.addObject("Part::Cut", "BaseWithPocket")
cut.Base = outer
cut.Tool = pocket

# Hide the intermediate solids
outer.ViewObject.Visibility = False
pocket.ViewObject.Visibility = False

doc.recompute()


# ---------------------------------------------------------------------------
# Helper: find the pocket floor face on BaseWithPocket
# ---------------------------------------------------------------------------
def find_pocket_floor_face(obj):
    """Return face name (e.g. 'Face11') for the pocket floor."""
    target_area = W_IN * H_IN
    for i, f in enumerate(obj.Shape.Faces):
        if abs(f.Area - target_area) < 1e-3:
            return f"Face{i + 1}"
    raise RuntimeError("Pocket floor face not found; check geometry / dimensions.")


pocket_face_name = find_pocket_floor_face(cut)


# ---------------------------------------------------------------------------
# Create four spacers for the Pi Zero corners
# SPACER_X0 / SPACER_Y0 is the first corner; others are offset by PCB_DX / PCB_DY
# ---------------------------------------------------------------------------
spacer_FL = make_spacer("Spacer_PiZero_FL", SPACER_X0, SPACER_Y0)
spacer_FR = make_spacer("Spacer_PiZero_FR", SPACER_X0 + PCB_DX, SPACER_Y0)
spacer_RL = make_spacer("Spacer_PiZero_RL", SPACER_X0, SPACER_Y0 - PCB_DY)
spacer_RR = make_spacer("Spacer_PiZero_RR", SPACER_X0 + PCB_DX, SPACER_Y0 - PCB_DY)
spacer_m_1 = make_spacer("Spacer_Maestro_1", SPACER_X0 - 20, SPACER_Y0)
spacer_m_2 = make_spacer("Spacer_Maestro_2", SPACER_X0 - 32, SPACER_Y0 - 30.5)


# ---------------------------------------------------------------------------
# Create mounting screw holes: M3 socket head from bottom
# Four holes: two near top edge, two near bottom edge
# Top pair: 5 mm from top edge, 5 mm from left/right edges
# Bottom pair: 5 mm from bottom edge, 25 mm from left/right edges
# ---------------------------------------------------------------------------

# Define XY centers of the four mount holes in plate coordinates
mount_hole_coords = [
    (5.0, H_OUT - 5.0),  # top-left
    (W_OUT - 5.0, H_OUT - 5.0),  # top-right
    (25.0, 5.0),  # bottom-left
    (W_OUT - 25.0, 5.0),  # bottom-right
]

mount_hole_fuses = []

for idx, (hx, hy) in enumerate(mount_hole_coords, start=1):
    # Through-hole for the screw shank
    shank = doc.addObject("Part::Cylinder", f"MountHole{idx}_shank")
    shank.Radius = SCREW_D / 2.0
    shank.Height = T_OUT
    shank.Placement = App.Placement(App.Vector(hx, hy, 0.0), App.Rotation(0, 0, 0, 1))

    # Counterbore for the screw head (socket head), from bottom
    head = doc.addObject("Part::Cylinder", f"MountHole{idx}_head")
    head.Radius = SCREW_HEAD_D / 2.0
    head.Height = SCREW_HEAD_H
    head.Placement = App.Placement(App.Vector(hx, hy, 0.0), App.Rotation(0, 0, 0, 1))

    # Fuse shank and head into a single cutting tool
    fuse = doc.addObject("Part::MultiFuse", f"MountHole{idx}")
    fuse.Shapes = [shank, head]

    # Hide construction shapes
    shank.ViewObject.Visibility = False
    head.ViewObject.Visibility = False

    mount_hole_fuses.append(fuse)

# Fuse all mount hole tools into one
if len(mount_hole_fuses) == 1:
    all_mount_holes = mount_hole_fuses[0]
else:
    all_mount_holes = doc.addObject("Part::MultiFuse", "MountHoles")
    all_mount_holes.Shapes = mount_hole_fuses
    for f in mount_hole_fuses:
        f.ViewObject.Visibility = False

# Cut the mounting holes out of the base plate with pocket
base_with_pocket_and_holes = doc.addObject("Part::Cut", "BaseWithPocketAndHoles")
base_with_pocket_and_holes.Base = cut
base_with_pocket_and_holes.Tool = all_mount_holes

# Hide intermediate base shape and hole tools
cut.ViewObject.Visibility = False
all_mount_holes.ViewObject.Visibility = False


from BOPTools import BOPFeatures

bp = BOPFeatures.BOPFeatures(doc)
bp.make_multi_fuse(
    [
        "Spacer_PiZero_FL",
        "Spacer_PiZero_FR",
        "Spacer_PiZero_RL",
        "Spacer_PiZero_RR",
        "Spacer_Maestro_1",
        "Spacer_Maestro_2",
        "BaseWithPocketAndHoles",
    ]
)
doc.recompute()

__objs__ = []
__objs__.append(doc.getObject("Fusion"))
import Mesh

if hasattr(Mesh, "exportOptions"):
    options = Mesh.exportOptions(f"/Users/coreyt/Downloads/{doc.Name}-Fusion.3mf")
    Mesh.export(__objs__, f"/Users/coreyt/Downloads/{doc.Name}-Fusion.3mf", options)
else:
    Mesh.export(__objs__, f"/Users/coreyt/Downloads/{doc.Name}-Fusion.3mf")

del __objs__

Gui.SendMsgToActiveView("ViewFit")
Gui.activeDocument().activeView().viewTop()
