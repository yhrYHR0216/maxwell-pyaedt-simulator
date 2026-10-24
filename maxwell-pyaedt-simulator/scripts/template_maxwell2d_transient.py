#!/usr/bin/env python
"""Parameterized Maxwell 2D Transient rotational actuator simulation (PyAEDT).

Cylindrical-about-Z (r-z) cross-section: a rotor inside a stator with one
current-excited coil in the air gap. The rotor sits in a motion band and a
torque parameter is computed on it. Adapt this template when translating a
natural-language request into code; every tunable value is in CONFIG.

Run:  python template_maxwell2d_transient.py
Requires: pyaedt (or ansys.aedt.core) and a local Ansys Electronics Desktop.
"""

import traceback
from pathlib import Path

# ---- User-editable configuration -------------------------------------------
CONFIG = {
    "project_name": "Actuator_2D",
    "design_name": "Transient_RotActuator",
    "solution_type": "TransientZ",         # "TransientZ" (cylindrical) | "TransientXY" (Cartesian)
    "version": "2025.1",
    "non_graphical": False,
    "close_on_exit": True,

    "geometry": {
        "units": "mm",
        "rotor_radius": "10mm",
        "rotor_height": "20mm",
        "rotor_z_center": "0mm",
        "stator_radius_inner": "14mm",
        "stator_radius_outer": "26mm",
        "stator_z_half": "15mm",
        "coil_radius_inner": "10.5mm",
        "coil_radius_outer": "13mm",
        "coil_z_half": "12mm",
        "band_clearance": "1mm",           # band pad around the rotor
        "region_pad": "50%",
    },
    "materials": {
        "rotor": "steel_1008",
        "stator": "steel_1008",
        "coil": "copper",
        "region": "vacuum",
    },
    "excitations": {
        "winding_type": "Current",         # "Current" | "Voltage" | "External"
        "winding_current": "1A",
        "winding_resistance": "0ohm",
        "winding_inductance": "0nH",
        "winding_voltage": "0mV",
        "is_solid": True,
        "parallel_branches": 1,
        "coil_conductors": 1,
    },
    "motion": {
        "move_type": "Rotate",             # "Rotate" | "Translate"
        "axis": "Z",
        "is_positive": True,
        "init_pos": "0deg",
        "angular_velocity": "0deg_per_sec",
        "has_limit": False,
        "consider_mechanical_transient": False,
    },
    "parameters": {
        "torque_objects": ["rotor"],
        "torque_axis": "Z",
        "is_virtual": True,
    },
    "setup": {
        "name": "Setup1",
        "stop_time": "10ms",
        "time_step": "0.05ms",
        "save_fields": True,
    },
    "post_processing": {
        "output_dir": "results",
        "field_quantities": ["Mag_B"],
        "plot_time": "0.01s",               # intrinsic time for transient field plots
        "report_expressions": [["Torque1.Torque_mag", "Torque1.Torque_z"]],
    },
}


