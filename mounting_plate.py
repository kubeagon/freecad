import FreeCAD as App
import Import
import Part
import os

# =========================
# Parametric dimensions (mm)
# =========================
plate_width = 105.0
plate_height = 105.0
plate_thickness = 3.0

# Main airflow opening for the fan
airflow_hole_diameter = 72.0
airflow_hole_center_x = plate_width / 2.0
airflow_hole_center_y = plate_height / 2.0

# Fan mounting holes (4-corner pattern)
fan_screw_hole_diameter = 4.3
fan_screw_spacing = 80.0

# Secondary clamp features that go into the case and hook outward
clamp_feature_center_y = 60.0
side_feature_height = 16.0
clamp_bottom_edge_clearance_min = 23.0
clamp_max_width = 25.0

clamp_connector_depth = 8.0
case_insert_thickness = 3.0
outward_hook_extension = 9.0
outward_hook_thickness = 3.0
clamp_gap = 5.0

# Front tabs used for clamping screws
front_tab_projection = 12.0
front_tab_thickness = 3.0
front_tab_hole_diameter = 5.7
front_tab_hole_edge_margin = 4.0

# Thread settings for clamp holes (for printed plastic screws)
use_threaded_clamp_holes = True
thread_pitch = 1.0
thread_depth = 0.45
thread_profile_radius = 0.28
thread_clearance_diameter = 0.15
thread_end_margin = 0.60
thread_debug_report = True

generate_clamp_test_part = True
clamp_test_offset_x = plate_width + 35.0
clamp_test_offset_y = 0.0
clamp_test_width = 9.0
clamp_test_height = 12.0
clamp_test_thickness = 5.0
use_external_screw_cutter_for_test = True
use_external_screw_cutter_for_plate = True
external_screw_step_path = "/Users/dan/Git/kubeagon/freecad/92005A420_Steel Pan Head Phillips Screw.STEP"
external_screw_clearance = 0.20
require_external_screw_cutter = True
external_cutter_envelope_scale = 1.1

# Export controls
run_exports_in_cli = True
export_basename = "MountingPlate"
round_corners_and_edges = True
corner_fillet_radius = 2.0
edge_fillet_radius = 0.8


# =========================
# Geometry helpers
# =========================
def make_box(x, y, z, width, height, depth):
    return Part.makeBox(width, height, depth, App.Vector(x, y, z))


def make_z_cylinder(cx, cy, z0, diameter, depth):
    radius = diameter / 2.0
    return Part.makeCylinder(radius, depth, App.Vector(cx, cy, z0))


def fillet_box_vertical_corner_edges(box_shape, fillet_radius, width, height, thickness):
    tol = 1e-6
    corner_edges = []
    for edge in box_shape.Edges:
        v1 = edge.Vertexes[0].Point
        v2 = edge.Vertexes[1].Point
        is_vertical = abs(v1.x - v2.x) < tol and abs(v1.y - v2.y) < tol and abs(abs(v1.z - v2.z) - thickness) < tol
        if not is_vertical:
            continue
        x_match = abs(v1.x - 0.0) < tol or abs(v1.x - width) < tol
        y_match = abs(v1.y - 0.0) < tol or abs(v1.y - height) < tol
        if x_match and y_match:
            corner_edges.append(edge)

    if len(corner_edges) == 0:
        return box_shape
    return box_shape.makeFillet(fillet_radius, corner_edges)


