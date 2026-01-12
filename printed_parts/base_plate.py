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

# Shift ONLY the Pi Zero standoffs left/right without moving the Maestro posts
# (negative moves left)
PI_ZERO_SHIFT_X = -3.0  # mm; tweak as needed

# ---------------------------------------------------------------------------
# Power connector holder (DC barrel -> screw terminal adapter)
# Positioned relative to the BOTTOM-RIGHT M3 mounting hole (MountHole4)
# ---------------------------------------------------------------------------
#
# NOTE: This is the black-body CENTER offset. With the holder wall + black-body half-depth,
# 9mm was too tight; 17mm yields ~5mm+ clearance from the MountHole4 center in X.
CONN_OFFSET_X_FROM_BR_M3 = 17.0  # mm
CONN_OFFSET_Y_FROM_BR_M3 = 0.0  # mm (same Y as BR M3 hole by default)

#
# Connector geometry (mm)
CONN_BLACK_W = 14.5   # width of the rectangular black block
CONN_BLACK_D = 13.0   # depth of the rectangular black block (along X for our holder)
CONN_TOTAL_LEN = 32.5 # black+silver overall length (informational)

# Derived length of the metal barrel portion that protrudes from the black block
CONN_METAL_LEN = CONN_TOTAL_LEN - CONN_BLACK_D  # ~19.5mm with your dims

# When True, we place the connector center along the diagonal from Pi RR to the plate corner
# while still honoring the required +X offset. This tends to land it "between" the hole and corner.
CONN_PLACE_ALONG_DIAGONAL_TO_CORNER = False

# Green terminal block geometry (mm)
CONN_GREEN_W = 10.0
CONN_GREEN_H = 10.0
CONN_GREEN_PROTRUDE = 5.0  # sticks out from the back of the black part

# Holder geometry (mm)
CONN_WALL = 2.0       # wall thickness around the cavity
CONN_FLOOR = 2.0      # floor thickness under the connector
CONN_LIP = 1.5        # small retaining lip over the top edge
CONN_LIP_TAB_W = 3.0   # width (in Y) of each retaining tab; leaves the top mostly open
CONN_CLEAR = 0.35     # clearance around the connector so it slides in
CONN_HOLDER_Z = 16.0  # overall holder height above the plate

# Placement constraint: keep metal end flush with edge or <= 5mm beyond.
# We approximate this by keeping the FRONT face of the black block at/before the edge.
CONN_MAX_METAL_PROTRUDE = 5.0

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
# Helper: make a connector holder (cradle) for the DC barrel -> screw terminal adapter
# The adapter sits "on its side" with the green block facing inward (toward -X).
# We model a simple pocketed block with a top lip and a side window.
# ---------------------------------------------------------------------------

