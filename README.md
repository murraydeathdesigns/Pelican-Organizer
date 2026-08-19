# Pelican 1606 Organizer

Generates STEP files for a 4-panel, lap-jointed organizer baseplate
sized to a Pelican 1606 lid, with an optional Gridfinity pocket grid,
a customizable hole pattern (round or elongated/slot, evenly spaced),
and an infill pattern (grid / honeycomb / diagonal) cut into the panel
instead of leaving it solid.

## Preview before you build (`preview.html`)

Open `preview.html` in any browser — no install, no CadQuery, works
offline. It's a live 2D layout tool: every parameter has a form field,
and the drawing updates instantly as you change them. Use it to dial
in dimensions, hole counts/spacing, and infill before spending a CI
run on the real 3D build.

- **Assembled plate / Separate pieces** toggle at the top switches
  between the full lid and the 4 individual quadrant pieces (as they'll
  actually come out of the STEP export), each with a dashed line
  showing roughly where its lap-joint overlap is.
- Every hole and infill feature shown is guaranteed collision-safe:
  the same math that draws the preview also drives the real generator,
  so what you see is what you'll get. Specifically, the tool
  automatically keeps new holes/infill clear of:
  - the 6 fixed perimeter mounting holes
  - the Gridfinity pockets (if enabled)
  - each other (custom holes vs. infill)
  - the quadrant split lines (custom holes only — a hole placed exactly
    on a seam would get physically cut in half when the plate splits
    into quadrants; infill is decorative, so it's fine for it to
    continue across a seam)
- Any candidate that would collide gets silently skipped, and the
  stats bar above the drawing tells you how many were skipped so you
  can tell if your spacing is too tight for the space available.

## Generating the real STEP files (GitHub Actions)

Same reasoning as before: CadQuery needs a real Windows-or-Linux
Python environment to run, which this chat can't do locally, so
GitHub's servers do it for you for free. You need a (free) GitHub
account, but never install anything yourself.

1. Repo already set up at `murraydeathdesigns/Pelican-Organizer`? Just
   upload/overwrite the changed files (drag onto the repo's file list,
   or use "Add file → Upload files"). New/changed files this round:
   `panel_layout.py`, `generate_step_files.py`, `preview.html`,
   `.github/workflows/generate-step-files.yml`.
2. Actions tab → "Generate STEP Files" → "Run workflow". A form pops
   up with every parameter (dimensions, Gridfinity, custom holes,
   infill) — set them to match whatever you liked in the preview, or
   leave the defaults.
3. Wait under a minute (it's a plain script run, no exe-building).
4. Open the finished run → download the `Pelican-1606-STEP-files`
   artifact. That's your four `Pelican_1606_Q*.step` files.

### Parameters

| Group | Field | Notes |
|---|---|---|
| Panel | length / width / thickness | mm |
| Gridfinity | enable / bottom-left-only / magnets | 42mm pitch, 6x5 max grid |
| Custom holes | shape | `round` or `slot` (elongated) |
| | diameter | hole diameter, or slot width |
| | slot extra length | slot only — added to diameter for total end-to-end length |
| | slot axis | slot only — `x` or `y` |
| | count X / Y, spacing X / Y | holes are always evenly spaced and centered by count + spacing, not a fixed grid pitch |
| Infill | pattern | `none`, `grid` (round holes), `honeycomb` (hex cells), `diagonal` (45°-rotated grid) |
| | spacing | pitch between features |
| | feature size | hole diameter, or hexagon flat-to-flat width |

`panel_layout.py` is the single source of truth for all of this
geometry math (positions, spacing, collision checks) — both
`generate_step_files.py` (real 3D cuts) and `preview.html`'s inlined
JavaScript (`panel_layout.js`, kept in exact sync) implement the exact
same algorithm, cross-checked against each other during development.

## If the build fails (red X instead of green check)

Click into the failed run, open whichever step is marked with a red X,
and copy the red error text back — I'll adjust the script and you
re-upload just the changed file(s).

## Also included: standalone Windows .exe build (optional, unrelated path)

`organizer_app.py` + `build_windows.py` + `stub_casadi.py` +
`.github/workflows/build-windows.yml` build a double-clickable Windows
GUI app instead of just STEP files, via the same GitHub Actions
approach. This predates the preview/infill/custom-hole features above
and hasn't been updated to include them — it's left in the repo in
case you want a real desktop app later, but the STEP-file workflow
above is the actively maintained path.
