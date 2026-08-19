"""
Shared 2D layout math for the Pelican 1606 organizer panel generator.

No CadQuery import here on purpose - this module only computes WHERE
things go (mounting holes, the custom hole pattern, the infill
pattern) and which candidate positions get skipped for being too
close to something else. generate_step_files.py imports this and
turns the results into real 3D cuts.

preview.html re-implements this exact same math in JavaScript (see
its PANEL_LAYOUT block) so you can see the layout instantly in a
browser without waiting on a CadQuery build. If you change the
algorithms here, mirror the change there too - see the comment at the
top of that block for a function-by-function map.
"""

from dataclasses import dataclass
from math import cos, sin, radians, sqrt
from typing import List, Tuple

Circle = Tuple[float, float, float]  # (x, y, radius)
Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Point generators
# ---------------------------------------------------------------------------

def evenly_spaced(count: int, spacing: float) -> List[float]:
    """N positions centered on 0, `spacing' apart. count<=1 -> [0.0]."""
    if count <= 1:
        return [0.0]
    span = spacing * (count - 1)
    start = -span / 2.0
    return [start + i * spacing for i in range(count)]


def grid_points(count_x: int, spacing_x: float, count_y: int, spacing_y: float) -> List[Point]:
    """Centered rectangular grid - same centering convention as CadQuery's Workplane.rarray()."""
    xs = evenly_spaced(count_x, spacing_x)
    ys = evenly_spaced(count_y, spacing_y)
    return [(x, y) for x in xs for y in ys]


def rotate(x: float, y: float, angle_deg: float) -> Point:
    a = radians(angle_deg)
    return (x * cos(a) - y * sin(a), x * sin(a) + y * cos(a))