def make_power_connector_holder(name, barrel_center_x, barrel_center_y):
    """Create a simple guide for the connector: two side walls and a small back-stop bump.

    The connector slides in from the FRONT edge (Y=0). We do NOT create a full box; the top and most sides
    are open so assembly is easier.

    Requirements implemented:
      - Only short walls on the left/right of the connector
      - Both walls shifted 4mm to the LEFT of their previous position (negative X)
      - Right wall height ~3mm; left wall stays tall
      - A 1–2mm stop/bump wall at Y=27.25mm from the front edge to prevent pushing the connector too far back
    """

    def _mm(v):
        """Return a float in mm from either a float/int or a FreeCAD Quantity."""
        try:
            return float(v)
        except Exception:
            try:
                return float(v.Value)
            except Exception:
                return float(App.Units.Quantity(v).Value)

    barrel_center_x = _mm(barrel_center_x)
    barrel_center_y = _mm(barrel_center_y)

    # Normalize constants to floats (mm)
    CONN_BLACK_D_F = float(_mm(CONN_BLACK_D))
    CONN_BLACK_W_F = float(_mm(CONN_BLACK_W))
    CONN_WALL_F = float(_mm(CONN_WALL))
    CONN_CLEAR_F = float(_mm(CONN_CLEAR))
    CONN_HOLDER_Z_F = float(_mm(CONN_HOLDER_Z))

    # Treat the black rectangular block as the part we guide.
    # X = depth direction (toward plate edge), Y = width direction, Z = height.
    black_dx = CONN_BLACK_D_F
    black_dy = CONN_BLACK_W_F

    # Channel dimensions (outer envelope of the side walls)
    outer_dx = black_dx + 2.0 * CONN_WALL_F
    outer_dy = black_dy + 2.0 * CONN_WALL_F

    # Interpret inputs as CENTER of the BLACK BODY in XY.
    black_cx = float(barrel_center_x)
    black_front_x = black_cx + (black_dx / 2.0)
    black_back_x = black_cx - (black_dx / 2.0)

    # Wall base placement
    # Align to FRONT edge and shift walls 4mm LEFT in X (negative X).
    SHIFT_X = 4.0
    outer_x = (black_back_x - CONN_WALL_F) - SHIFT_X
    outer_y = 0.0
    # Build the holder on top of the plate
    outer_z = float(_mm(T_OUT))

    # Left wall: tall
    left_wall = doc.addObject("Part::Box", name + "_left_wall")
    # LEFT wall runs along Y; thin in X
    left_wall.Length = CONN_WALL_F           # X thickness
    # Shorten by 12mm and set back 12mm from the front edge
    left_wall.Width = max(0.0, outer_dy - 12.0)  # Y span
    left_wall.Height = 3.0 # <-- was CONN_HOLDER_Z_F
    left_wall.Placement = App.Placement(
        App.Vector(outer_x - 3.0, outer_y + 13.0, outer_z),
        App.Rotation(0, 0, 0, 1),
    )

    # Right wall: short (~3mm tall)
    right_wall = doc.addObject("Part::Box", name + "_right_wall")
    # RIGHT wall runs along Y; thin in X
    right_wall.Length = CONN_WALL_F          # X thickness
    right_wall.Width = outer_dy              # Y span
    right_wall.Height = 3.0
    right_wall.Placement = App.Placement(
        App.Vector(outer_x + outer_dx - CONN_WALL_F, outer_y + 10, outer_z),
        App.Rotation(0, 0, 0, 1),
    )

    # Back-stop bump wall: small ridge at a fixed Y from the front edge.
    # This prevents the connector from being pushed too far back (+Y).
    # Back-stop bump wall: small ridge at a fixed Y from the front edge.
    stop_y = 28.25
    stop_thickness = 2.0
    stop_height = 2.0

    pocket_floor_z = float(_mm(z0))           # z0 is pocket floor (global)
    span_down = float(_mm(T_OUT)) - pocket_floor_z

    back_stop = doc.addObject("Part::Box", name + "_back_stop")
    back_stop.Length = outer_dx
    back_stop.Width = stop_thickness
    back_stop.Height = stop_height + span_down   # extend down through the recess
    back_stop.Placement = App.Placement(
        App.Vector(outer_x, stop_y, pocket_floor_z),  # start at pocket floor
        App.Rotation(0, 0, 0, 1),
    )

    # Front support wall: small bump to support the barrel connector
    # 2mm tall, 4mm long (X), centered between left/right walls, set back 3mm from front edge
    front_y = 3.0
    front_thickness = 2.0  # Y thickness
    front_len_x = 4.0      # X length
    front_height = 1.0     # Z height

    left_inner_x = (outer_x - 2.0) + CONN_WALL_F
    right_inner_x = (outer_x + outer_dx - CONN_WALL_F)
    front_center_x = 0.5 * (left_inner_x + right_inner_x)
    front_x = front_center_x - (front_len_x / 2.0)

    front_stop = doc.addObject("Part::Box", name + "_front_stop")
    front_stop.Length = front_len_x
    front_stop.Width = front_thickness
    front_stop.Height = front_height
    front_stop.Placement = App.Placement(
        App.Vector(front_x, front_y, outer_z),
        App.Rotation(0, 0, 0, 1),
    )

    # Fuse the three solids into one stable shape
    walls = doc.addObject("Part::MultiFuse", name + "_walls")
    walls.Shapes = [left_wall, right_wall, back_stop, front_stop]

    doc.recompute()

    # Freeze into a plain feature for robustness in later fuses
    holder_solid = doc.addObject("Part::Feature", name + "_solid")
    holder_solid.Shape = walls.Shape

    # Hide construction solids
    left_wall.ViewObject.Visibility = False
    right_wall.ViewObject.Visibility = False
    back_stop.ViewObject.Visibility = False
    front_stop.ViewObject.Visibility = False
    walls.ViewObject.Visibility = False

    return holder_solid



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
# Pi Zero standoffs (shiftable in X)
pi_x0 = SPACER_X0 + PI_ZERO_SHIFT_X
pi_y0 = SPACER_Y0

spacer_FL = make_spacer("Spacer_PiZero_FL", pi_x0, pi_y0)
spacer_FR = make_spacer("Spacer_PiZero_FR", pi_x0 + PCB_DX, pi_y0)
spacer_RL = make_spacer("Spacer_PiZero_RL", pi_x0, pi_y0 - PCB_DY)
spacer_RR = make_spacer("Spacer_PiZero_RR", pi_x0 + PCB_DX, pi_y0 - PCB_DY)
spacer_m_1 = make_spacer("Spacer_Maestro_1", SPACER_X0 - 20, SPACER_Y0)
spacer_m_2 = make_spacer("Spacer_Maestro_2", SPACER_X0 - 32, SPACER_Y0 - 30.5)

