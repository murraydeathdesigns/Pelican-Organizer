"""
Pelican 1606 Organizer Lid Generator
-------------------------------------
Small desktop GUI (Tkinter) that drives CadQuery to generate a 4-panel,
lap-jointed organizer baseplate sized to the Pelican 1606 lid interior,
with an optional Gridfinity pocket grid (with magnet holes) on one or
all quadrants.

Output: STEP files (one per quadrant), optionally also STL.

This file is intentionally unchanged from the working version - the
GitHub Actions workflow in .github/workflows/build-windows.yml turns it
into a standalone PelicanOrganizer.exe automatically, so nothing here
needs to be edited for the build to succeed. Edit ui/geometry logic here
directly if you want to change behavior; every push to GitHub will
rebuild the .exe.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cadquery as cq


class PelicanOrganizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pelican 1606 STEP Generator")
        self.geometry("520x620")
        self.resizable(False, False)

        # Variables
        self.var_length = tk.DoubleVar(value=617.0)
        self.var_width = tk.DoubleVar(value=494.0)
        self.var_thickness = tk.DoubleVar(value=5.5)
        self.var_gridfinity = tk.BooleanVar(value=True)
        self.var_q3_only = tk.BooleanVar(value=True)
        self.var_magnets = tk.BooleanVar(value=True)
        self.var_export_stl = tk.BooleanVar(value=False)
        self.var_out_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop"))

        self._build_ui()

    def _build_ui(self):
        pad = {'padx': 12, 'pady': 6}

        # Dimensions Group
        f_dim = ttk.LabelFrame(self, text="Envelope & Base Dimensions (mm)")
        f_dim.pack(fill="x", **pad)
        ttk.Label(f_dim, text="Length (X):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(f_dim, textvariable=self.var_length, width=12).grid(row=0, column=1, sticky="w")
        ttk.Label(f_dim, text="Width (Y):").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(f_dim, textvariable=self.var_width, width=12).grid(row=1, column=1, sticky="w")
        ttk.Label(f_dim, text="Thickness:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(f_dim, textvariable=self.var_thickness, width=12).grid(row=2, column=1, sticky="w")

        # Gridfinity Options
        f_gf = ttk.LabelFrame(self, text="Gridfinity Configuration")
        f_gf.pack(fill="x", **pad)
        ttk.Checkbutton(f_gf, text="Enable Gridfinity Baseplate", variable=self.var_gridfinity).pack(anchor="w", padx=6, pady=3)
        ttk.Checkbutton(f_gf, text="Apply to Q3 (Bottom-Left) Only", variable=self.var_q3_only).pack(anchor="w", padx=6, pady=3)
        ttk.Checkbutton(f_gf, text="Add 6x2mm Magnet/Screw Holes", variable=self.var_magnets).pack(anchor="w", padx=6, pady=3)

        # Export Format Options
        f_exp = ttk.LabelFrame(self, text="Export Options")
        f_exp.pack(fill="x", **pad)
        ttk.Checkbutton(f_exp, text="Also export STL mesh (for slicer preview)", variable=self.var_export_stl).pack(anchor="w", padx=6, pady=3)
        f_dir = ttk.Frame(f_exp)
        f_dir.pack(fill="x", padx=6, pady=6)
        ttk.Entry(f_dir, textvariable=self.var_out_dir).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(f_dir, text="Browse...", command=self._browse_dir).pack(side="right")

        # Generate Button & Status
        self.btn_generate = ttk.Button(self, text="Generate & Export STEP Files", command=self._start_generation)
        self.btn_generate.pack(fill="x", padx=12, pady=12)

        self.lbl_status = ttk.Label(self, text="Ready", foreground="gray")
        self.lbl_status.pack(pady=4)

        self.progress = ttk.Progressbar(self, mode="indeterminate")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.var_out_dir.get())
        if d:
            self.var_out_dir.set(d)

    def _start_generation(self):
        self.btn_generate.config(state="disabled")
        self.progress.pack(fill="x", padx=12, pady=4)
        self.progress.start()
        self.lbl_status.config(text="Computing CAD geometry... (this takes ~15-30s)", foreground="blue")

        thread = threading.Thread(target=self._run_cad)
        thread.start()

    def _run_cad(self):
        try:
            length = self.var_length.get()
            width = self.var_width.get()
            thickness = self.var_thickness.get()
            enable_gf = self.var_gridfinity.get()
            q3_only = self.var_q3_only.get()
            add_mags = self.var_magnets.get()
            out_dir = self.var_out_dir.get()
            export_stl = self.var_export_stl.get()

            os.makedirs(out_dir, exist_ok=True)

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

            # Gridfinity or M4 Grid
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

                if export_stl:
                    stl_path = os.path.join(out_dir, f"Pelican_1606_{q_name}.stl")
                    cq.exporters.export(solid, stl_path)

            self.after(0, self._on_success, out_dir)
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _on_success(self, out_dir):
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_generate.config(state="normal")
        self.lbl_status.config(text="Export completed successfully!", foreground="green")
        messagebox.showinfo("Complete", f"STEP files successfully exported to:\n{out_dir}")

    def _on_error(self, err_msg):
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_generate.config(state="normal")
        self.lbl_status.config(text="Error occurred", foreground="red")
        messagebox.showerror("CAD Error", f"An error occurred during generation:\n{err_msg}")


if __name__ == "__main__":
    app = PelicanOrganizerApp()
    app.mainloop()
