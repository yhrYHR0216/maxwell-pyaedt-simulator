#!/usr/bin/env python
"""Parameterized Maxwell 3D Magnetostatic solenoid simulation built with PyAEDT.

Adapt this template when translating a natural-language request into code.
Every user-tunable value lives in CONFIG below. Keep the structure:
launch -> geometry -> materials -> excitation -> parameters -> mesh -> setup
-> analyze -> post-process -> export -> save.

Run:  python template_maxwell3d_magnetostatic.py
Requires: pyaedt (or ansys.aedt.core) and a local Ansys Electronics Desktop.
"""

import os
import traceback
from pathlib import Path

# ---- User-editable configuration -------------------------------------------
CONFIG = {
    "project_name": "Solenoid_3D",
    "design_name": "MagStatic_Solenoid",
    "solution_type": "Magnetostatic",      # "Magnetostatic" | "AC Magnetic" | "Transient" | ...
    "version": "2025.1",                   # AEDT version string or None for latest
    "non_graphical": False,                # True for batch/headless run
    "close_on_exit": True,

    "geometry": {
        "units": "mm",
        "core_radius": "6mm",              # fixed core cylinder
        "core_height": "15mm",
        "plugnut_height": "5mm",           # movable armature below the core
        "coil_radius_inner": "8mm",
        "coil_radius_outer": "12mm",
        "coil_height": "13mm",
        "coil_z_center": "7.5mm",
        "yoke_thickness": "4mm",
        "yoke_box": "30mm",                # bottom return-path plate size
        "region_pad": "50%",
    },
    "materials": {
        "core": "steel_1008",
        "plugnut": "steel_1008",
        "coil": "copper",
        "yoke": "steel_1008",
        "region": "vacuum",
    },
    "excitations": {
        "coil_current": "1A",              # total ampere-turns on coil terminal face
        "swap_direction": False,
    },
    "parameters": {
        "force_objects": ["plugnut"],      # force computed on these objects
        "force_virtual": True,
    },
    "mesh": {
        "core_max_length": "1mm",          # None disables the length op
    },
    "setup": {
        "name": "Setup1",
        "max_passes": 10,
        "min_passes": 2,
        "min_converged_passes": 1,
        "percent_refinement": 30,
        "percent_error": 1,                # convergence target in percent
    },
    "post_processing": {
        "output_dir": "results",
        "field_quantities": ["Mag_B"],     # volume field plots to create + export
        "report_expressions": [["Force1.Force_mag", "Force1.Force_z"]],
    },
}


def launch():
    try:
        from ansys.aedt.core import Maxwell3d
    except ImportError:
        from pyaedt import Maxwell3d
    return Maxwell3d(
        project=CONFIG["project_name"],
        design=CONFIG["design_name"],
        solution_type=CONFIG["solution_type"],
        version=CONFIG["version"],
        non_graphical=CONFIG["non_graphical"],
        new_desktop=True,
        close_on_exit=CONFIG["close_on_exit"],
    )


def _mm(value):
    """Strip a 'mm' unit suffix and return the float in model units."""
    return float(str(value).replace("mm", ""))


def build_geometry(m3d, g):
    """Create core, plugnut, hollow coil, bottom yoke, and background region."""
    modeler = m3d.modeler
    mats = CONFIG["materials"]

    ph = _mm(g["plugnut_height"])   # plugnut height / yoke z-offset
    ch = _mm(g["coil_height"])
    yb = _mm(g["yoke_box"])
    yt = _mm(g["yoke_thickness"])

    # Fixed core cylinder on the Z axis (z in [0, core_height]).
    core = modeler.create_cylinder(
        "Z", [0, 0, 0], g["core_radius"], g["core_height"],
        name="core", material=mats["core"])
    if not core:
        raise RuntimeError("Failed to create 'core' cylinder.")

    # Movable plugnut (armature) below the core (z in [-ph, 0]).
    plugnut = modeler.create_cylinder(
        "Z", [0, 0, -ph], g["core_radius"], g["plugnut_height"],
        name="plugnut", material=mats["plugnut"])
    if not plugnut:
        raise RuntimeError("Failed to create 'plugnut' cylinder.")

    # Hollow coil: outer cylinder minus inner cylinder -> copper tube.
    coil = modeler.create_cylinder(
        "Z", [0, 0, -ch / 2], g["coil_radius_outer"], g["coil_height"],
        name="coil", material=mats["coil"])
    inner = modeler.create_cylinder(
        "Z", [0, 0, -ch / 2], g["coil_radius_inner"], g["coil_height"],
        name="coil_inner_tool", material=mats["coil"])
    if not modeler.subtract(blank_list="coil", tool_list="coil_inner_tool", keep_originals=False):
        raise RuntimeError("Failed to hollow the coil (subtract).")

    # Bottom yoke return-path plate under the plugnut (z in [-(ph+yt), -ph]).
    yoke = modeler.create_box(
        [-yb / 2, -yb / 2, -(ph + yt)], [yb, yb, yt],
        name="yoke", material=mats["yoke"])
    if not yoke:
        raise RuntimeError("Failed to create 'yoke' box.")

    # Background region.
    modeler.create_region(pad_value=g["region_pad"], pad_type="Percentage Offset", name="Region")
    return {"core": core, "plugnut": plugnut, "coil": coil, "yoke": yoke}


