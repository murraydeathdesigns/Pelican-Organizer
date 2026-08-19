"""
Headless STEP file generator for the Pelican 1606 organizer lid.

Same geometry as organizer_app.py's GUI, but with no window and no
freezing step - this just runs straight through as a normal Python
script. Meant to run inside GitHub Actions (see
.github/workflows/generate-step-files.yml): GitHub's servers install
CadQuery normally and run this file, then hand you back the finished
STEP (and optionally STL) files as a downloadable artifact. Nothing to
install locally, nothing to package - just the output files.

Parameters are read from environment variables (populated by the
workflow from its "Run workflow" form inputs) with the same defaults
as the GUI app.
"""

import os

import cadquery as cq


def env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val not in (None, "") else default


def env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val in (None, ""):
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def main() -> None:
    length = env_float("PANEL_LENGTH", 617.0)
    width = env_float("PANEL_WIDTH", 494.0)
    thickness = env_float("PANEL_THICKNESS", 5.5)
    enable_gf = env_bool("ENABLE_GRIDFINITY", True)
    q3_only = env_bool("GRIDFINITY_Q3_ONLY", True)
    add_mags = env_bool("ADD_MAGNETS", True)
    export_stl = env_bool("EXPORT_STL", False)
    out_dir = os.environ.get("OUTPUT_DIR", "output")

    os.makedirs(out_dir, exist_ok=True)

    print(
        f"[generate] length={length} width={width} thickness={thickness} "
        f"gridfinity={enable_gf} q3_only={q3_only} magnets={add_mags} stl={export_stl}"
    )

    # Master Plate
    plate = (
        cq.Workplane("XY")
        .rect(length, width)
        .extrude(thickness)
        .edges("|Z")
        .fillet(25.4)
    )

    # Perimeter Mounting Holes
    mount_x = (length / 2.0) - 25.0
    mount_y = (width / 2.0) - 25.0
    plate = (
        plate.faces(">Z")
        .workplane()
        .pushPoints([
            (mount_x, mount_y), (-mount_x, mount_y),
            (-mount_x, -mount_y), (mount_x, -mount_y),
            (0, mount_y), (0, -mount_y)
        ])
        .cboreHole(diameter=4.5, cboreDiameter=8.5, cboreDepth=2.5, depth=thickness)
    )

    # Gridfinity or plain M4 grid
    if enable_gf:
        cutter = (
            cq.Workplane("XY")
            .rect(41.5, 41.5)
            .workplane(offset=-4.4)
            .rect(37.5, 37.5)
            .loft(combine=True)
        )
        if add_mags:
            mag_pts = [(13.0, 13.0), (-13.0, 13.0), (-13.0, -13.0), (13.0, -13.0)]
            mag_studs = (
                cq.Workplane("XY")
                .workplane(offset=-4.4)
                .pushPoints(mag_pts)
                .circle(6.5 / 2.0)
                .extrude(-2.4)
            )
            cutter = cutter.union(mag_studs)

        start_x = -((6 - 1) * 42.0) / 2.0 - (length / 4.0)
        start_y = -((5 - 1) * 42.0) / 2.0 - (width / 4.0)
        for i in range(6):
            for j in range(5):
                cx = start_x + (i * 42.0)
                cy = start_y + (j * 42.0)
                if not q3_only or (cx < -20 and cy < -20):
                    plate = plate.cut(cutter.translate((cx, cy, thickness)))

    # Quadrant Split & Lap Joints
    half_x, half_y, step_z = length / 2.0, width / 2.0, thickness / 2.0
    lap_x = cq.Workplane("XY").rect(length + 20, 12.0).extrude(step_z + 0.2).translate([0, 0, step_z])
    lap_y = cq.Workplane("XY").rect(12.0, width + 20).extrude(step_z + 0.2).translate([0, 0, 0])

    quad_masks = {
        "Q1_TopRight": cq.Workplane("XY").rect(half_x + 50, half_y + 50).extrude(thickness * 2).translate([(half_x + 50) / 2, (half_y + 50) / 2, -1]),
        "Q2_TopLeft": cq.Workplane("XY").rect(half_x + 50, half_y + 50).extrude(thickness * 2).translate([-(half_x + 50) / 2, (half_y + 50) / 2, -1]),
        "Q3_BottomLeft": cq.Workplane("XY").rect(half_x + 50, half_y + 50).extrude(thickness * 2).translate([-(half_x + 50) / 2, -(half_y + 50) / 2, -1]),
        "Q4_BottomRight": cq.Workplane("XY").rect(half_x + 50, half_y + 50).extrude(thickness * 2).translate([(half_x + 50) / 2, -(half_y + 50) / 2, -1]),
    }

    for q_name, mask in quad_masks.items():
        raw_q = plate.intersect(mask)
        if "TopRight" in q_name:
            solid = raw_q.cut(lap_x).cut(lap_y)
        elif "TopLeft" in q_name:
            solid = raw_q.cut(lap_x)
        elif "BottomRight" in q_name:
            solid = raw_q.cut(lap_y)
        else:
            solid = raw_q

        step_path = os.path.join(out_dir, f"Pelican_1606_{q_name}.step")
        cq.exporters.export(solid, step_path)
        print(f"[generate] wrote {step_path}")

        if export_stl:
            stl_path = os.path.join(out_dir, f"Pelican_1606_{q_name}.stl")
            cq.exporters.export(solid, stl_path)
            print(f"[generate] wrote {stl_path}")

    print("[generate] done")


if __name__ == "__main__":
    main()
