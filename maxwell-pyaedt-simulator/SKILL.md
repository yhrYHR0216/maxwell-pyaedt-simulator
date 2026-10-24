---
name: maxwell-pyaedt-simulator
description: Builds Ansys Maxwell electromagnetic models from natural-language descriptions by generating parameterized PyAEDT scripts, running the solve, and exporting .aedt projects, field plots, and result reports. Use when the user asks to model, simulate, modify, or post-process a Maxwell magnetostatic, eddy-current, transient, or electrostatic problem. Do not use for HFSS, Icepak, Q3D, SIwave, or circuit-only tasks.
---

# Maxwell PyAEDT Simulator

Translate natural-language electromagnetic simulation requests into runnable, parameterized PyAEDT scripts for Ansys Maxwell (2D and 3D), execute them, and produce standard Ansys outputs: `.aedt` project files, field distribution plots, performance curves, and result reports.

## Core workflow

1. **Parse the request.** Extract: design dimensionality (2D or 3D), solver type, geometry entities, materials, boundaries and excitations, solution parameters (force, torque, matrix), mesh requests, solve setup values, and requested outputs. Use `references/maxwell-concepts.md` for the domain model and `references/pyaedt-api-mapping.md` for the API surface.
2. **Select a template.** Copy `scripts/template_maxwell3d_magnetostatic.py` or `scripts/template_maxwell2d_transient.py` as the skeleton. Adapt the geometry and assignments; keep the structure (CONFIG dict, step functions, error handling, output export) intact.
3. **Parameterize everything.** Every user-tunable value (dimensions, materials, boundary values, excitation amplitudes, setup criteria) must be a key in the top-of-file `CONFIG` dict. Never hard-code a tunable value inline. Follow `references/parameter-conventions.md`.
4. **Generate and validate.** Write the script, then run `python scripts/validate_pyaedt_script.py <script.py>` (syntax + structural checks). Fix any reported issue before execution.
5. **Run.** Execute with the configured AEDT version. If the user's machine has no license or a non-graphical run is requested, set `CONFIG["non_graphical"] = True`. Report the run result and the exported file paths.
6. **Verify outputs.** Confirm the `.aedt` was saved, field-plot images and data files exist, and report files (.jpg/.csv) were exported. Print key numeric results (force magnitude, torque, inductance, etc.) from `get_solution_data`.

## Request parsing rules

- **Dimensionality:** "2D"/"axisymmetric"/"Cartesian XY" → `Maxwell2d`; "3D"/"solid model" → `Maxwell3d`. For 2D, pick the geometry-mode suffix: `Z` = cylindrical about Z (axisymmetric), `XY` = Cartesian.
- **Solver intent:**
  - static magnetic field, DC current, permanent magnet → `Magnetostatic`
  - sinusoidal/frequency-domain, eddy currents, "AC magnetic", "eddy current" → `AC Magnetic` (3D) or `EddyCurrent` (2D); "AC magnetic with DC bias" → `AC Magnetic with DC`
  - time-varying, motion, PWM, moving objects → `Transient` (2D or 3D)
  - static electric field, capacitance → `Electrostatic`
  - DC/AC current flow, ohmic loss → `DC Conduction` / `AC Conduction`
  - A-Phi variants only when the user explicitly mentions A-Phi, mixed excitation on one conduction path, or displacement-current effects.
- **Physical entities to primitives:** coil → `create_cylinder` (or rectangle in 2D), core/yoke → cylinder/box, permanent magnet → box with `magnetic_coercivity` material, housing/insulator → box/cylinder, return path → box or half-torus. Conductor hollowing = create outer + inner, then `modeler.subtract`.
- **Boundary/excitation intent:** keywords like "insulating", "flux tangential", "symmetry", "vector potential at edge", "current on coil", "voltage across terminals", "winding", "external circuit", "band for motion", "force on object X".
- **Output intent:** "field plot of B/H/J", "B distribution", "flux lines" → volume/surface field plots; "force vs time", "torque curve", "losses", "inductance matrix" → reports + numeric extraction.

## Translation rules (NL concept → PyAEDT call)

Apply these when converting parsed intent into code. Full signatures are in `references/pyaedt-api-mapping.md`.

