import FreeCAD as App
import Import
import Part
import os


# =========================
# Parametric dimensions (mm)
# =========================
# Official outside dimensions for the Lian Li / DAN A3-mATX are 443 D x 194 W.
# These are only used to create sane baseline lengths; measure your real gap
# before treating this as a finished fit.
case_depth = 443.0
case_width = 194.0

# Gap filler cross-section.
gap_height = 11.0
gap_depth = 12.0
top_flange_thickness = 1.8
top_flange_outer_lip = 2.5
top_flange_inner_lip = 3.0
retention_rib_height = 2.0
retention_rib_width = 2.2

# Length controls. Margins keep the baseline away from rounded panel corners.
side_length = case_depth - 64.0
front_rear_length = case_width - 44.0
end_margin = 0.0

# Simple clip/latch reliefs along each strip. Set the lists empty once you want
# uninterrupted bars, or tune the positions/widths for the real case latches.
side_latch_relief_positions = [58.0, 188.0, 318.0]
front_rear_latch_relief_positions = [42.0, 108.0]
latch_relief_width = 18.0
latch_relief_extra_depth = 0.8

# Fit/print controls.
round_edges = True
edge_radius = 0.8
export_basename = "A3RoofGapFillers"
run_exports_in_cli = True

# Arrangement in the FreeCAD document.
preview_spacing = 18.0


# =========================
# Geometry helpers
# =========================
def make_box(x, y, z, width, depth, height):
    return Part.makeBox(width, depth, height, App.Vector(x, y, z))


def make_linear_filler(length, latch_relief_positions):
    usable_length = max(1.0, length - (2.0 * end_margin))
    y0 = top_flange_outer_lip

    body = make_box(
        end_margin,
        y0,
        0.0,
        usable_length,
        gap_depth,
        gap_height,
    )
    top_flange = make_box(
        end_margin,
        0.0,
        gap_height - top_flange_thickness,
        usable_length,
        top_flange_outer_lip + gap_depth + top_flange_inner_lip,
        top_flange_thickness,
    )
    retention_rib = make_box(
        end_margin,
        y0 + gap_depth - retention_rib_width,
        -retention_rib_height,
        usable_length,
        retention_rib_width,
        retention_rib_height,
    )

    shape = body.fuse(top_flange).fuse(retention_rib)

    for position in latch_relief_positions:
        relief = make_box(
            end_margin + position - (latch_relief_width / 2.0),
            -0.1,
            -retention_rib_height - 0.1,
            latch_relief_width,
            top_flange_outer_lip + gap_depth + top_flange_inner_lip + latch_relief_extra_depth,
            gap_height + retention_rib_height + 0.2,
        )
        shape = shape.cut(relief)

    if round_edges and edge_radius > 0.0:
        try:
            shape = shape.makeFillet(edge_radius, shape.Edges)
        except Exception:
            pass

    return shape


def mirror_x(shape):
    mirrored = shape.copy()
    mirrored.mirror(App.Vector(0.0, 0.0, 0.0), App.Vector(1.0, 0.0, 0.0))
    return mirrored


def add_part(doc, name, shape, placement):
    existing = doc.getObject(name)
    if existing is not None:
        doc.removeObject(name)
        doc.recompute()

    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    obj.Placement = placement
    return obj


# =========================
# Build parts
# =========================
doc = App.ActiveDocument
if doc is None:
    doc = App.newDocument("A3RoofGapFillers")

side_filler = make_linear_filler(side_length, side_latch_relief_positions)
front_rear_filler = make_linear_filler(front_rear_length, front_rear_latch_relief_positions)

left_obj = add_part(
    doc,
    "LeftSideRoofGapFiller",
    side_filler,
    App.Placement(App.Vector(0.0, 0.0, 0.0), App.Rotation()),
)
right_obj = add_part(
    doc,
    "RightSideRoofGapFiller",
    mirror_x(side_filler),
    App.Placement(App.Vector(side_length, gap_depth + preview_spacing, 0.0), App.Rotation()),
)
front_obj = add_part(
    doc,
    "FrontRoofGapFiller",
    front_rear_filler,
    App.Placement(App.Vector(0.0, (gap_depth + preview_spacing) * 2.0, 0.0), App.Rotation()),
)
rear_obj = add_part(
    doc,
    "RearRoofGapFiller",
    front_rear_filler,
    App.Placement(App.Vector(0.0, (gap_depth + preview_spacing) * 3.0, 0.0), App.Rotation()),
)

doc.recompute()


# =========================
# CLI exports
# =========================
is_cli = not App.GuiUp

if run_exports_in_cli and is_cli:
    script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    fcstd_path = os.path.join(script_dir, export_basename + ".FCStd")
    step_path = os.path.join(script_dir, export_basename + ".step")

    doc.saveAs(fcstd_path)
    Import.export([left_obj, right_obj, front_obj, rear_obj], step_path)

    for obj in [left_obj, right_obj, front_obj, rear_obj]:
        stl_path = os.path.join(script_dir, export_basename + "-" + obj.Name + ".stl")
        obj.Shape.exportStl(stl_path)
        print("Exported:", stl_path)

    print("Exported:", fcstd_path)
    print("Exported:", step_path)