def make_threaded_hole_cutter_z(x_center, y_center, z_start, length, major_diameter):
    effective_length = length - (2.0 * thread_end_margin)
    if effective_length <= thread_pitch:
        return make_z_cylinder(x_center, y_center, z_start, major_diameter, length)

    minor_diameter = major_diameter - (2.0 * thread_depth) + thread_clearance_diameter
    if minor_diameter <= 0.0:
        return make_z_cylinder(x_center, y_center, z_start, major_diameter, length)

    helix_radius = (major_diameter / 2.0) - thread_depth + (thread_profile_radius / 2.0)

    core = make_z_cylinder(
        x_center,
        y_center,
        z_start + thread_end_margin,
        minor_diameter,
        effective_length,
    )

    helix = Part.makeHelix(thread_pitch, effective_length, helix_radius)
    half_profile = thread_profile_radius
    p1 = App.Vector(helix_radius - half_profile, 0.0, -half_profile)
    p2 = App.Vector(helix_radius + half_profile, 0.0, 0.0)
    p3 = App.Vector(helix_radius - half_profile, 0.0, half_profile)
    profile_wire = Part.Wire(Part.makePolygon([p1, p2, p3, p1]))
    thread_shell = Part.Wire(helix).makePipeShell([profile_wire], True, True)
    thread_shell.translate(App.Vector(x_center, y_center, z_start + thread_end_margin))

    return core.fuse(thread_shell)


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
half_fan_spacing = fan_screw_spacing / 2.0
fan_hole_1_x = airflow_hole_center_x - half_fan_spacing
fan_hole_2_x = airflow_hole_center_x + half_fan_spacing
fan_hole_1_y = airflow_hole_center_y - half_fan_spacing
fan_hole_2_y = airflow_hole_center_y + half_fan_spacing

left_feature_x = 0.0
right_feature_x = plate_width - case_insert_thickness

effective_side_feature_height = min(side_feature_height, clamp_max_width)
feature_y_start = max(
    clamp_feature_center_y - (effective_side_feature_height / 2.0),
    clamp_bottom_edge_clearance_min,
)
clamp_hole_center_y = feature_y_start + (effective_side_feature_height / 2.0)

front_tab_z = 0.0
back_feature_z = plate_thickness
effective_clamp_gap = min(clamp_gap, clamp_connector_depth - outward_hook_thickness)
hook_z = plate_thickness + effective_clamp_gap

left_tab_x = -front_tab_projection
right_tab_x = plate_width



# =========================
# Build primary plate
# =========================
base_plate = make_box(0.0, 0.0, 0.0, plate_width, plate_height, plate_thickness)
if round_corners_and_edges:
    # Round only the mounting plate perimeter before adding clamp features/threads.
    # This keeps screw-thread geometry untouched.
    try:
        base_plate = fillet_box_vertical_corner_edges(
            base_plate,
            corner_fillet_radius,
            plate_width,
            plate_height,
            plate_thickness,
        )
    except Exception:
        pass

airflow_hole = make_z_cylinder(
    airflow_hole_center_x,
    airflow_hole_center_y,
    0.0,
    airflow_hole_diameter,
    plate_thickness,
)

fan_hole_depth = plate_thickness
fan_hole_1 = make_z_cylinder(fan_hole_1_x, fan_hole_1_y, 0.0, fan_screw_hole_diameter, fan_hole_depth)
fan_hole_2 = make_z_cylinder(fan_hole_2_x, fan_hole_1_y, 0.0, fan_screw_hole_diameter, fan_hole_depth)
fan_hole_3 = make_z_cylinder(fan_hole_2_x, fan_hole_2_y, 0.0, fan_screw_hole_diameter, fan_hole_depth)
fan_hole_4 = make_z_cylinder(fan_hole_1_x, fan_hole_2_y, 0.0, fan_screw_hole_diameter, fan_hole_depth)

plate_cutters = airflow_hole.fuse(fan_hole_1).fuse(fan_hole_2).fuse(fan_hole_3).fuse(fan_hole_4)
main_plate = base_plate.cut(plate_cutters)