| Natural-language intent | PyAEDT call |
|---|---|
| Solve type | `Maxwell3d(project=..., design=..., solution_type="Magnetostatic", version=..., non_graphical=..., new_desktop=True)` or `Maxwell2d(..., solution_type="TransientZ")` |
| Create a part with material | `m3d.modeler.create_cylinder("Z", origin, radius, height, name=..., material="copper")`, `create_box(origin, sizes, name=..., material=...)`, `create_rectangle(...)`, `create_polyline(...)` |
| Hollow conductor / subtract tool bodies | `m3d.modeler.subtract(blank_list=..., tool_list=..., keep_originals=False)` |
| Background region | `m3d.modeler.create_region(pad_value="50%", pad_type="Percentage Offset")` |
| Current on a conductor | `m3d.assign_current(faces_or_objects, amplitude="1A", solid=True, swap_direction=False, name="Current1")` |
| Voltage excitation | `m3d.assign_voltage(objects_or_faces, amplitude="1V", name="Voltage1")` |
| Winding (current/voltage/external) | `m3d.assign_winding(name="Winding1", winding_type="Current", is_solid=True, current=1, resistance=0, inductance=0, parallel_branches=1, phase=0)` |
| Coil terminals (2D/transient) | `m3d.assign_coil(assignment=faces, conductors_number=N, polarity="Positive", name="Coil1")` |
| Insulating boundary | `m3d.assign_insulating(objects_or_faces, name="Insulating1")` |
| Zero tangential H (flux normal) | `m3d.assign_zero_tangential_h_field(faces, boundary="ZeroTangentialHField1")` |
| Symmetry plane | `m3d.assign_symmetry(faces, symmetry_name="Sym1", is_odd=True)` |
| Vector potential on 2D edges | `m2d.assign_vector_potential(edges, vector_value=0, boundary="VectorPotential1")` |
| Force parameter | `force = m3d.assign_force(["core"], coordinate_system="Global", is_virtual=True, force_name="Force1")` |
| Torque parameter | `m3d.assign_torque(["rotor"], axis="Z", is_positive=True, torque_name="Torque1")` |
| Mesh refinement | `m3d.mesh.assign_length_mesh(objects, inside_selection=True, maximum_length=1, name="Len1")`, `assign_skin_depth(...)`, `assign_surface_mesh(...)` |
| Solve setup | `setup = m3d.create_setup(name="Setup1")` then set `setup.props[...]` and `setup.update()` (see `references/pyaedt-api-mapping.md`) |
| Run the solve | `m3d.validate_simple()` then `m3d.analyze(setup="Setup1")` |
| Motion band (transient) | create the band object, then assign via the raw MotionSetup module: `m3d.odesign.GetModule("MotionSetup").AssignBand(...)` (see API mapping; PyAEDT may require the raw command) |
| B/H/J field plot | `fp = m3d.post.create_fieldplot_volume(objects, quantity="Mag_B", setup="Setup1 : LastAdaptive", plot_name="B_vol")` |
| Export field plot image/data | `fp.export_image(full_path=out/"B_vol.png")`; `m3d.post.export_field_plot("B_vol", out_dir, file_format="aedtplt")` |
| Performance curve / report | `m3d.post.create_report(expressions=["Force1.Force_mag"], setup_sweep_name="Setup1 : LastAdaptive", domain="Sweep", plot_name="ForceReport")` |
| Export report image/CSV | `m3d.post.export_report_to_jpg(project_dir, "ForceReport", 800, 450)`; `m3d.post.export_report_to_csv(project_dir, "ForceReport")` |
| Numeric result extraction | `m3d.post.get_solution_data(expressions=["Force1.Force_mag"], setup_sweep_name=...)` |
| Save project | `m3d.save_project()` (writes `<project>.aedt` plus results folders) |

## Parameterization convention

Every generated script follows this shape:

```python
CONFIG = {
    "project_name": "MySim", "design_name": "Design1", "solution_type": "Magnetostatic",
    "version": "2025.1", "non_graphical": False,
    "geometry": { "units": "mm", "core_radius": "6mm", "core_height": "30mm", "coil_radius": "9mm", ... },
    "materials": { "core": "steel_1008", "coil": "copper", "region": "vacuum" },
    "excitations": { "current_amplitude": "1A", "turns": 200 },
    "parameters": { "force_objects": ["core"], "compute_torque": False },
    "mesh": { "core_max_length": "1mm" },
    "setup": { "max_passes": 10, "percent_refinement": 30, "percent_error": 1 },
    "post_processing": { "field_quantities": ["Mag_B"], "reports": [["Force1.Force_mag"]] },
}
```

Rules:
- Values that reach the AEDT API as strings must include units ("1A", "0.2mm", "60Hz"). Bare floats are accepted for non-unit parameters.
- Materials are library names ("copper", "steel_1008", "iron", "vacuum", "air", custom nonlinear steels). Never invent a material; if unknown, ask or use a documented AEDT library material.
- When the user supplies a parameter as "X turns at Y A", pass the total current (turns x current) to `assign_current` for stranded coils, or model turns via `assign_winding`/`assign_coil`.

