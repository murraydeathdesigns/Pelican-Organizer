// Shared 2D layout math for the Pelican 1606 organizer panel generator.
// JavaScript port of panel_layout.py - keep these two files in exact sync.
// Function-for-function mirror; see panel_layout.py for the authoritative
// explanation of what each one does.

function evenlySpaced(count, spacing) {
  if (count <= 1) return [0.0];
  const span = spacing * (count - 1);
  const start = -span / 2.0;
  const out = [];
  for (let i = 0; i < count; i++) out.push(start + i * spacing);
  return out;
}

function gridPoints(countX, spacingX, countY, spacingY) {
  const xs = evenlySpaced(countX, spacingX);
  const ys = evenlySpaced(countY, spacingY);
  const out = [];
  for (const x of xs) for (const y of ys) out.push([x, y]);
  return out;
}

function rotatePoint(x, y, angleDeg) {
  const a = (angleDeg * Math.PI) / 180.0;
  return [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];
}

function hexPoints(spacing, halfX, halfY) {
  const rowH = (spacing * Math.sqrt(3)) / 2.0;
  if (rowH <= 0 || spacing <= 0) return [];
  const maxRow = Math.floor((halfY + spacing) / rowH) + 1;
  const maxCol = Math.floor((halfX + spacing) / spacing) + 1;
  const points = [];
  for (let j = -maxRow; j <= maxRow; j++) {
    const y = j * rowH;
    const xOffset = j % 2 !== 0 ? spacing / 2.0 : 0.0;
    for (let i = -maxCol; i <= maxCol; i++) {
      const x = i * spacing + xOffset;
      points.push([x, y]);
    }
  }
  return points;
}

function distPointToSegment(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const segLenSq = dx * dx + dy * dy;
  if (segLenSq === 0) return Math.hypot(px - ax, py - ay);
  let t = ((px - ax) * dx + (py - ay) * dy) / segLenSq;
  t = Math.max(0.0, Math.min(1.0, t));
  const cx = ax + t * dx, cy = ay + t * dy;
  return Math.hypot(px - cx, py - cy);
}

function circleOk(x, y, radius, exclusions, clearance) {
  for (const [cx, cy, cr] of exclusions) {
    if (Math.hypot(x - cx, y - cy) < radius + cr + clearance) return false;
  }
  return true;
}

function slotOk(x, y, halfLength, axis, halfWidth, exclusions, clearance) {
  let ax, ay, bx, by;
  if (axis === "y") {
    ax = x; ay = y - halfLength; bx = x; by = y + halfLength;
  } else {
    ax = x - halfLength; ay = y; bx = x + halfLength; by = y;
  }
  for (const [cx, cy, cr] of exclusions) {
    if (distPointToSegment(cx, cy, ax, ay, bx, by) < halfWidth + cr + clearance) return false;
  }
  return true;
}

const DEFAULT_CONFIG = {
  length: 617.0,
  width: 494.0,
  thickness: 5.5,
  cornerRadius: 25.4,

  mountOffset: 25.0,
  cbThroughDia: 4.5,
  cbDia: 8.5,
  cbDepth: 2.5,

  enableGridfinity: true,
  gridfinityQ3Only: true,
  gridfinityMagnets: true,

  enableHoles: false,
  holeShape: "round",
  holeDiameter: 5.0,
  holeSlotLength: 10.0,
  holeSlotAxis: "x",
  holeCountX: 4,
  holeCountY: 3,
  holeSpacingX: 80.0,
  holeSpacingY: 80.0,
  holeFieldMargin: 20.0,

  infillPattern: "none",
  infillSpacing: 20.0,
  infillCutWidth: 10.0,
  infillFieldMargin: 20.0,

  minClearance: 1.5,
};

const MAX_INFILL_FEATURES = 5000;

function mountingHolePoints(cfg) {
  const mx = cfg.length / 2.0 - cfg.mountOffset;
  const my = cfg.width / 2.0 - cfg.mountOffset;
  return [
    [mx, my], [-mx, my], [-mx, -my], [mx, -my], [0, my], [0, -my],
  ];
}