def hex_points(spacing: float, half_x: float, half_y: float) -> List[Point]:
    """Offset-row hex lattice covering +-half_x / +-half_y, centered on 0."""
    row_h = spacing * sqrt(3) / 2.0
    if row_h <= 0 or spacing <= 0:
        return []
    max_row = int((half_y + spacing) // row_h) + 1
    max_col = int((half_x + spacing) // spacing) + 1

    points = []
    for j in range(-max_row, max_row + 1):
        y = j * row_h
        x_offset = (spacing / 2.0) if (j % 2 != 0) else 0.0
        for i in range(-max_col, max_col + 1):
            x = i * spacing + x_offset
            points.append((x, y))
    return points


# ---------------------------------------------------------------------------
# Collision checks
# ---------------------------------------------------------------------------

def dist_point_to_segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return sqrt((px - ax) ** 2 + (py - ay) ** 2)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    cx, cy = ax + t * dx, ay + t * dy
    return sqrt((px - cx) ** 2 + (py - cy) ** 2)


def circle_ok(x: float, y: float, radius: float, exclusions: List[Circle], clearance: float) -> bool:
    """True if a circular feature of `radius' at (x,y) clears every exclusion circle."""
    for (cx, cy, cr) in exclusions:
        if sqrt((x - cx) ** 2 + (y - cy) ** 2) < radius + cr + clearance:
            return False
    return True


def slot_ok(x: float, y: float, half_length: float, axis: str, half_width: float,
            exclusions: List[Circle], clearance: float) -> bool:
    """True if a slot centered at (x,y) (core segment of `half_length' along `axis',
    half-width `half_width') clears every exclusion circle."""
    if axis == "y":
        ax, ay, bx, by = x, y - half_length, x, y + half_length
    else:
        ax, ay, bx, by = x - half_length, y, x + half_length, y
    for (cx, cy, cr) in exclusions:
        if dist_point_to_segment(cx, cy, ax, ay, bx, by) < half_width + cr + clearance:
            return False
    return True


# ---------------------------------------------------------------------------
# Panel configuration + layout computation
# ---------------------------------------------------------------------------

@dataclass
class PanelConfig:
    length: float = 617.0
    width: float = 494.0
    thickness: float = 5.5
    corner_radius: float = 25.4

    mount_offset: float = 25.0
    cb_through_dia: float = 4.5
    cb_dia: float = 8.5
    cb_depth: float = 2.5

    enable_gridfinity: bool = True
    gridfinity_q3_only: bool = True
    gridfinity_magnets: bool = True

    enable_holes: bool = False
    hole_shape: str = "round"       # "round" | "slot"
    hole_diameter: float = 5.0      # round: hole dia. slot: slot width.
    hole_slot_length: float = 10.0  # slot only: straight-segment length added beyond the width
    hole_slot_axis: str = "x"       # "x" | "y" - which way the slot elongates
    hole_count_x: int = 4
    hole_count_y: int = 3
    hole_spacing_x: float = 80.0
    hole_spacing_y: float = 80.0
    hole_field_margin: float = 20.0  # keep-out from the panel's outer edge

    infill_pattern: str = "none"    # "none" | "grid" | "honeycomb" | "diagonal"
    infill_spacing: float = 20.0
    infill_cut_width: float = 10.0
    infill_field_margin: float = 20.0

    min_clearance: float = 1.5      # min gap enforced between any two cut features

    MAX_INFILL_FEATURES = 5000


def mounting_hole_points(cfg: PanelConfig) -> List[Point]:
    mx = (cfg.length / 2.0) - cfg.mount_offset
    my = (cfg.width / 2.0) - cfg.mount_offset
    return [(mx, my), (-mx, my), (-mx, -my), (mx, -my), (0, my), (0, -my)]


def mounting_hole_exclusions(cfg: PanelConfig) -> List[Circle]:
    r = cfg.cb_dia / 2.0
    return [(x, y, r) for (x, y) in mounting_hole_points(cfg)]


def _fit_and_center(spacing: float, lo: float, hi: float) -> List[float]:
    """As many `spacing'-separated positions as fit in [lo, hi], centered."""
    span = hi - lo
    if span <= 0 or spacing <= 0:
        return []
    count = max(1, int(span // spacing) + 1)
    while count > 1 and spacing * (count - 1) > span:
        count -= 1
    center = (lo + hi) / 2.0
    return [center + p for p in evenly_spaced(count, spacing)]


def gridfinity_cells(cfg: PanelConfig) -> List[Point]:
    """Centers of the Gridfinity pockets, 42mm pitch (cell body 41.5mm).

    gridfinity_q3_only=True fills just the bottom-left quadrant.
    gridfinity_q3_only=False fills all 4 quadrants.

    Each quadrant is gridded independently (not as one continuous grid
    spanning the seams) so no cell's 41.5mm body ever crosses a
    quadrant seam at x=0/y=0 - if it did, the quadrant split would
    physically cut that pocket in half. `seam' is set >= half the cell
    body width for exactly this reason; `margin' likewise keeps cells
    off the outer panel edge/corner fillet.

    Note: earlier versions of this generator always anchored the grid
    into the bottom-left corner regardless of this flag (toggling it
    did nothing), and later a version that centered one grid across
    the seams could still let edge cells overhang a seam. Both fixed
    here.
    """
    if not cfg.enable_gridfinity:
        return []
    pitch = 42.0
    cell_half = 41.5 / 2.0
    margin = cell_half + 4.0   # keep-out from the outer panel edge
    seam = cell_half + 4.0     # keep-out from the x=0/y=0 quadrant seams
    half_x, half_y = cfg.length / 2.0, cfg.width / 2.0

    def quadrant_grid(x_lo, x_hi, y_lo, y_hi):
        xs = _fit_and_center(pitch, x_lo, x_hi)
        ys = _fit_and_center(pitch, y_lo, y_hi)
        return [(x, y) for x in xs for y in ys]

    q3 = quadrant_grid(-half_x + margin, -seam, -half_y + margin, -seam)
    if cfg.gridfinity_q3_only:
        return q3

    q1 = quadrant_grid(seam, half_x - margin, seam, half_y - margin)
    q2 = quadrant_grid(-half_x + margin, -seam, seam, half_y - margin)
    q4 = quadrant_grid(seam, half_x - margin, -half_y + margin, -seam)
    return q3 + q1 + q2 + q4


def gridfinity_exclusions(cfg: PanelConfig) -> List[Circle]:
    """Bounding circles around each Gridfinity cell (41.5mm square), used
    to keep the custom hole pattern and infill from cutting into a
    pocket floor. Radius is the square's half-diagonal, so it's a
    conservative (slightly generous) circular approximation."""
    r = (41.5 / 2.0) * sqrt(2)
    return [(x, y, r) for (x, y) in gridfinity_cells(cfg)]


def _crosses_seam(cfg: PanelConfig, x: float, y: float) -> bool:
    """True if this hole's own body would straddle the x=0 or y=0 quadrant
    seam - which would physically split a functional hole in half when the
    plate is cut into quadrants. (An odd hole count places one hole
    exactly on a seam by construction of the centered spacing, so this
    isn't just a theoretical edge case.) Infill features are allowed to
    cross seams (they're decorative, not functional), so this check is
    only applied to the custom hole pattern."""
    if cfg.hole_shape == "slot":
        half_len = cfg.hole_slot_length / 2.0 + cfg.hole_diameter / 2.0
        half_w = cfg.hole_diameter / 2.0
        half_extent_x, half_extent_y = (half_len, half_w) if cfg.hole_slot_axis == "x" else (half_w, half_len)
    else:
        half_extent_x = half_extent_y = cfg.hole_diameter / 2.0
    return abs(x) < half_extent_x + cfg.min_clearance or abs(y) < half_extent_y + cfg.min_clearance


def compute_custom_holes(cfg: PanelConfig) -> Tuple[List[Point], int]:
    """Returns (kept_points, skipped_count). Applies to the whole master
    plate (pre quadrant-split), same as the mounting holes / Gridfinity."""
    if not cfg.enable_holes:
        return [], 0

    candidates = grid_points(cfg.hole_count_x, cfg.hole_spacing_x, cfg.hole_count_y, cfg.hole_spacing_y)
    exclusions = mounting_hole_exclusions(cfg) + gridfinity_exclusions(cfg)
    half_x = cfg.length / 2.0 - cfg.hole_field_margin
    half_y = cfg.width / 2.0 - cfg.hole_field_margin

    kept, skipped = [], 0
    for (x, y) in candidates:
        if abs(x) > half_x or abs(y) > half_y or _crosses_seam(cfg, x, y):
            skipped += 1
            continue
        if cfg.hole_shape == "slot":
            ok = slot_ok(x, y, cfg.hole_slot_length / 2.0, cfg.hole_slot_axis,
                         cfg.hole_diameter / 2.0, exclusions, cfg.min_clearance)
        else:
            ok = circle_ok(x, y, cfg.hole_diameter / 2.0, exclusions, cfg.min_clearance)
        if ok:
            kept.append((x, y))
        else:
            skipped += 1
    return kept, skipped


def compute_infill(cfg: PanelConfig, custom_hole_points: List[Point]) -> Tuple[List[Point], int]:
    """Returns (kept_points, skipped_count). Avoids mounting holes,
    Gridfinity cells, and the custom hole pattern (if any). Applies to
    the whole master plate."""
    if cfg.infill_pattern == "none" or cfg.infill_spacing <= 0:
        return [], 0

    half_x = cfg.length / 2.0 - cfg.infill_field_margin
    half_y = cfg.width / 2.0 - cfg.infill_field_margin
    if half_x <= 0 or half_y <= 0:
        return [], 0

    if cfg.infill_pattern == "honeycomb":
        candidates = hex_points(cfg.infill_spacing, half_x, half_y)
    elif cfg.infill_pattern == "diagonal":
        pad = half_x + half_y  # generous - after a 45deg rotation the corners need more source points
        nx = int((half_x + pad) // cfg.infill_spacing) + 2
        ny = int((half_y + pad) // cfg.infill_spacing) + 2
        raw = grid_points(nx * 2 + 1, cfg.infill_spacing, ny * 2 + 1, cfg.infill_spacing)
        candidates = [rotate(x, y, 45) for (x, y) in raw]
    else:  # "grid"
        nx = int(half_x // cfg.infill_spacing) + 1
        ny = int(half_y // cfg.infill_spacing) + 1
        candidates = grid_points(nx * 2 + 1, cfg.infill_spacing, ny * 2 + 1, cfg.infill_spacing)

    feature_radius = cfg.infill_cut_width / 2.0

    exclusions = mounting_hole_exclusions(cfg) + gridfinity_exclusions(cfg)
    for (x, y) in custom_hole_points:
        if cfg.hole_shape == "slot":
            bounding_r = (cfg.hole_diameter + cfg.hole_slot_length) / 2.0
        else:
            bounding_r = cfg.hole_diameter / 2.0
        exclusions.append((x, y, bounding_r))

    kept, skipped = [], 0
    for (x, y) in candidates:
        if abs(x) > half_x or abs(y) > half_y:
            continue  # simply outside the field - not a collision, don't count it
        if circle_ok(x, y, feature_radius, exclusions, cfg.min_clearance):
            kept.append((x, y))
        else:
            skipped += 1

    if len(kept) > PanelConfig.MAX_INFILL_FEATURES:
        raise ValueError(
            f"infill pattern would cut {len(kept)} features (> {PanelConfig.MAX_INFILL_FEATURES} safety cap). "
            "Increase infill_spacing."
        )

    return kept, skipped


def quadrant_masks_bounds(cfg: PanelConfig):
    """Bounding box (min_x, min_y, max_x, max_y) per quadrant, matching the
    +-50mm overlap margin used for the boolean intersect masks in the
    generator, so the preview's exploded view lines up with real output."""
    half_x, half_y = cfg.length / 2.0, cfg.width / 2.0
    return {
        "Q1_TopRight": (0, 0, half_x, half_y),
        "Q2_TopLeft": (-half_x, 0, 0, half_y),
        "Q3_BottomLeft": (-half_x, -half_y, 0, 0),
        "Q4_BottomRight": (0, -half_y, half_x, 0),
    }