def coil_terminal_face(m3d, object_name):
    """Return the face ID of the coil's top annular face (max Z centroid)."""
    face_ids = m3d.modeler.get_object_faces(object_name)
    if not face_ids:
        raise RuntimeError(f"No faces found on '{object_name}'.")
    top = max(face_ids, key=lambda fid: m3d.modeler.get_face_center(fid)[2])
    return top


def apply_excitation(m3d):
    """Assign the coil current on the coil's terminal face."""
    face = coil_terminal_face(m3d, "coil")
    current = m3d.assign_current(
        [face], amplitude=CONFIG["excitations"]["coil_current"],
        solid=True, swap_direction=CONFIG["excitations"]["swap_direction"],
        name="Current1")
    if not current:
        raise RuntimeError("Failed to assign current excitation on the coil face.")


def apply_solution_parameters(m3d):
    """Request force computation on the configured objects."""
    objs = CONFIG["parameters"]["force_objects"]
    force = m3d.assign_force(objs, coordinate_system="Global",
                             is_virtual=CONFIG["parameters"]["force_virtual"],
                             force_name="Force1")
    if not force:
        raise RuntimeError(f"Failed to assign force on {objs}.")


def apply_mesh(m3d):
    """Optional length-based refinement on the magnetic core."""
    max_len = CONFIG["mesh"].get("core_max_length")
    if max_len:
        op = m3d.mesh.assign_length_mesh(
            ["core", "plugnut"], inside_selection=True, maximum_length=max_len, name="LenCore")
        if not op:
            raise RuntimeError("Failed to assign length mesh on core/plugnut.")


def create_setup(m3d):
    """Create the adaptive magnetostatic solve setup from CONFIG."""
    s = CONFIG["setup"]
    setup = m3d.create_setup(name=s["name"])
    props = setup.props
    props["MaximumPasses"] = s["max_passes"]
    props["MinimumPasses"] = s["min_passes"]
    props["MinimumConvergedPasses"] = s["min_converged_passes"]
    props["PercentRefinement"] = s["percent_refinement"]
    props["PercentError"] = s["percent_error"]
    props["SolveMatrixAtLast"] = True
    setup.update()
    return setup


def post_process(m3d, out_dir):
    """Field plots, force report, and numeric extraction."""
    pp = m3d.post
    solution = f"{CONFIG['setup']['name']} : LastAdaptive"

    # Field plots on the magnetic parts.
    for quantity in CONFIG["post_processing"]["field_quantities"]:
        plot_name = f"{quantity}_volume"
        fp = pp.create_fieldplot_volume(
            ["core", "plugnut", "yoke"], quantity=quantity,
            setup=solution, plot_name=plot_name)
        if fp:
            img = out_dir / f"{plot_name}.png"
            try:
                fp.export_image(full_path=str(img), width=1280, height=720,
                                orientation="isometric", show_region=False)
            except Exception as exc:  # image export is best-effort
                print(f"[warn] field plot image export failed: {exc}")
            pp.export_field_plot(plot_name, out_dir, file_name=plot_name, file_format="aedtplt")

    # Force report + CSV.
    for expressions in CONFIG["post_processing"]["report_expressions"]:
        rep = pp.create_report(
            expressions=expressions, setup_sweep_name=solution,
            domain="Sweep", plot_name="ForceReport", show=False)
        if rep:
            try:
                pp.export_report_to_jpg(str(out_dir), "ForceReport", 800, 450)
                pp.export_report_to_csv(str(out_dir), "ForceReport")
            except Exception as exc:
                print(f"[warn] report export failed: {exc}")
        # Numeric summary from the solution data.
        sd = pp.get_solution_data(expressions=expressions, setup_sweep_name=solution,
                                  domain="Sweep")
        if sd:
            vals = sd.data_real()
            print(f"[info] {expressions} values: {vals}")
            with (out_dir / "results_summary.txt").open("a", encoding="utf-8") as fh:
                fh.write(f"{expressions}: {vals}\n")


def main():
    out_dir = Path(CONFIG["post_processing"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    m3d = None
    try:
        m3d = launch()
        print(f"[info] design: {m3d.design_name}, solution: {m3d.solution_type}")

        build_geometry(m3d, CONFIG["geometry"])
        apply_excitation(m3d)
        apply_solution_parameters(m3d)
        apply_mesh(m3d)
        create_setup(m3d)

        m3d.validate_simple()
        if not m3d.analyze(setup=CONFIG["setup"]["name"]):
            raise RuntimeError("Solve failed (analyze returned False).")

        post_process(m3d, out_dir)
        print("[info] simulation completed successfully.")
    except Exception:
        traceback.print_exc()
        raise
    finally:
        if m3d is not None:
            try:
                m3d.save_project()
                print(f"[info] project saved: {m3d.project_file}")
            except Exception as exc:
                print(f"[warn] project save failed: {exc}")
            if CONFIG["close_on_exit"]:
                m3d.close_desktop()


if __name__ == "__main__":
    main()