function mountingHoleExclusions(cfg) {
  const r = cfg.cbDia / 2.0;
  return mountingHolePoints(cfg).map(([x, y]) => [x, y, r]);
}

function fitAndCenter(spacing, lo, hi) {
  const span = hi - lo;
  if (span <= 0 || spacing <= 0) return [];
  let count = Math.max(1, Math.floor(span / spacing) + 1);
  while (count > 1 && spacing * (count - 1) > span) count--;
  const center = (lo + hi) / 2.0;
  return evenlySpaced(count, spacing).map((p) => center + p);
}

// gridfinityQ3Only=true fills just the bottom-left quadrant. false fills
// all 4, each gridded independently so no 41.5mm cell body ever crosses
// a quadrant seam. See panel_layout.py's gridfinity_cells() for the
// full explanation - keep this in exact sync with that function.
function gridfinityCells(cfg) {
  if (!cfg.enableGridfinity) return [];
  const pitch = 42.0;
  const cellHalf = 41.5 / 2.0;
  const margin = cellHalf + 4.0;
  const seam = cellHalf + 4.0;
  const halfX = cfg.length / 2.0, halfY = cfg.width / 2.0;

  function quadrantGrid(xLo, xHi, yLo, yHi) {
    const xs = fitAndCenter(pitch, xLo, xHi);
    const ys = fitAndCenter(pitch, yLo, yHi);
    const pts = [];
    for (const x of xs) for (const y of ys) pts.push([x, y]);
    return pts;
  }

  const q3 = quadrantGrid(-halfX + margin, -seam, -halfY + margin, -seam);
  if (cfg.gridfinityQ3Only) return q3;

  const q1 = quadrantGrid(seam, halfX - margin, seam, halfY - margin);
  const q2 = quadrantGrid(-halfX + margin, -seam, seam, halfY - margin);
  const q4 = quadrantGrid(seam, halfX - margin, -halfY + margin, -seam);
  return q3.concat(q1, q2, q4);
}

// Bounding circles around each Gridfinity cell (half-diagonal of the
// 41.5mm square) - keeps custom holes / infill from cutting into a
// pocket floor. See panel_layout.py's gridfinity_exclusions().
function gridfinityExclusions(cfg) {
  const r = (41.5 / 2.0) * Math.sqrt(2);
  return gridfinityCells(cfg).map(([x, y]) => [x, y, r]);
}

// True if this hole's own body would straddle the x=0/y=0 quadrant seam
// (an odd hole count places one hole exactly on a seam by construction of
// the centered spacing). Only applied to the custom hole pattern - infill
// crossing a seam is fine, it's decorative not functional. See
// panel_layout.py's _crosses_seam() for the full explanation.
function crossesSeam(cfg, x, y) {
  let halfExtentX, halfExtentY;
  if (cfg.holeShape === "slot") {
    const halfLen = cfg.holeSlotLength / 2.0 + cfg.holeDiameter / 2.0;
    const halfW = cfg.holeDiameter / 2.0;
    if (cfg.holeSlotAxis === "x") { halfExtentX = halfLen; halfExtentY = halfW; }
    else { halfExtentX = halfW; halfExtentY = halfLen; }
  } else {
    halfExtentX = halfExtentY = cfg.holeDiameter / 2.0;
  }
  return Math.abs(x) < halfExtentX + cfg.minClearance || Math.abs(y) < halfExtentY + cfg.minClearance;
}