## Error handling

Wrap execution steps in `try/except` with descriptive messages. Specific rules:

- Before assigning excitations/boundaries to faces, verify the object exists and faces were resolved: check the returned face-id list is non-empty; raise `RuntimeError("no faces found on <obj>")` otherwise.
- After creating geometry, confirm each returned object handle is truthy before use; fail fast with the object name in the message.
- Run `m3d.validate_simple()` before `analyze`; if it fails, collect the log and stop instead of launching the solve.
- Wrap every AEDT call that can fail (field plot, report, export) individually so one post-processing failure does not discard an already-computed solution.
- On launch failure (no license, wrong version), fall back to `non_graphical=True` retry once, then report the original error.
- Always `m3d.save_project()` in a `finally` block so partial work persists.
- `validate_simple()` is necessary but not sufficient. Before a long transient run, do a 0.02 s smoke solve and read `GetMessages` level 2/1/0.

## Known failure modes (read before inventing a new approach)

Detailed symptom/root-cause/fix entries are in `references/troubleshooting.md`. The rules that cost the most iterations:

- **3D coil terminals**: assign `CoilTerminal` to **internal sheet objects** at a cross-section of the closed conductor, then `assign_winding` + `add_winding_coils`. Face-based terminals on an internal solid trigger `Illegal external terminal ... must border the edge of the problem region`.
- **Translation motion**: `assign_translate_motion(..., periodic_translate=False)`. The default is `True` and causes `Error in mesh mapping on band. 114`.
- **Band contents must be flat**: every moving object inside the band must be a box. Cylinders, `num_sides` prisms, swept polygons, chamfers, and non-model cosmetic overlays all trigger `band can not have any curved surface` or intersection errors.
- **Band length**: rear clearance must be at least the positive travel, otherwise `Positive motion limit is too large`.
- **Project path**: AEDT cannot save to non-ASCII (e.g. Chinese) paths. Save to an ASCII working directory, then copy `.aedt` + `.aedtresults` to the user-facing folder.
- **Field images**: `export_image()` may silently return a geometry-only PNG. Export `export_field_file_on_grid(...)` and plot with matplotlib instead.
- **Numeric results**: do not call `SolutionData.data_real()` in PyAEDT 1.3; use `get_expression_data()` or parse the exported report CSV.

## Outputs

- Project: `<project_name>.aedt` (plus `<project_name>.aedtresults/` and results data).
- Field plots: PNG images via `fp.export_image(...)` and solver-format data via `export_field_plot(..., file_format="aedtplt")`.
- Reports: JPG/PNG images and CSV data in the output folder.
- Numeric summary: print key scalars (force/torque magnitude, losses, inductance) to stdout and write a `results_summary.txt` into the output folder.

## Execution notes

- Generated scripts run under CPython (`python script.py`); they launch AEDT through PyAEDT's COM/gRPC layer. Requires a local Ansys Electronics Desktop installation matching `CONFIG["version"]`.
- Recommend `non_graphical=True` for batch runs and `new_desktop=True` to isolate the session; use `close_on_exit=True` in scripts to avoid leaving AEDT open.
- The templates and the validator (`scripts/validate_pyaedt_script.py`) are authoritative for code structure. For any API not listed in the mapping reference, inspect the installed package first (e.g. `python -c "import inspect, ansys.aedt.core as a; print(inspect.signature(a.Maxwell3d.assign_current))"`) before guessing.

## References

- `references/pyaedt-api-mapping.md` — verified PyAEDT method signatures plus raw AEDT command-array fallbacks with examples from the Maxwell scripting guide.
- `references/parameter-conventions.md` — CONFIG conventions, units, per-solver parameter tables, and result expression glossary.
- `references/maxwell-concepts.md` — solver types/formulations, standard model workflow, boundary/excitation applicability, 2D vs 3D differences, motion and HPC concepts.
- `references/troubleshooting.md` — symptom -> root cause -> correct pattern log for 3D terminals, motion bands, field export, PyAEDT API changes, and Windows/AEDT path problems.
- `scripts/template_maxwell3d_magnetostatic.py` — complete parameterized 3D magnetostatic solenoid example.
- `scripts/template_maxwell2d_transient.py` — complete parameterized 2D transient rotational actuator example.
- `scripts/validate_pyaedt_script.py` — CLI validator (syntax + structural checks) for generated scripts.
