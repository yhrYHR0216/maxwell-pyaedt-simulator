# Parameter Conventions

Rules for exposing user-adjustable simulation parameters and for documenting them to the end user. Every generated script must place all tunable values in a single `CONFIG` dict at the top of the file and derive every subsequent hard-coded string from it.

## CONFIG layout

```python
CONFIG = {
    # ---- identity ----
    "project_name": "MySim",
    "design_name": "Design1",
    "solution_type": "Magnetostatic",      # see solution types in api mapping
    "version": "2025.1",                   # AEDT version; None = latest installed
    "non_graphical": False,                # True = batch/headless run
    "close_on_exit": True,

    # ---- geometry (all values carry units as strings) ----
    "geometry": {
        "units": "mm",
        "core_radius": "6mm",
        "core_height": "30mm",
        "coil_radius_inner": "8mm",
        "coil_radius_outer": "12mm",
        "coil_height": "15mm",
        "yoke_size": "60mm",
        "region_pad": "50%",
    },

    # ---- materials (AEDT library names) ----
    "materials": {
        "core": "steel_1008",
        "plugnut": "steel_1008",
        "coil": "copper",
        "yoke": "steel_1008",
        "region": "vacuum",
    },

    # ---- excitations ----
    "excitations": {
        "coil_current": "1A",              # total ampere-turns for stranded
        "turns": 200,                      # used to document A-turns
        "swap_direction": False,
        "excitation_model": "Single Potential",
    },

    # ---- solution parameters ----
    "parameters": {
        "force_objects": ["plugnut"],
        "force_virtual": True,
        "torque_objects": [],
        "torque_axis": "Z",
    },

    # ---- mesh ----
    "mesh": {
        "core_max_length": "1mm",
        "coil_skin_depth": None,           # None = no skin-depth op
    },

    # ---- solve setup ----
    "setup": {
        "name": "Setup1",
        "max_passes": 10,
        "min_passes": 2,
        "min_converged_passes": 1,
        "percent_refinement": 30,
        "percent_error": 1,
        "frequency": None,                 # "60Hz" for AC Magnetic
        "stop_time": None,                 # "10ms" for Transient
        "time_step": None,                 # "0.05ms" for Transient
    },

    # ---- outputs ----
    "output_dir": "results",
    "field_quantities": ["Mag_B"],         # field-plot quantities to export
    "report_expressions": [["Force1.Force_mag", "Force1.Force_z"]],
}
```

## Units conventions

- **Always include units in strings passed to the AEDT API.** `"1A"`, `"0.2mm"`, `"60Hz"`, `"10ms"`, `"5deg"`, `"1000rpm"`, `"3.5V"`. Bare numbers are rejected or misinterpreted by AEDT.
- Numeric parameters without units (pass counts, percentages, element counts, integer branch numbers) stay as Python numbers.
- Keep a single geometry unit (`units`) and construct all geometry values consistently.
- When the user changes a dimension, update only the corresponding CONFIG entry; generated code must not contain that dimension anywhere else.

## Per-solver parameter tables

### Magnetostatic (2D/3D)
- Geometry: core/plugnut/yoke/coil sizes.
- Materials: magnetic steels (nonlinear BH curve), copper windings, vacuum background.
- Excitation: `coil_current` (total A) on conductor terminal faces/objects.
- Parameters: force (objects), torque (axis), inductance matrix (windings).
- Setup: adaptive `max_passes`, `percent_refinement`, `percent_error` (typical 0.5-5%).

### AC Magnetic / Eddy Current (2D/3D)
- Add `frequency` to setup; if "AC Magnetic with DC", also `dc_current`/`dc_voltage`.
- Field plot quantities `Mag_B`, `ComplexMag_J`; losses from reports (`OhmicLoss`, `CoreLoss`).
- Use skin-depth mesh on conductors (`assign_skin_depth`).

