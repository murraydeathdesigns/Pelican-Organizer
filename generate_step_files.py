"""
Headless STEP file generator for the Pelican 1606 organizer lid.

Runs as a normal Python script (no window, no PyInstaller freezing) -
meant for GitHub Actions (see .github/workflows/generate-step-files.yml):
GitHub's servers install CadQuery normally and run this file, then hand
you back the finished STEP (and optionally STL) files as a downloadable
artifact. Nothing to install locally.

The WHERE (positions of the custom hole pattern and the infill pattern,
with mounting-hole collision avoidance) is computed by panel_layout.py,
which has no CadQuery dependency and is unit-tested separately. This
file only turns those positions into real 3D cuts. preview.html shows
the exact same layout live in a browser before you spend a CI run on it.

Parameters are read from environment variables (populated by the
workflow from its "Run workflow" form inputs), matching panel_layout's
PanelConfig defaults.
"""

import os

import cadquery as cq

from panel_layout import (
    PanelConfig,
    mounting_hole_points,
    gridfinity_cells,
    compute_custom_holes,
    compute_infill,
)


def env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val not in (None, "") else default


def env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(float(val)) if val not in (None, "") else default


def env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val in (None, ""):
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def env_str(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def build_config() -> PanelConfig:
    return PanelConfig(
        length=env_float("PANEL_LENGTH", 617.0),
        width=env_float("PANEL_WIDTH", 494.0),
        thickness=env_float("PANEL_THICKNESS", 5.5),
        enable_gridfinity=env_bool("ENABLE_GRIDFINITY", True),
        gridfinity_q3_only=env_bool("GRIDFINITY_Q3_ONLY", True),
        gridfinity_magnets=env_bool("ADD_MAGNETS", True),
        enable_holes=env_bool("ENABLE_HOLES", False),
        hole_shape=env_str("HOLE_SHAPE", "round"),
        hole_diameter=env_float("HOLE_DIAMETER", 5.0),
        hole_slot_length=env_float("HOLE_SLOT_LENGTH", 10.0),
        hole_slot_axis=env_str("HOLE_SLOT_AXIS", "x"),
        hole_count_x=env_int("HOLE_COUNT_X", 4),
        hole_count_y=env_int("HOLE_COUNT_Y", 3),
        hole_spacing_x=env_float("HOLE_SPACING_X", 80.0),
        hole_spacing_y=env_float("HOLE_SPACING_Y", 80.0),
        hole_field_margin=env_float("HOLE_FIELD_MARGIN", 20.0),
        infill_pattern=env_str("INFILL_PATTERN", "none"),
        infill_spacing=env_float("INFILL_SPACING", 20.0),
        infill_cut_width=env_float("INFILL_CUT_WIDTH", 10.0),
        infill_field_margin=env_float("INFILL_FIELD_MARGIN", 20.0),
        min_clearance=env_float("MIN_CLEARANCE", 1.5),
    )


def main() -> None:
    cfg = build_config()
    export_stl = env_bool("EXPORT_STL", False)
    out_dir = os.environ.get("OUTPUT_DIR", "output")
    os.makedirs(out_dir, exist_ok=True)

    print(
        f"[generate] {cfg.length}x{cfg.width}x{cfg.thickness}mm "
        f"gridfinity={cfg.enable_gridfinity}(q3_only={cfg.gridfinity_q3_only}) "
        f"holes={cfg.enable_holes}({cfg.hole_shape}) infill={cfg.infill_pattern}"
    )

    # ------------------------------------------------------------------
    # Master plate + fixed perimeter mounting holes
    # ------------------------------------------------------------------
    plate = (
        cq.Workplane("XY")
        .rect(cfg.length, cfg.width)
        .extrude(cfg.thickness)
        .edges("|Z")
        .fillet(cfg.corner_radius)
    )

    plate = (
        plate.faces(">Z")
        .workplane()
        .pushPoints(mounting_hole_points(cfg))
        .cboreHole(
            diameter=cfg.cb_through_dia,
            cboreDiameter=cfg.cb_dia,
            cboreDepth=cfg.cb_depth,
            depth=cfg.thickness,
        )
    )

    # ------------------------------------------------------------------
    # Gridfinity pockets (unchanged from the original script)
    # ------------------------------------------------------------------
    if cfg.enable_gridfinity:
        cutter = (
            cq.Workplane("XY")
            .rect(41.5, 41.5)
            .workplane(offset=-4.4)
            .rect(37.5, 37.5)
            .loft(combine=True)
        )
        if cfg.gridfinity_magnets:
            mag_pts = [(13.0, 13.0), (-13.0, 13.0), (-13.0, -13.0), (13.0, -13.0)]
            mag_studs = (
                cq.Workplane("XY")
                .workplane(offset=-4.4)
                .pushPoints(mag_pts)
                .circle(6.5 / 2.0)
                .extrude(-2.4)
            )
            cutter = cutter.union(mag_studs)

        for (cx, cy) in gridfinity_cells(cfg):
            plate = plate.cut(cutter.translate((cx, cy, cfg.thickness)))

    # ------------------------------------------------------------------
    # Custom hole pattern (round or slot, evenly spaced, mounting-hole safe)
    # ------------------------------------------------------------------
    custom_hole_points, holes_skipped = compute_custom_holes(cfg)
    if holes_skipped:
        print(f"[generate] custom hole pattern: {len(custom_hole_points)} placed, "
              f"{holes_skipped} skipped (out of field or too close to a mounting hole)")

    if custom_hole_points:
        wp = plate.faces(">Z").workplane().pushPoints(custom_hole_points)
        if cfg.hole_shape == "slot":
            total_len = cfg.hole_diameter + cfg.hole_slot_length
            angle = 0 if cfg.hole_slot_axis == "x" else 90
            plate = wp.slot2D(total_len, cfg.hole_diameter, angle).cutThruAll()
        else:
            plate = wp.hole(diameter=cfg.hole_diameter)

    # ------------------------------------------------------------------
    # Infill pattern (grid / honeycomb / diagonal), avoiding mounting
    # holes and the custom hole pattern above
    # ------------------------------------------------------------------
    infill_points, infill_skipped = compute_infill(cfg, custom_hole_points)
    if infill_skipped:
        print(f"[generate] infill pattern: {len(infill_points)} features placed, "
              f"{infill_skipped} skipped due to collisions")

    if infill_points:
        wp = plate.faces(">Z").workplane().pushPoints(infill_points)
        if cfg.infill_pattern == "honeycomb":
            plate = wp.polygon(6, cfg.infill_cut_width, circumscribed=True).cutThruAll()
        else:  # "grid" or "diagonal" - round perforations
            plate = wp.hole(diameter=cfg.infill_cut_width)

    # ------------------------------------------------------------------
    # Quadrant split & lap joints (unchanged)
    # ------------------------------------------------------------------
    half_x, half_y, step_z = cfg.length / 2.0, cfg.width / 2.0, cfg.thickness / 2.0
    lap_x = cq.Workplane("XY").rect(cfg.length + 20, 12.0).extrude(step_z + 0.2).translate([0, 0, step_z])
    lap_y = cq.Workplane("XY").rect(12.0, cfg.width + 20).extrude(step_z + 0.2).translate([0, 0, 0])

    quad_masks = {
        "Q1_TopRight": cq.Workplane("XY").rect(half_x + 50, half_y + 50).extrude(cfg.thickness * 2).translate([(half_x + 50) / 2, (half_y + 50) / 2, -1]),
        "Q2_TopLeft": cq.Workplane("XY").rect(half_x + 50, half_y + 50).extrude(cfg.thickness * 2).translate([-(half_x + 50) / 2, (half_y + 50) / 2, -1]),
        "Q3_BottomLeft": cq.Workplane("XY").rect(half_x + 50, half_y + 50).extrude(cfg.thickness * 2).translate([-(half_x + 50) / 2, -(half_y + 50) / 2, -1]),
        "Q4_BottomRight": cq.Workplane("XY").rect(half_x + 50, half_y + 50).extrude(cfg.thickness * 2).translate([(half_x + 50) / 2, -(half_y + 50) / 2, -1]),
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
