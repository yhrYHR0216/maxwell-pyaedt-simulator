# Maxwell PyAEDT Simulator

Ansys Maxwell electromagnetic simulation skill for AI agents: turns natural-language requests into parameterized PyAEDT scripts, runs solves, and exports `.aedt` projects, field plots, and result reports for magnetostatic, eddy-current, transient, and electrostatic problems.

**Repository:** https://github.com/yhrYHR0216/maxwell-pyaedt-simulator

---

## What This Skill Does

- Parses a natural-language request into solver type, geometry, materials, boundaries/excitations, solution parameters, mesh, setup values, and requested outputs.
- Generates a single-file, fully parameterized PyAEDT script (all tunable values live in one `CONFIG` dict at the top).
- Validates the script statically before running it.
- Runs the solve through a local Ansys Electronics Desktop installation.
- Exports the `.aedt` project, field-plot images/data, and CSV/JPG reports, and prints key numeric results.

**Supported solvers:** Magnetostatic, AC Magnetic (Eddy Current), Transient (incl. motion), Electrostatic, DC/AC Conduction. **Not** for HFSS, Icepak, Q3D, SIwave, or circuit-only tasks.

---

## Repository Layout

```
maxwell-pyaedt-simulator/
├── README.md                         # This document
└── maxwell-pyaedt-simulator/         # The skill folder
    ├── SKILL.md                      # Skill definition (frontmatter + core workflow)
    ├── references/
    │   ├── maxwell-concepts.md       # Solver types, workflow, boundaries/excitations, 2D vs 3D
    │   ├── pyaedt-api-mapping.md     # Verified PyAEDT signatures + raw AEDT command fallbacks
    │   ├── parameter-conventions.md  # CONFIG layout, units, per-solver parameter tables
    │   └── troubleshooting.md        # Symptom → root cause → correct pattern log
    └── scripts/
        ├── template_maxwell3d_magnetostatic.py   # 3D magnetostatic solenoid example
        ├── template_maxwell2d_transient.py       # 2D transient rotational actuator example
        └── validate_pyaedt_script.py             # Static validator for generated scripts
```

> Make sure the `references/` and `scripts/` subfolders and all their files are committed, otherwise the relative paths referenced in `SKILL.md` will break.

---

## Prerequisites

| Requirement | Details |
|---|---|
| **OS** | Windows (required for AEDT COM/gRPC automation) |
| **Ansys Electronics Desktop** | Installed locally, version matching `CONFIG["version"]` (templates default to `2025.1`) |
| **License** | A valid Maxwell license (HPC license only if you request `cores`/`tasks`/`gpus`) |
| **Python** | CPython 3.9+ |
| **PyAEDT** | `ansys-aedt-core` (PyAEDT ≥ 1.3, imported as `ansys.aedt.core`; the older `pyaedt` package is also supported) |

---

## Installation & Configuration

### 1. Clone the repository