### Transient (2D/3D)
- Add `stop_time`, `time_step` (rule of thumb: time step <= 1/10 of smallest time constant or 1/20 of period for AC).
- Windings: `assign_winding` (Current/Voltage/External) + `assign_coil` terminals; for a 3D closed coil put the `CoilTerminal` on internal **sheet objects**, not on solid faces. Order coil terminals for A-Phi designs.
- Motion: band object + `MotionSetup.AssignBand` (rotate/translate), torque on moving part, optional mechanical transient (mass, damping, load).
- **Translation motion must set `periodic_translate=False`.** The PyAEDT helper defaults to `True`, which produces `Error in mesh mapping on band. 114`.
- **All objects inside the band must be boxes (planar faces only).** A cylindrical battery, cylindrical band, `num_sides` prism, swept polygonal prism, or chamfered solid triggers `band can not have any curved surface`. Non-model cosmetic cylinders still fail intersection validation.
- **Band sizing**: `band_length >= moving_object_length + travel + front_clearance + rear_clearance`. Rear clearance must be at least the positive travel, otherwise `Positive motion limit is too large`.
- **Region sizing**: keep the region boundary beyond the band's maximum travel position, not just its initial position.
- **Field saving**: leave `SaveFieldsType=None` for the main transient. In AEDT 2026.1, `SaveSingleField` / `Every N Steps` can hang. Do a 0.02 s smoke solve before the full run.
- Reports: time-domain curves (`primary_sweep_variable="Time"`), e.g. torque vs time, winding current vs time. Prefer `export_report_to_csv` + CSV parsing over `SolutionData.data_real()` (removed in PyAEDT 1.3).

### Electrostatic / DC / AC Conduction
- Excitation: voltage (`assign_voltage`) or voltage drop; current density for conduction.
- Parameters: capacitance matrix (electrostatic), resistance matrix (DC/AC conduction).
- Field quantities `Mag_E`, `E_Vector`, `Ohmic_Loss`.

## Result expressions glossary

| Intent | Expression |
|---|---|
| Force on object | `Force1.Force_mag`, `Force1.Force_x`, `Force1.Force_y`, `Force1.Force_z` |
| Torque on object | `Torque1.Torque_mag`, `Torque1.Torque_z` (axis component) |
| Inductance matrix | `Matrix1.L(W1,W1)`, `Matrix1.L(W1,W2)` |
| Resistance matrix | `Matrix1.R(W1,W2)` |
| Winding current/voltage | `TerminalCurrent(W1)`, `TerminalVoltage(W1)`, `FluxLinkage(W1)` |
| Losses | `OhmicLoss`, `SolidLoss`, `StrandedLoss`, `AvgCoreLoss`, `PerWindingSolidLoss(W1)`, `PerWindingStrandedLoss(W1)` |

## Documenting parameters for the user

When delivering a script, include a short parameter table in the response (or as a `README` comment block at the top of the script, not a separate file) mapping each CONFIG key to: what it controls, its unit, typical range, and an example. If the user requests a web/config interface, keep the CONFIG dict JSON-serializable so it can be edited through a GUI/JSON without code changes.

## Guardrails

- Never invent material names; use AEDT library materials unless the user provides a material definition (e.g. BH curve data), in which case create it with the Definition Manager before assigning.
- Never silently ignore a CONFIG key; every key must be consumed by the script (validate at startup: known keys only, fail fast on typos).
- Keep generated scripts single-file and dependency-free beyond `ansys.aedt.core`/`pyaedt` so the user can edit and re-run them standalone.
- **Project path must be ASCII-only.** AEDT 2026.1 cannot reliably save to a path with Chinese/non-ASCII characters; save to an ASCII working directory and copy `.aedt` + `.aedtresults` to the deliverable folder afterwards.
- **Do not trust `validate_simple()` alone.** Run a short smoke solve (0.02 s) and read AEDT messages before committing to a long transient.
- **Do not use `export_image()` as a field-result proof.** It can return a geometry-only PNG. Use `export_field_file_on_grid` + matplotlib.