# =========================
# Build side in-case clamp features (left/right, top/bottom)
# =========================
def build_side_feature(x_start, y_start, is_left):
    insert_leg = make_box(
        x_start,
        y_start,
        back_feature_z,
        case_insert_thickness,
        effective_side_feature_height,
        clamp_connector_depth,
    )

    if is_left:
        hook_x = x_start - outward_hook_extension
    else:
        hook_x = x_start + case_insert_thickness

    hook = make_box(
        hook_x,
        y_start,
        hook_z,
        outward_hook_extension,
        effective_side_feature_height,
        outward_hook_thickness,
    )

    return insert_leg.fuse(hook)


left_feature = build_side_feature(left_feature_x, feature_y_start, True)
right_feature = build_side_feature(right_feature_x, feature_y_start, False)

rear_features = left_feature.fuse(right_feature)


# =========================
# Build front clamp tabs aligned with rear features
# =========================
def build_front_tab(x_start, y_start):
    return make_box(
        x_start,
        y_start,
        front_tab_z,
        front_tab_projection,
        effective_side_feature_height,
        front_tab_thickness,
    )


left_tab = build_front_tab(left_tab_x, feature_y_start)
right_tab = build_front_tab(right_tab_x, feature_y_start)

front_tabs = left_tab.fuse(right_tab)


# =========================
# Cut clamp screw holes through tabs + rear features (Z-axis)
# =========================
y_center = clamp_hole_center_y

# Keep hole centers inset from the front-tab outer edges so holes do not break out.
front_tab_hole_radius = front_tab_hole_diameter / 2.0
front_tab_hole_inset = front_tab_hole_edge_margin + front_tab_hole_radius
front_tab_hole_inset = min(front_tab_hole_inset, front_tab_projection - front_tab_hole_radius)

left_hole_x = left_tab_x + front_tab_hole_inset
right_hole_x = (right_tab_x + front_tab_projection) - front_tab_hole_inset
clamp_hole_z_start = front_tab_z
clamp_hole_z_length = front_tab_thickness
clamp_hole_extra_cut = 1.0
clamp_hole_cut_z_start = clamp_hole_z_start - (clamp_hole_extra_cut / 2.0)
clamp_hole_cut_z_length = clamp_hole_z_length + clamp_hole_extra_cut

clamp_hole_left = make_z_cylinder(
    left_hole_x,
    y_center,
    clamp_hole_cut_z_start,
    front_tab_hole_diameter,
    clamp_hole_cut_z_length,
)
clamp_hole_right = make_z_cylinder(
    right_hole_x,
    y_center,
    clamp_hole_cut_z_start,
    front_tab_hole_diameter,
    clamp_hole_cut_z_length,
)

clamp_base_hole_diameter = front_tab_hole_diameter
if use_external_screw_cutter_for_plate:
    clamp_base_hole_diameter = max(front_tab_hole_diameter - (2.0 * thread_depth), 1.0)

clamp_base_hole_left = make_z_cylinder(
    left_hole_x,
    y_center,
    clamp_hole_cut_z_start,
    clamp_base_hole_diameter,
    clamp_hole_cut_z_length,
)
clamp_base_hole_right = make_z_cylinder(
    right_hole_x,
    y_center,
    clamp_hole_cut_z_start,
    clamp_base_hole_diameter,
    clamp_hole_cut_z_length,
)
clamp_base_holes = clamp_base_hole_left.fuse(clamp_base_hole_right)

clamp_thread_holes = None
if use_threaded_clamp_holes:
    clamp_thread_left = make_threaded_hole_cutter_z(
        left_hole_x,
        y_center,
        clamp_hole_cut_z_start,
        clamp_hole_cut_z_length,
        front_tab_hole_diameter,
    )
    clamp_thread_right = make_threaded_hole_cutter_z(
        right_hole_x,
        y_center,
        clamp_hole_cut_z_start,
        clamp_hole_cut_z_length,
        front_tab_hole_diameter,
    )
    if is_valid_shape(clamp_thread_left) and is_valid_shape(clamp_thread_right):
        clamp_thread_holes = clamp_thread_left.fuse(clamp_thread_right)

