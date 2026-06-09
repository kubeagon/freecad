import FreeCAD as App
import Import
import Part
import os

# =========================
# Parametric dimensions (mm)
# =========================
plate_width = 92.0
plate_height = 92.0
plate_thickness = 3.0

# Main airflow opening
airflow_hole_diameter = 72.0

# Fan mounting holes (4-corner pattern)
fan_screw_hole_diameter = 4.3
fan_screw_spacing = 80.0

# Side extension with screw hole
extension_height = 24.0
extension_screw_hole_diameter = 5.7
extension_hole_far_edge_margin = 4.0
extension_plate_overlap = 0.01
thread_pitch = 1.0
thread_depth = 0.45
thread_profile_radius = 0.28
thread_clearance_diameter = 0.15
thread_end_margin = 0.60
thread_cut_extra = 1.0
use_external_screw_cutter = True
external_screw_step_path = "/Users/dan/Git/kubeagon/freecad/92005A420_Steel Pan Head Phillips Screw.STEP"
external_screw_clearance = 0.20
external_cutter_envelope_scale = 1.1
require_external_screw_cutter = True

# Export controls
run_exports_in_cli = True
export_basename = "MountingPlate"
round_outer_corners = True
outer_corner_radius = 5.0


# =========================
# Geometry helpers
# =========================
def make_box(x, y, z, width, height, depth):
    return Part.makeBox(width, height, depth, App.Vector(x, y, z))


def make_z_cylinder(cx, cy, z0, diameter, depth):
    return Part.makeCylinder(diameter / 2.0, depth, App.Vector(cx, cy, z0))


def fillet_vertical_corner_edges(shape, radius, x0, y0, width, height, thickness, skip_y_min=False):
    if radius <= 0.0:
        return shape
    tol = 1e-6
    corner_edges = []
    x1 = x0 + width
    y1 = y0 + height
    for edge in shape.Edges:
        v1 = edge.Vertexes[0].Point
        v2 = edge.Vertexes[1].Point
        is_vertical = abs(v1.x - v2.x) < tol and abs(v1.y - v2.y) < tol and abs(abs(v1.z - v2.z) - thickness) < tol
        if not is_vertical:
            continue
        x_match = abs(v1.x - x0) < tol or abs(v1.x - x1) < tol
        y_match = abs(v1.y - y0) < tol or abs(v1.y - y1) < tol
        if skip_y_min and abs(v1.y - y0) < tol:
            continue
        if x_match and y_match:
            corner_edges.append(edge)
    if len(corner_edges) == 0:
        return shape
    try:
        return shape.makeFillet(radius, corner_edges)
    except Exception:
        return shape


def make_threaded_hole_cutter_z(x_center, y_center, z_start, length, major_diameter):
    effective_length = length - (2.0 * thread_end_margin)
    if effective_length <= thread_pitch:
        return make_z_cylinder(x_center, y_center, z_start, major_diameter, length)

    minor_diameter = major_diameter - (2.0 * thread_depth) + thread_clearance_diameter
    if minor_diameter <= 0.0:
        return make_z_cylinder(x_center, y_center, z_start, major_diameter, length)

    helix_radius = (major_diameter / 2.0) - thread_depth + (thread_profile_radius / 2.0)
    # Always keep a continuous through-bore so the hole is never capped.
    through_core = make_z_cylinder(
        x_center,
        y_center,
        z_start,
        minor_diameter,
        length,
    )

    helix = Part.makeHelix(thread_pitch, effective_length, helix_radius)
    half_profile = thread_profile_radius
    p1 = App.Vector(helix_radius - half_profile, 0.0, -half_profile)
    p2 = App.Vector(helix_radius + half_profile, 0.0, 0.0)
    p3 = App.Vector(helix_radius - half_profile, 0.0, half_profile)
    profile_wire = Part.Wire(Part.makePolygon([p1, p2, p3, p1]))
    thread_shell = Part.Wire(helix).makePipeShell([profile_wire], True, True)
    thread_shell.translate(App.Vector(x_center, y_center, z_start + thread_end_margin))
    return through_core.fuse(thread_shell)


def is_valid_shape(shape):
    if shape is None:
        return False
    if shape.isNull():
        return False
    if not shape.isValid():
        return False
    if len(shape.Solids) == 0:
        return False
    return True


def import_step_shape_compound(doc, step_path):
    before_names = {obj.Name for obj in doc.Objects}
    Import.insert(step_path, doc.Name)
    imported_objs = [obj for obj in doc.Objects if obj.Name not in before_names]
    imported_shapes = [obj.Shape.copy() for obj in imported_objs if hasattr(obj, "Shape") and is_valid_shape(obj.Shape)]
    for obj in imported_objs:
        doc.removeObject(obj.Name)
    doc.recompute()
    if len(imported_shapes) == 0:
        return None
    if len(imported_shapes) == 1:
        return imported_shapes[0]
    return Part.makeCompound(imported_shapes)



# =========================
# Derived values
# =========================
airflow_hole_center_x = plate_width / 2.0
airflow_hole_center_y = plate_height / 2.0