# ---------------------------------------------------------------------------
# Power connector holder placement
# Reference: BOTTOM-RIGHT M3 mounting hole (MountHole4)
# ---------------------------------------------------------------------------
br_m3_x = W_OUT - 25.0
br_m3_y = 5.0

# User intent: CENTER of the black body ~ offset to the right (+X) of the BR M3 hole
conn_center_x = br_m3_x + CONN_OFFSET_X_FROM_BR_M3
# Align holder to FRONT edge (Y=0) so connector slides in from the front
conn_outer_dy = (CONN_BLACK_W + 2.0 * CONN_WALL)
conn_center_y = (conn_outer_dy / 2.0) + CONN_OFFSET_Y_FROM_BR_M3

# NOTE: We intentionally do NOT apply the diagonal-to-corner logic here.
# The holder is front-aligned (Y=0) so the connector can slide in from the front.
power_conn_holder = make_power_connector_holder("PowerConnHolder", conn_center_x, conn_center_y)


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

# Make sure all upstream shapes are computed before final booleans
base_with_pocket_and_holes.ViewObject.Visibility = False
for f in mount_hole_fuses:
    f.ViewObject.Visibility = False

doc.recompute()

# ---------------------------------------------------------------------------
# Final boolean: fuse add-ons (standoffs + connector holder) onto the base
# Using Part::MultiFuse + Part::Fuse avoids BOPTools failures.
# ---------------------------------------------------------------------------
addons = doc.addObject("Part::MultiFuse", "AddOns")
# Build a safe list of addon solids (filter out null/invalid shapes)
_addon_candidates = [
    spacer_FL,
    spacer_FR,
    spacer_RL,
    spacer_RR,
    spacer_m_1,
    spacer_m_2,
    power_conn_holder,
]

_addons_ok = []
for o in _addon_candidates:
    try:
        if o is None:
            continue
        if not hasattr(o, "Shape"):
            continue
        if o.Shape.isNull():
            App.Console.PrintError(f"AddOn shape is NULL: {o.Name}\n")
            continue
        # OCC validity can be expensive; only warn, don't block.
        if hasattr(o.Shape, "isValid") and not o.Shape.isValid():
            App.Console.PrintError(f"AddOn shape INVALID: {o.Name}\n")
        _addons_ok.append(o)
    except Exception as e:
        App.Console.PrintError(f"AddOn inspection failed for {getattr(o,'Name','<unknown>')}: {e}\n")

# MultiFuse needs at least 2 shapes; handle 0/1 gracefully.
if len(_addons_ok) == 0:
    App.Console.PrintError("No valid add-on shapes; skipping AddOns fuse.\n")
    addons.Shapes = []
elif len(_addons_ok) == 1:
    addons.Shapes = _addons_ok
else:
    addons.Shapes = _addons_ok

doc.recompute()

final_fuse = doc.addObject("Part::Fuse", "Final")
final_fuse.Base = base_with_pocket_and_holes
final_fuse.Tool = addons

doc.recompute()

# Refine (remove splitter edges) into a clean exportable solid
final_refined = doc.addObject("Part::Feature", "FinalRefined")
final_refined.Shape = final_fuse.Shape.removeSplitter()

# Validate final shape before export
if final_refined.Shape.isNull():
    raise RuntimeError("FinalRefined shape is NULL (Final fuse likely failed). See Report view for which add-on is null/invalid.")
# if hasattr(final_refined.Shape, "isValid") and not final_refined.Shape.isValid():
#     App.Console.PrintError("WARNING: FinalRefined shape is invalid; export may fail.\n")

doc.recompute()

# Hide everything except the refined final
for obj in doc.Objects:
    if hasattr(obj, "ViewObject"):
        obj.ViewObject.Visibility = False

final_refined.ViewObject.Visibility = True
final_refined.ViewObject.DisplayMode = "Shaded"



__objs__ = []
__objs__.append(doc.getObject("FinalRefined"))
import Mesh

if hasattr(Mesh, "exportOptions"):
    options = Mesh.exportOptions(f"/Users/coreyt/Downloads/{doc.Name}-FinalRefined.3mf")
    Mesh.export(__objs__, f"/Users/coreyt/Downloads/{doc.Name}-FinalRefined.3mf", options)
else:
    Mesh.export(__objs__, f"/Users/coreyt/Downloads/{doc.Name}-FinalRefined.3mf")

del __objs__

Gui.SendMsgToActiveView("ViewFit")
Gui.activeDocument().activeView().viewIsometric()