```bash
git clone https://github.com/yhrYHR0216/maxwell-pyaedt-simulator.git
cd maxwell-pyaedt-simulator
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install PyAEDT

```bash
pip install ansys-aedt-core
```

Verify the import works:

```bash
python -c "import ansys.aedt.core; print(ansys.aedt.core.__version__)"
```

### 4. Point PyAEDT at your AEDT installation

PyAEDT locates AEDT automatically in most cases. If it does not, set the install path explicitly:

```bat
set ANSYSEM_ROOT251=C:\Program Files\AnsysEM\v251\Win64
set ANSYSEMSV_ROOT251=C:\Program Files\AnsysEM\v251\Win64
```

(Use the folder matching your installed version. You can also pass `version="2025.1"` in the `CONFIG` dict.)

### 5. Use an ASCII-only working directory

AEDT cannot reliably save projects to paths containing non-ASCII characters (e.g. Chinese folder names). Set a dedicated ASCII working folder before running any script:

```bat
set AEDT_WORKDIR=C:\Users\<you>\Documents\Ansoft\MaxwellRuns
```

The scripts save the `.aedt` there; copy results to your deliverable folder afterwards.

---

## Running the Skill

### Option A — Run a template directly

```bash
python maxwell-pyaedt-simulator\scripts\template_maxwell3d_magnetostatic.py
```

Edit the `CONFIG` dict at the top of the script to change geometry, materials, excitation, mesh, setup, and outputs. **Never** hard-code a tunable value outside `CONFIG`.

### Option B — Validate a generated script first

Before executing any generated or hand-edited script, run the static validator:

```bash
python maxwell-pyaedt-simulator\scripts\validate_pyaedt_script.py path\to\your_script.py --verbose
```

It checks syntax, required imports, the `CONFIG` dict structure, required pipeline calls (`validate_simple`, `analyze`, `save_project`), undefined-name typos, and unit hygiene in excitation/setup arguments. Exit code `0` means all checks pass.

### Option C — Headless / batch runs

In `CONFIG`, set:

```python
"non_graphical": True,
"close_on_exit": True,
```

This launches AEDT without a GUI and closes it on completion — suitable for CI or remote runs.

---

## Parameterization Rule (Important)

Every generated script keeps all tunable values in a single `CONFIG` dict:

```python
CONFIG = {
    "project_name": "MySim",
    "design_name": "Design1",
    "solution_type": "Magnetostatic",
    "version": "2025.1",
    "non_graphical": False,
    "geometry":  { "units": "mm", "core_radius": "6mm", ... },
    "materials": { "core": "steel_1008", "coil": "copper", "region": "vacuum" },
    "excitations": { "coil_current": "1A", "turns": 200 },
    "parameters": { "force_objects": ["plugnut"] },
    "mesh":      { "core_max_length": "1mm" },
    "setup":     { "max_passes": 10, "percent_error": 1 },
    "post_processing": { "field_quantities": ["Mag_B"], ... },
}
```

- Values reaching the AEDT API as strings **must include units** (`"1A"`, `"0.2mm"`, `"60Hz"`, `"10ms"`).
- Materials are AEDT library names (`copper`, `steel_1008`, `vacuum`, …). Never invent materials.
- To change a dimension, edit only the matching `CONFIG` entry.

---

## Known Pitfalls (Read Before Debugging)

The full symptom → root cause → fix log is in `maxwell-pyaedt-simulator/references/troubleshooting.md`. Highest-impact ones:

- **3D closed-coil terminals** — assign `CoilTerminal` to **internal sheet objects**, not solid faces, or AEDT reports `Illegal external terminal ...`.
- **Translation motion** — set `periodic_translate=False` (the default `True` causes `Error in mesh mapping on band. 114`).
- **Motion band contents must be boxes** — cylinders, `num_sides` prisms, swept polygons, and chamfers trigger `band can not have any curved surface`.
- **Band length** — rear clearance ≥ positive travel, else `Positive motion limit is too large`.
- **Project path must be ASCII-only** — non-ASCII paths break `save_project()`.
- **Field images** — `export_image()` may return a geometry-only PNG; use `export_field_file_on_grid()` + matplotlib instead.
- **Numeric extraction** — PyAEDT 1.3 has no `SolutionData.data_real()`; use `get_expression_data()` or parse the exported CSV.
- **`validate_simple()` is not a solve** — run a 0.02 s smoke solve and read AEDT messages before a long transient.

---

## Verifying the Setup

A successful run should produce:

- `<project_name>.aedt` and `<project_name>.aedtresults/`
- Field-plot PNGs and `.aedtplt` data files in the output folder
- Report JPG + CSV files
- A `results_summary.txt` with key scalars (force/torque, losses, inductance)

If `analyze()` returns `False`, check the AEDT messages (`GetMessages` levels 2/1/0) before changing the model.

---

## Using This Skill in an Agent

If your agent framework supports skill directories, place the `maxwell-pyaedt-simulator/` subfolder from this repository where the framework loads skills (e.g. `.claude/skills/maxwell-pyaedt-simulator/`). The agent reads `SKILL.md` and its `description` frontmatter to decide when to invoke the skill, and consults the `references/` files for domain and API details.

Example invocation: *"Simulate a 3D magnetostatic solenoid and report the force on the plugnut"* — the skill will pick the 3D template, parameterize geometry/excitation, validate, solve, and export results.

---

## License / Credits

Grounded in the Ansys Maxwell help (`Maxwell.pdf`, 2026 R1), the Maxwell scripting guide, and PyAEDT 1.3.0. Add your chosen license file before publishing.