half_fan_spacing = fan_screw_spacing / 2.0
fan_hole_1_x = airflow_hole_center_x - half_fan_spacing
fan_hole_2_x = airflow_hole_center_x + half_fan_spacing
fan_hole_1_y = airflow_hole_center_y - half_fan_spacing
fan_hole_2_y = airflow_hole_center_y + half_fan_spacing

extension_x = (plate_width - extension_height) / 2.0
extension_y = plate_height - extension_plate_overlap
extension_hole_x = extension_x + (extension_height / 2.0)
extension_hole_y = plate_height + 35.0
extension_projection = 35.0 + (extension_screw_hole_diameter / 2.0) + extension_hole_far_edge_margin


# =========================
# Build plate
# =========================
base_plate = make_box(0.0, 0.0, 0.0, plate_width, plate_height, plate_thickness)
side_extension = make_box(
    extension_x,
    extension_y,
    0.0,
    extension_height,
    extension_projection + extension_plate_overlap,
    plate_thickness,
)

if round_outer_corners:
    base_plate = fillet_vertical_corner_edges(
        base_plate,
        outer_corner_radius,
        0.0,
        0.0,
        plate_width,
        plate_height,
        plate_thickness,
    )
    side_extension = fillet_vertical_corner_edges(
        side_extension,
        outer_corner_radius,
        extension_x,
        extension_y,
        extension_height,
        extension_projection + extension_plate_overlap,
        plate_thickness,
        skip_y_min=True,
    )

plate_with_extension = base_plate.fuse(side_extension)

airflow_hole = make_z_cylinder(
    airflow_hole_center_x,
    airflow_hole_center_y,
    0.0,
    airflow_hole_diameter,
    plate_thickness,
)

fan_hole_1 = make_z_cylinder(fan_hole_1_x, fan_hole_1_y, 0.0, fan_screw_hole_diameter, plate_thickness)
fan_hole_2 = make_z_cylinder(fan_hole_2_x, fan_hole_1_y, 0.0, fan_screw_hole_diameter, plate_thickness)
fan_hole_3 = make_z_cylinder(fan_hole_2_x, fan_hole_2_y, 0.0, fan_screw_hole_diameter, plate_thickness)
fan_hole_4 = make_z_cylinder(fan_hole_1_x, fan_hole_2_y, 0.0, fan_screw_hole_diameter, plate_thickness)
extension_hole_z_start = -(thread_cut_extra / 2.0)
extension_hole_length = plate_thickness + thread_cut_extra
cutters = airflow_hole.fuse(fan_hole_1).fuse(fan_hole_2).fuse(fan_hole_3).fuse(fan_hole_4)
final_shape = plate_with_extension.cut(cutters)

doc = App.ActiveDocument
if doc is None:
    doc = App.newDocument("MountingPlate")

if use_external_screw_cutter:
    script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    resolved_screw_step_path = external_screw_step_path
    if not os.path.isabs(resolved_screw_step_path):
        resolved_screw_step_path = os.path.join(script_dir, resolved_screw_step_path)

    plate_cutter_applied = False
    if os.path.exists(resolved_screw_step_path):
        imported_screw_shape = import_step_shape_compound(doc, resolved_screw_step_path)
        if imported_screw_shape is not None and is_valid_shape(imported_screw_shape):
            screw_cutter = imported_screw_shape.copy()
            screw_bb = screw_cutter.BoundBox
            screw_center_x = (screw_bb.XMin + screw_bb.XMax) / 2.0
            screw_center_y = (screw_bb.YMin + screw_bb.YMax) / 2.0
            move_x = extension_hole_x - screw_center_x
            move_y = extension_hole_y - screw_center_y
            move_z = extension_hole_z_start - screw_bb.ZMin
            screw_cutter.translate(App.Vector(move_x, move_y, move_z))

            envelope = make_z_cylinder(
                extension_hole_x,
                extension_hole_y,
                extension_hole_z_start,
                extension_screw_hole_diameter * external_cutter_envelope_scale,
                extension_hole_length,
            )
            screw_cutter = screw_cutter.common(envelope)

            cutters_to_try = []
            if external_screw_clearance > 0.0:
                try:
                    cutters_to_try.append(screw_cutter.makeOffsetShape(external_screw_clearance, 0.01))
                except Exception:
                    pass
            cutters_to_try.append(screw_cutter)

            for cutter_try in cutters_to_try:
                if is_valid_shape(cutter_try):
                    candidate = final_shape.cut(cutter_try)
                    if is_valid_shape(candidate):
                        final_shape = candidate
                        plate_cutter_applied = True
                        break
    if require_external_screw_cutter and not plate_cutter_applied:
        raise RuntimeError("External screw cutter was not applied to extension hole. Missing/invalid STEP: " + resolved_screw_step_path)


# =========================
# Document objects
# =========================
existing = doc.getObject("MountingPlate")
if existing is not None:
    doc.removeObject("MountingPlate")
    doc.recompute()

obj = doc.addObject("Part::Feature", "MountingPlate")
obj.Shape = final_shape

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
    Import.export([obj], step_path)

    print("Exported:", fcstd_path)
    print("Exported:", step_path)