# =========================
# Final shape
# =========================
combined_shape = main_plate.fuse(rear_features).fuse(front_tabs)
final_shape = combined_shape.cut(clamp_base_holes)
if clamp_thread_holes is not None:
    final_shape = final_shape.cut(clamp_thread_holes)


# =========================
# Standalone clamp test part
# =========================
clamp_test_shape = None
if generate_clamp_test_part:
    clamp_tab_test = make_box(
        left_hole_x - (clamp_test_width / 2.0),
        y_center - (clamp_test_height / 2.0),
        front_tab_z,
        clamp_test_width,
        clamp_test_height,
        clamp_test_thickness,
    )
    clamp_test_shape = clamp_tab_test


doc = App.ActiveDocument
if doc is None:
    doc = App.newDocument("MountingPlate")

script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
resolved_screw_step_path = external_screw_step_path
if not os.path.isabs(resolved_screw_step_path):
    resolved_screw_step_path = os.path.join(script_dir, resolved_screw_step_path)

if use_external_screw_cutter_for_plate:
    plate_cutter_applied = False
    if os.path.exists(resolved_screw_step_path):
        imported_screw_shape = import_step_shape_compound(doc, resolved_screw_step_path)
        if imported_screw_shape is not None and is_valid_shape(imported_screw_shape):
            base_cutter = imported_screw_shape.copy()
            base_bb = base_cutter.BoundBox
            base_center_x = (base_bb.XMin + base_bb.XMax) / 2.0
            base_center_y = (base_bb.YMin + base_bb.YMax) / 2.0
            base_shift_z = clamp_hole_cut_z_start - base_bb.ZMin

            left_cutter = base_cutter.copy()
            left_cutter.translate(App.Vector(left_hole_x - base_center_x, y_center - base_center_y, base_shift_z))
            right_cutter = base_cutter.copy()
            right_cutter.translate(App.Vector(right_hole_x - base_center_x, y_center - base_center_y, base_shift_z))

            envelope_diameter = front_tab_hole_diameter * external_cutter_envelope_scale
            envelope_depth = clamp_hole_cut_z_length
            left_envelope = make_z_cylinder(
                left_hole_x,
                y_center,
                clamp_hole_cut_z_start,
                envelope_diameter,
                envelope_depth,
            )
            right_envelope = make_z_cylinder(
                right_hole_x,
                y_center,
                clamp_hole_cut_z_start,
                envelope_diameter,
                envelope_depth,
            )
            left_cutter = left_cutter.common(left_envelope)
            right_cutter = right_cutter.common(right_envelope)

            cutters_to_try = []
            if external_screw_clearance > 0.0:
                try:
                    left_offset = left_cutter.makeOffsetShape(external_screw_clearance, 0.01)
                    right_offset = right_cutter.makeOffsetShape(external_screw_clearance, 0.01)
                    cutters_to_try.append((left_offset, right_offset))
                except Exception:
                    pass
            cutters_to_try.append((left_cutter, right_cutter))

            for left_try, right_try in cutters_to_try:
                if is_valid_shape(left_try) and is_valid_shape(right_try):
                    plate_thread_cutter = left_try.fuse(right_try)
                    final_shape = final_shape.cut(plate_thread_cutter)
                    plate_cutter_applied = True
                    break
        else:
            print("Warning: could not import external screw shape for plate holes; keeping parametric threaded holes.")
    else:
        print("Warning: external screw STEP not found for plate holes:", resolved_screw_step_path)
    if require_external_screw_cutter and not plate_cutter_applied:
        raise RuntimeError("External screw cutter was not applied to plate holes. Missing/invalid STEP: " + resolved_screw_step_path)

existing = doc.getObject("MountingPlate")
if existing is not None:
    doc.removeObject("MountingPlate")
    doc.recompute()

obj = doc.addObject("Part::Feature", "MountingPlate")
obj.Shape = final_shape