def launch():
    try:
        from ansys.aedt.core import Maxwell2d
    except ImportError:
        from pyaedt import Maxwell2d
    return Maxwell2d(
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
    """Rotor, stator, air-gap coil, motion band, and background region."""
    modeler = m3d.modeler
    mats = CONFIG["materials"]

    # All dimensions in mm (floats after unit-stripping).
    rr, rh = _mm(g["rotor_radius"]), _mm(g["rotor_height"])
    sri, sro, sz = (_mm(g["stator_radius_inner"]), _mm(g["stator_radius_outer"]),
                    _mm(g["stator_z_half"]))
    cri, cro, cz = (_mm(g["coil_radius_inner"]), _mm(g["coil_radius_outer"]),
                    _mm(g["coil_z_half"]))
    bc = _mm(g["band_clearance"])

    # Rotor (moving): rectangle in the model plane, r in [0, rotor_radius].
    rotor = modeler.create_rectangle(
        [0, -rh / 2], [rr, rh],
        name="rotor", material=mats["rotor"])
    if not rotor:
        raise RuntimeError("Failed to create 'rotor'.")

    # Stator (stationary): annulus cross-section.
    stator = modeler.create_rectangle(
        [sri, -sz], [sro - sri, 2 * sz],
        name="stator", material=mats["stator"])
    if not stator:
        raise RuntimeError("Failed to create 'stator'.")

    # Coil in the air gap (stationary, current-excited).
    coil = modeler.create_rectangle(
        [cri, -cz], [cro - cri, 2 * cz],
        name="coil", material=mats["coil"])
    if not coil:
        raise RuntimeError("Failed to create 'coil'.")

    # Band enclosing the moving rotor only.
    band = modeler.create_rectangle(
        [0, -rh / 2 - bc], [rr + bc, rh + 2 * bc],
        name="band", material="vacuum")
    if not band:
        raise RuntimeError("Failed to create 'band'.")

    modeler.create_region(pad_value=g["region_pad"], pad_type="Percentage Offset", name="Region")
    return {"rotor": rotor, "stator": stator, "coil": coil, "band": band}


def apply_excitation(m3d):
    """Winding group + coil terminal on the coil cross-section."""
    ex = CONFIG["excitations"]
    winding = m3d.assign_winding(
        name="Winding1", winding_type=ex["winding_type"], is_solid=ex["is_solid"],
        current=ex["winding_current"], resistance=ex["winding_resistance"],
        inductance=ex["winding_inductance"], voltage=ex["winding_voltage"],
        parallel_branches=ex["parallel_branches"])
    if not winding:
        raise RuntimeError("Failed to assign winding 'Winding1'.")
    coil = m3d.assign_coil(assignment=["coil"], conductors_number=ex["coil_conductors"],
                          polarity="Positive", name="Coil1")
    if not coil:
        raise RuntimeError("Failed to assign coil terminal 'Coil1'.")


def apply_motion(m3d):
    """Assign the motion band via the raw MotionSetup module."""
    mo = CONFIG["motion"]
    oMotion = m3d.odesign.GetModule("MotionSetup")
    oMotion.AssignBand([
        "NAME:Data",
        "Move Type:=", mo["move_type"],
        "Coordinate System:=", "Global",
        "Axis:=", mo["axis"],
        "Is Positive:=", mo["is_positive"],
        "InitPos:=", mo["init_pos"],
        "HasRotateLimit:=", mo["has_limit"],
        "NonCylindrical:=", False,
        "Consider Mechanical Transient:=", mo["consider_mechanical_transient"],
        "Angular Velocity:=", mo["angular_velocity"],
        "Objects:=", ["band"],
    ])


def apply_solution_parameters(m3d):
    """Torque on the moving rotor."""
    p = CONFIG["parameters"]
    torque = m3d.assign_torque(
        p["torque_objects"], coordinate_system="Global",
        is_positive=True, is_virtual=p["is_virtual"],
        axis=p["torque_axis"], torque_name="Torque1")
    if not torque:
        raise RuntimeError(f"Failed to assign torque on {p['torque_objects']}.")


def create_setup(m3d):
    """Transient solve setup (stop time / time step)."""
    s = CONFIG["setup"]
    setup = m3d.create_setup(name=s["name"])
    props = setup.props
    if "StopTime" in props:
        props["StopTime"] = s["stop_time"]
        props["TimeStep"] = s["time_step"]
    else:  # older/newer prop naming
        props["TransientTime"] = s["stop_time"]
        props["TransientTimeStep"] = s["time_step"]
    if "SaveFieldsType" in props:  # optional property; may not exist in all versions
        props["SaveFieldsType"] = "Every N Steps" if s.get("save_fields") else "None"
    setup.update()
    return setup


def post_process(m3d, out_dir):
    """Transient field plot, torque-vs-time report, and numeric extraction."""
    pp = m3d.post
    solution = f"{CONFIG['setup']['name']} : Transient"
    intrinsics = {"Time": CONFIG["post_processing"]["plot_time"]}

    for quantity in CONFIG["post_processing"]["field_quantities"]:
        plot_name = f"{quantity}_surf"
        fp = pp.create_fieldplot_surface(
            ["rotor", "stator", "coil"], quantity=quantity,
            setup=solution, intrinsics=intrinsics, plot_name=plot_name)
        if fp:
            try:
                fp.export_image(full_path=str(out_dir / f"{plot_name}.png"),
                                width=1280, height=720, orientation="isometric",
                                show_region=False)
            except Exception as exc:
                print(f"[warn] field plot image export failed: {exc}")
            pp.export_field_plot(plot_name, out_dir, file_name=plot_name, file_format="aedtplt")

    for expressions in CONFIG["post_processing"]["report_expressions"]:
        rep = pp.create_report(
            expressions=expressions, setup_sweep_name=solution, domain="Sweep",
            primary_sweep_variable="Time", plot_name="TorqueReport", show=False)
        if rep:
            try:
                pp.export_report_to_jpg(str(out_dir), "TorqueReport", 800, 450)
                pp.export_report_to_csv(str(out_dir), "TorqueReport")
            except Exception as exc:
                print(f"[warn] report export failed: {exc}")
        sd = pp.get_solution_data(expressions=expressions, setup_sweep_name=solution,
                                  domain="Sweep", primary_sweep_variable="Time")
        if sd:
            vals = sd.data_real()
            print(f"[info] {expressions} values: {vals}")
            with (out_dir / "results_summary.txt").open("a", encoding="utf-8") as fh:
                fh.write(f"{expressions}: {vals}\n")


def main():
    out_dir = Path(CONFIG["post_processing"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    m2d = None
    try:
        m2d = launch()
        print(f"[info] design: {m2d.design_name}, solution: {m2d.solution_type}")

        build_geometry(m2d, CONFIG["geometry"])
        apply_excitation(m2d)
        apply_motion(m2d)
        apply_solution_parameters(m2d)
        create_setup(m2d)

        m2d.validate_simple()
        if not m2d.analyze(setup=CONFIG["setup"]["name"]):
            raise RuntimeError("Solve failed (analyze returned False).")

        post_process(m2d, out_dir)
        print("[info] simulation completed successfully.")
    except Exception:
        traceback.print_exc()
        raise
    finally:
        if m2d is not None:
            try:
                m2d.save_project()
                print(f"[info] project saved: {m2d.project_file}")
            except Exception as exc:
                print(f"[warn] project save failed: {exc}")
            if CONFIG["close_on_exit"]:
                m2d.close_desktop()


if __name__ == "__main__":
    main()
