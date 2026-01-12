import FreeCAD as App
import FreeCADGui as Gui
import Part

DOC_NAME = "pcb_end_clamp_v3"
doc = App.newDocument(DOC_NAME)

# -----------------------
# Known dimensions (mm)
# -----------------------
pcb_w   = 30.0 + 2.0    # nominal width + tolerance
pcb_t   = 1.5 - 0.1

# Screw pattern at ONE end (two screws at an end)
hole_spacing_tb = 21.5 + 0.5      # separation across PCB width direction
m3_clearance_d  = 3.2

# -----------------------
# Gap / overlap
# -----------------------
pcb_setback = 3.0 - 2.1     # <-- measure: screw-line to PCB edge (along length)
overlap_len = 10.0 - 4.0    # overlaps onto PCB
outer_lip   = 3.0           # extends outward beyond screw line

# -----------------------
# Clamp body
# -----------------------
side_margin = 4.0           # extra beyond PCB edge per side
clamp_thick = 3.0 + 2.0  # total thickness of clamp body

# Optional head relief
use_counterbore = True
cb_diameter     = 5.8
cb_depth        = 2.2


# Underside PCB locating step (a shallow pocket)
use_pcb_step   = True
step_clearance = 0.25       # extra clearance so it doesn't bind (0.2-0.4 is typical)
step_depth     = pcb_t + step_clearance   # pocket depth from underside
step_inset_x   = 0.6        # pocket narrower than PCB width so edges have strength
step_start_in  = 1.0        # start pocket this far INBOARD from PCB edge (prevents catching)

# Optional PCB corner locating pins (to engage the PCB's corner holes)
# Assumes corner hole centers are ~2mm from each PCB edge and ~2mm from the PCB end.
use_pcb_pins   = True
pin_d          = 1.5        # pin diameter (mm)
pin_h          = 1.2        # pin height below clamp underside (mm)
pin_edge_off   = 2.0  + 1.0      # distance from PCB edge to hole center (mm)

# Comfort
fillet_r = 1.0

# -----------------------
# Derived sizes
# -----------------------
clamp_w = pcb_w + 2.0 * side_margin
clamp_len = outer_lip + pcb_setback + overlap_len

# Coordinate convention:
# X: width, Y: outward->inward, Z: up
y_screw_line = outer_lip
y_pcb_edge   = outer_lip + pcb_setback

# Base plate
solid = Part.makeBox(clamp_w, clamp_len, clamp_thick)
solid.translate(App.Vector(-clamp_w/2.0, 0, 0))

# Screw holes
x1 = -hole_spacing_tb / 2.0
x2 =  hole_spacing_tb / 2.0
y_hole = y_screw_line

h1 = Part.makeCylinder(m3_clearance_d/2.0, clamp_thick + 1.0, App.Vector(x1, y_hole, -0.5))
h2 = Part.makeCylinder(m3_clearance_d/2.0, clamp_thick + 1.0, App.Vector(x2, y_hole, -0.5))
solid = solid.cut(h1).cut(h2)

if use_counterbore:
    cb1 = Part.makeCylinder(cb_diameter/2.0, cb_depth + 0.5,
                            App.Vector(x1, y_hole, clamp_thick - cb_depth))
    cb2 = Part.makeCylinder(cb_diameter/2.0, cb_depth + 0.5,
                            App.Vector(x2, y_hole, clamp_thick - cb_depth))
    solid = solid.cut(cb1).cut(cb2)


# PCB locating step (underside pocket)
if use_pcb_step:
    pocket_w = pcb_w - 2.0 * step_inset_x
    pocket_len = overlap_len - step_start_in
    if pocket_len > 0:
        pocket = Part.makeBox(pocket_w, pocket_len, step_depth)
        # center in X, and start pocket slightly inward from the PCB edge
        pocket.translate(App.Vector(-pocket_w/2.0, y_pcb_edge + step_start_in, -0.01))
        solid = solid.cut(pocket)
    else:
        App.Console.PrintWarning("Pocket skipped: overlap_len too small vs step_start_in\n")

# PCB corner locating pins (two pins for the two corners at this end)
# Pins are centered on the PCB rectangle: X spans width, Y spans length from the PCB edge inward.
if use_pcb_pins:
    # Corner holes near this end (the end under the clamp): at ~2mm from each PCB side and ~2mm from the PCB end edge
    x_pin_l = -(pcb_w / 2.0) + pin_edge_off
    x_pin_r =  (pcb_w / 2.0) - pin_edge_off
    y_pin   =  y_pcb_edge + pin_edge_off

    # Safety: only place pins if they land within the overlapped region
    if y_pin <= (y_pcb_edge + overlap_len):
        down = App.Vector(0, 0, 1)

        # If we have a PCB recess pocket, the "ceiling" of that pocket is at Z = step_depth.
        # Start the pin there so it appears inside the recess and extends downward through the opening.
        z_base = step_depth if use_pcb_step else 0.0
        pin_len = pin_h + (step_depth if use_pcb_step else 0.0)
        pin_len = clamp_thick
        z_base = 0.0

        p1 = Part.makeCylinder(pin_d / 2.0, pin_len, App.Vector(x_pin_l, y_pin, z_base), down)
        p2 = Part.makeCylinder(pin_d / 2.0, pin_len, App.Vector(x_pin_r, y_pin, z_base), down)
        solid = solid.fuse(p1).fuse(p2)
    else:
        App.Console.PrintWarning("Pins skipped: pin location beyond overlap_len; increase overlap_len or reduce pin_edge_off\n")

# Fillet (may fail if too aggressive)
if fillet_r > 0:
    try:
        solid = solid.makeFillet(fillet_r, solid.Edges)
    except Exception as e:
        App.Console.PrintWarning(f"Fillet skipped: {e}\n")

# Add to document
obj = doc.addObject("Part::Feature", "EndClamp")
obj.Shape = solid
doc.recompute()
Gui.ActiveDocument.ActiveView.fitAll()

print("Created:", DOC_NAME)
print(f"Clamp width:  {clamp_w} mm")
print(f"Clamp length: {clamp_len} mm  (outer_lip + pcb_setback + overlap_len)")
print(f"Screw line Y: {y_screw_line} mm")
print(f"PCB edge  Y:  {y_pcb_edge} mm")