existing_test = doc.getObject("ClampTestPart")
if existing_test is not None:
    doc.removeObject("ClampTestPart")
    doc.recompute()

if clamp_test_shape is not None:
    clamp_test_cutter_applied = False
    if use_external_screw_cutter_for_test:
        if os.path.exists(resolved_screw_step_path):
            imported_screw_shape = import_step_shape_compound(doc, resolved_screw_step_path)
            if imported_screw_shape is not None and is_valid_shape(imported_screw_shape):
                cutter_shape = imported_screw_shape.copy()
                screw_bb = cutter_shape.BoundBox
                screw_center_x = (screw_bb.XMin + screw_bb.XMax) / 2.0
                screw_center_y = (screw_bb.YMin + screw_bb.YMax) / 2.0
                move_x = left_hole_x - screw_center_x
                move_y = y_center - screw_center_y
                move_z = clamp_hole_cut_z_start - screw_bb.ZMin
                cutter_shape.translate(App.Vector(move_x, move_y, move_z))
                test_envelope = make_z_cylinder(
                    left_hole_x,
                    y_center,
                    clamp_hole_cut_z_start,
                    front_tab_hole_diameter * external_cutter_envelope_scale,
                    clamp_test_thickness + clamp_hole_extra_cut,
                )
                cutter_shape = cutter_shape.common(test_envelope)
                cutters_to_try = []
                if external_screw_clearance > 0.0:
                    try:
                        cutters_to_try.append(cutter_shape.makeOffsetShape(external_screw_clearance, 0.01))
                    except Exception:
                        pass
                cutters_to_try.append(cutter_shape)

                for cutter_try in cutters_to_try:
                    if is_valid_shape(cutter_try):
                        clamp_test_shape = clamp_test_shape.cut(cutter_try)
                        clamp_test_cutter_applied = True
                        break
        if not clamp_test_cutter_applied:
            print("Warning: external screw cutter not applied; falling back to parametric test hole.")
            if require_external_screw_cutter:
                raise RuntimeError("External screw cutter was not applied to ClampTestPart.")

    if not clamp_test_cutter_applied:
        clamp_hole_test = make_z_cylinder(
            left_hole_x,
            y_center,
            clamp_hole_cut_z_start,
            front_tab_hole_diameter,
            clamp_test_thickness + clamp_hole_extra_cut,
        )
        clamp_thread_hole_test = None
        if use_threaded_clamp_holes:
            clamp_thread_hole_test = make_threaded_hole_cutter_z(
                left_hole_x,
                y_center,
                clamp_hole_cut_z_start,
                clamp_test_thickness + clamp_hole_extra_cut,
                front_tab_hole_diameter,
            )
        clamp_test_shape = clamp_test_shape.cut(clamp_hole_test)
        if clamp_thread_hole_test is not None and is_valid_shape(clamp_thread_hole_test):
            clamp_test_shape = clamp_test_shape.cut(clamp_thread_hole_test)

    clamp_test_shape.translate(App.Vector(clamp_test_offset_x, clamp_test_offset_y, 0.0))

    test_obj = doc.addObject("Part::Feature", "ClampTestPart")
    test_obj.Shape = clamp_test_shape

existing_screws = doc.getObject("ClampScrews")
if existing_screws is not None:
    doc.removeObject("ClampScrews")
    doc.recompute()

existing_combined = doc.getObject("MountingPlateWithTests")
if existing_combined is not None:
    doc.removeObject("MountingPlateWithTests")
    doc.recompute()

if clamp_test_shape is not None:
    combined_export_shape = Part.makeCompound([final_shape, clamp_test_shape])
else:
    combined_export_shape = final_shape

combined_obj = doc.addObject("Part::Feature", "MountingPlateWithTests")
combined_obj.Shape = combined_export_shape

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
    Import.export([combined_obj], step_path)

    print("Exported:", fcstd_path)
    print("Exported:", step_path)