function computeCustomHoles(cfg) {
  if (!cfg.enableHoles) return { kept: [], skipped: 0 };

  const candidates = gridPoints(cfg.holeCountX, cfg.holeSpacingX, cfg.holeCountY, cfg.holeSpacingY);
  const exclusions = mountingHoleExclusions(cfg).concat(gridfinityExclusions(cfg));
  const halfX = cfg.length / 2.0 - cfg.holeFieldMargin;
  const halfY = cfg.width / 2.0 - cfg.holeFieldMargin;

  const kept = [];
  let skipped = 0;
  for (const [x, y] of candidates) {
    if (Math.abs(x) > halfX || Math.abs(y) > halfY || crossesSeam(cfg, x, y)) { skipped++; continue; }
    let ok;
    if (cfg.holeShape === "slot") {
      ok = slotOk(x, y, cfg.holeSlotLength / 2.0, cfg.holeSlotAxis, cfg.holeDiameter / 2.0, exclusions, cfg.minClearance);
    } else {
      ok = circleOk(x, y, cfg.holeDiameter / 2.0, exclusions, cfg.minClearance);
    }
    if (ok) kept.push([x, y]); else skipped++;
  }
  return { kept, skipped };
}

function computeInfill(cfg, customHolePoints) {
  if (cfg.infillPattern === "none" || cfg.infillSpacing <= 0) return { kept: [], skipped: 0, capped: false };

  const halfX = cfg.length / 2.0 - cfg.infillFieldMargin;
  const halfY = cfg.width / 2.0 - cfg.infillFieldMargin;
  if (halfX <= 0 || halfY <= 0) return { kept: [], skipped: 0, capped: false };

  let candidates;
  if (cfg.infillPattern === "honeycomb") {
    candidates = hexPoints(cfg.infillSpacing, halfX, halfY);
  } else if (cfg.infillPattern === "diagonal") {
    const pad = halfX + halfY;
    const nx = Math.floor((halfX + pad) / cfg.infillSpacing) + 2;
    const ny = Math.floor((halfY + pad) / cfg.infillSpacing) + 2;
    const raw = gridPoints(nx * 2 + 1, cfg.infillSpacing, ny * 2 + 1, cfg.infillSpacing);
    candidates = raw.map(([x, y]) => rotatePoint(x, y, 45));
  } else {
    const nx = Math.floor(halfX / cfg.infillSpacing) + 1;
    const ny = Math.floor(halfY / cfg.infillSpacing) + 1;
    candidates = gridPoints(nx * 2 + 1, cfg.infillSpacing, ny * 2 + 1, cfg.infillSpacing);
  }

  const featureRadius = cfg.infillCutWidth / 2.0;

  const exclusions = mountingHoleExclusions(cfg).concat(gridfinityExclusions(cfg));
  for (const [x, y] of customHolePoints) {
    const boundingR = cfg.holeShape === "slot"
      ? (cfg.holeDiameter + cfg.holeSlotLength) / 2.0
      : cfg.holeDiameter / 2.0;
    exclusions.push([x, y, boundingR]);
  }

  const kept = [];
  let skipped = 0;
  for (const [x, y] of candidates) {
    if (Math.abs(x) > halfX || Math.abs(y) > halfY) continue;
    if (circleOk(x, y, featureRadius, exclusions, cfg.minClearance)) kept.push([x, y]);
    else skipped++;
  }

  const capped = kept.length > MAX_INFILL_FEATURES;
  return { kept: capped ? kept.slice(0, MAX_INFILL_FEATURES) : kept, skipped, capped, total: kept.length };
}

function quadrantBounds(cfg) {
  const halfX = cfg.length / 2.0, halfY = cfg.width / 2.0;
  return {
    Q1_TopRight: [0, 0, halfX, halfY],
    Q2_TopLeft: [-halfX, 0, 0, halfY],
    Q3_BottomLeft: [-halfX, -halfY, 0, 0],
    Q4_BottomRight: [0, -halfY, halfX, 0],
  };
}

if (typeof module !== "undefined") {
  module.exports = {
    evenlySpaced, gridPoints, rotatePoint, hexPoints, distPointToSegment,
    circleOk, slotOk, DEFAULT_CONFIG, mountingHolePoints, mountingHoleExclusions,
    gridfinityCells, gridfinityExclusions, crossesSeam, computeCustomHoles, computeInfill, quadrantBounds, MAX_INFILL_FEATURES,
  };
}
