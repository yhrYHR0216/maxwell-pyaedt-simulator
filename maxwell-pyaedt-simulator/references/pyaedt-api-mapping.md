# PyAEDT API Mapping for Maxwell

Authoritative reference for translating Maxwell concepts into code. All PyAEDT signatures below were verified against PyAEDT 1.3.0 (`ansys.aedt.core`, Jan 2026). When a high-level PyAEDT call is unavailable, use the raw AEDT command-array form (module handles exposed as `m3d.odesign`, `m3d.oboundary`, `m3d.omeshmodule`, `m3d.oanalysis`, `m3d.oreportsetup`, `m3d.ofieldsreporter`, `m3d.modeler.oeditor`).

Raw command arrays use the AEDT "NAME:" convention: `["NAME:<Name>", "<Prop>:=", value, ...]`. Units are required in string values.

## Import & launch

```python
try:
    from ansys.aedt.core import Maxwell3d, Maxwell2d   # PyAEDT >= 1.3
except ImportError:
    from pyaedt import Maxwell3d, Maxwell2d            # PyAEDT < 1.3

m3d = Maxwell3d(project="Solenoid", design="Design1", solution_type="Magnetostatic",
                version="2025.1", non_graphical=False, new_desktop=True, close_on_exit=True)
# project=None  -> creates temp; design=None -> auto name
m3d.save_project()       # writes <project>.aedt and results folders
m3d.close_desktop()
```

## Solution types (official strings)

Maxwell 3D: `"Transient"`, `"Magnetostatic"`, `"AC Magnetic"`, `"AC Magnetic APhi"`, `"AC Magnetic with DC"`, `"Electrostatic"`, `"DC Conduction"`, `"Electric DC Conduction"`, `"AC Conduction"`, `"Electric Transient"`, `"Transient APhi"`.

Maxwell 2D (suffix = geometry mode; `Z` = cylindrical about Z, `XY` = Cartesian): `"TransientZ"`, `"TransientXY"`, `"MagnetostaticZ"`, `"MagnetostaticXY"`, `"EddyCurrentZ"`, `"EddyCurrentXY"`, `"ElectroStaticZ"`, `"ElectroStaticXY"`, `"DCConductionZ"`, `"DCConductionXY"`, `"ACConductionZ"`, `"ACConductionXY"`.

Enums: `from ansys.aedt.core.generic.constants import SolutionsMaxwell3D, SolutionsMaxwell2D`.

## Modeler primitives

| Call (verified) | Notes |
|---|---|
| `m3d.modeler.create_box(origin, sizes, name=None, material=None, **kwargs)` | origin/sizes in model units |
| `m3d.modeler.create_cylinder(orientation, origin, radius, height, num_sides=0, name=None, material=None)` | orientation `"Z"`/`"X"`/`"Y"` or `Plane` |
| `m3d.modeler.create_rectangle(orientation, origin, sizes, name=None, material=None, is_covered=True)` | 2D faces |
| `m3d.modeler.create_polyline(points, segment_type=None, cover_surface=False, close_surface=False, name=None, material=None, xsection_type=None, xsection_width=None, ...)` | coils/paths |
| `m3d.modeler.create_sphere(origin, radius, name=None, material=None)` | |
| `m3d.modeler.create_torus(origin, major_radius, minor_radius, axis=None, name=None, material=None)` | |
| `m3d.modeler.create_region(pad_value=300, pad_type="Percentage Offset", name="Region")` | background; pad_value can be `"50%"` |
| `m3d.modeler.subtract(blank_list, tool_list, keep_originals=True)` | hollow conductors: outer minus inner |
| `m3d.modeler.unite(assignment, purge=False, keep_originals=False)` | |
| `m3d.modeler.move(assignment, vector)` / `rotate(assignment, axis, angle, units="deg")` | |
| `m3d.modeler.duplicate_along_line(assignment, vector, clones=2, attach=False)` / `duplicate_around_axis(assignment, axis, angle, clones=2)` | repeated poles |
| `m3d.modeler.get_object_faces(name)` -> list of face IDs | resolve faces for excitation assignment |
| `m3d.modeler.get_face_center(face_id)` -> [x, y, z] | pick terminal face by centroid |

Raw fallback (3D Modeler editor):
```python
oeditor = m3d.modeler.oeditor
oeditor.CreateCylinder(["NAME:CylinderParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
    "ZCenter:=", "0mm", "Radius:=", "6mm", "Height:=", "30mm", "WhichAxis:=", "Z",
    "NumSides:=", 0, "ThetaStart:=", "0deg", "ThetaEnd:=", "360deg"],
    ["NAME:Attributes", "Name:=", "core", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global", "MaterialValue:=", '"steel_1008"',
     "SolveInside:=", True])
```

## Materials

- Assign at creation via `material=` (see above), or later: `m3d.assign_material(objects, "copper")` / `obj.material = "steel_1008"`.
- Library materials commonly used: `copper`, `aluminum`, `iron`, `steel_1008` (nonlinear BH), `steel_1010`, `vacuum`, `air`, `pec`.
- Custom nonlinear material via Definition Manager raw call (`oProject.GetDefinitionManager().AddMaterial(...)`) — see BH-curve example in the Maxwell scripting guide (chapter 28). The script `scripts/template_maxwell3d_magnetostatic.py` includes a working `add_bh_material` helper pattern.

## Boundaries (verified PyAEDT)

| Intent | Call |
|---|---|
| Insulating (no current flow) | `m3d.assign_insulating(assignment, name="Insulating1")` |
| Symmetry (even/odd) | `m3d.assign_symmetry(faces, symmetry_name="Sym1", is_odd=True)` |
| Zero tangential H (flux-normal outer faces) | `m3d.assign_zero_tangential_h_field(faces, boundary="ZTH1")` |
| Vector potential on 2D edges | `m2d.assign_vector_potential(edges, vector_value=0, boundary="VP1")` |
| Impedance / thin layer / touching | not wrapped for Maxwell in PyAEDT 1.3; use raw `AssignImpedance`, `AssignThinLayer`, `AssignTouching` on `m3d.oboundary` |

Raw fallback examples (module = `oDesign.GetModule("BoundarySetup")`):
```python
oModule = m3d.oboundary
oModule.AssignInsulating(["NAME:Insulating1", "Objects:=", ["frame"]])
oModule.AssignVectorPotential(["NAME:VectorPotential1", "Edges:=", [21],
                               "Phase:=", "0deg", "Value:=", "0Wb/m", "CoordinateSystem:=", "Global"])
oModule.AssignSymmetry(["NAME:Sym1", "Objects:=", ["Region"],
                        "IsSymmetry:=", True, "SymmetryType:=", "Even Odd", "IsOdd:=", True])
oModule.AssignZeroTangentialHField(["NAME:ZeroTangentialHField1", "Faces:=", [7]])
oModule.AssignFluxTangential(["NAME:FluxTangential1", "Edges:=", [2]])
```

## Excitations (verified PyAEDT)

| Intent | Call |
|---|---|
| Current (magnetostatic / AC magnetic / 2D+3D transient) | `m3d.assign_current(assignment, amplitude="1A", phase="0deg", solid=True, swap_direction=False, name="Current1", excitation_model="Single Potential")` |
| Current, DC-biased (AC Magnetic with DC) | same call; DC handled via winding below |
| Voltage | `m3d.assign_voltage(assignment, amplitude="1V", name="Voltage1", swap_direction=False, initial_current=0, has_initial_current=False, phase=0)` |
| Voltage drop (solid conductor) | `m3d.assign_voltage_drop(assignment, amplitude="1V", swap_direction=False, name="VD1")` |
| Current density (vector J) | `m3d.assign_current_density(assignment, current_density_name="J1", phase="0deg", current_density_x="0", current_density_y="0", current_density_z="0")` |
| Winding (group excitation) | `m3d.assign_winding(assignment=None, winding_type="Current", is_solid=True, current=1, resistance=0, inductance=0, voltage=0, parallel_branches=1, phase=0, name="Winding1")` |
| Coil terminal (2D / transient conduction path) | `m3d.assign_coil(assignment=faces, conductors_number=1, polarity="Positive", name="Coil1")` |
| Matrix (inductance/capacitance/resistance matrix) | `m3d.assign_matrix(MaxwellMatrixSchema)` — see matrix note below |

Raw fallback examples:
```python
oModule = m3d.oboundary
# 3D magnetostatic solid current on terminal face
oModule.AssignCurrent(["NAME:Current1", "Faces:=", [260], "Current:=", "1A",
                       "IsSolid:=", True, "Point out of terminal:=", False])
# 2D magnetic stranded current on object
oModule.AssignCurrent(["NAME:Current1", "Objects:=", ["coil"], "Current:=", "10mA", "IsPositive:=", True])
# winding group (transient, external circuit)
oModule.AssignWindingGroup(["NAME:Winding1", "Type:=", "External", "IsSolid:=", False,
    "Current:=", "0mA", "Resistance:=", "0ohm", "Inductance:=", "0nH",
    "Voltage:=", "0mV", "ParallelBranchesNum:=", "1"])
```

Matrix note (PyAEDT 1.3): `m3d.assign_matrix` dispatches on solution type. For magnetostatic, pass a `MatrixMagnetostatic` schema (`from ansys.aedt.core.modules.boundary.maxwell_boundary import MatrixMagnetostatic`); for electric solvers a `MatrixElectric`; for AC magnetic a `MatrixACMagnetic`. Inspect the class with `help(...)` before use.

**3D closed-coil terminal pattern (verified).** `assign_winding(assignment=...)` is not a way to apply a stranded winding directly to a conductor object; it forwards to `assign_coil` and creates a terminal. For a coil fully inside the region, put `CoilTerminal` on two **sheet objects** at an internal cross-section, then create the winding group with `assignment=None` and add both terminals:
```python
m3d.modeler.create_rectangle("YZ", [0, ri, 0], [ro - ri, L],
                             name="Coil_Section1", material=None)
m3d.modeler.create_rectangle("YZ", [0, -ro, 0], [ro - ri, L],
                             name="Coil_Section2", material=None)
m3d.assign_coil(["Coil_Section1"], conductors_number=400,
                polarity="Positive", name="CoilTerminal1")
m3d.assign_coil(["Coil_Section2"], conductors_number=400,
                polarity="Negative", name="CoilTerminal2")
m3d.assign_winding(name="Winding1", winding_type="Voltage", is_solid=False,
                   voltage=12, resistance=4, inductance=0, parallel_branches=1)
m3d.add_winding_coils("Winding1", ["CoilTerminal1", "CoilTerminal2"])
```
Do not put a `CoilTerminal` on a solid face inside the region: AEDT reports `Illegal external terminal ... must border the edge of the problem region`.

## Motion (band, transient only)

PyAEDT 1.3 does not expose a stable high-level band helper; use the raw MotionSetup module:
```python
oMotion = m3d.odesign.GetModule("MotionSetup")
oMotion.AssignBand([
    "NAME:Data",
    "Move Type:=", "Rotate",
    "Coordinate System:=", "Global",
    "Axis:=", "Z",
    "Is Positive:=", True,
    "InitPos:=", "0deg",
    "HasRotateLimit:=", False,
    "NonCylindrical:=", False,
    "Consider Mechanical Transient:=", False,
    "Angular Velocity:=", "0deg_per_sec",
    "Objects:=", ["band"]])
```
For translation: `"Move Type:=", "Translate"`, `"InitPos:=", "0mm"`, `"NegativePos:=", "-5mm"`, `"PositivePos:=", "5mm"`. Mechanical transient adds `"Mass:="`, `"Damping:="`, `"Load Force:="`. Then add force/torque parameters on the moving object(s).

When using the high-level helper, explicitly set `periodic_translate=False`:
```python
m3d.assign_translate_motion(
    assignment="band", coordinate_system="Global", axis="Z",
    positive_movement=True, start_position=0, periodic_translate=False,
    negative_limit=0, positive_limit=78, mechanical_transient=True,
    velocity=0, mass=0.2, damping=0, load_force=0, motion_name="Motion1")
```
The default is `True` and produces `Error in mesh mapping on band. 114`. The band must be a box and every moving object inside it must also be a box; cylinders and swept/chamfered solids trigger `band can not have any curved surface`. Size the band so rear clearance >= positive travel, and keep the region above the band's maximum travel position.

## Mesh operations (verified)

```python
m3d.mesh.assign_length_mesh(objects, inside_selection=True, maximum_length=1, maximum_elements=1000, name="Len1")
m3d.mesh.assign_skin_depth(objects, skin_depth="0.2mm", maximum_elements=None,
                           triangulation_max_length="0.1mm", layers_number="2", name="Skin1")
m3d.mesh.assign_surface_mesh(objects, level, name="Surf1")
m3d.mesh.assign_model_resolution(objects, defeature_length=None, name="ModelRes1")
```
Raw fallback: `oDesign.GetModule("MeshSetup").AssignLengthOp(...)`, `AssignSkinDepthOp(...)`, `AssignMeshRegion(...)`.

## Solve setup (verified)

```python
setup = m3d.create_setup(name="Setup1", setup_type=None)   # kwargs map to properties
setup.props["MaximumPasses"] = 10          # adaptive passes
setup.props["MinimumPasses"] = 2
setup.props["MinimumConvergedPasses"] = 1
setup.props["PercentRefinement"] = 30
setup.props["PercentError"] = 1            # convergence (%) - magnetostatic/AC/electrostatic
setup.props["SolveMatrixAtLast"] = True
setup.props["UseNonLinearIterNum"] = False # nonlinear solver (BH curves)
setup.props["NonLinearResidual"] = 0.0001
setup.props["HasSweepSetup"] = False
setup.update()
```
For frequency-domain setups set `setup.props["Frequency"] = "60Hz"`. For transient set `setup.props["StopTime"] = "10ms"`, `setup.props["TimeStep"] = "0.05ms"`, and optionally `"SaveFieldsType:=" ...` etc. Inspect available props with `print(setup.props.keys())` before editing.

Raw fallback (module = `AnalysisSetup`): `oDesign.GetModule("AnalysisSetup").InsertSetup("Magnetostatic", ["NAME:Setup1", "Enabled:=", True, ["NAME:MeshLink", "ImportMesh:=", False], "MaximumPasses:=", 10, "MinimumPasses:=", 2, "MinimumConvergedPasses:=", 1, "PercentRefinement:=", 30, "PercentError:=", 1, "SolveFieldOnly:=", False, "SolveMatrixAtLast:=", True, "UseNonLinearIterNum:=", False, "UseIterativeSolver:=", False, "RelativeResidual:=", 1e-05, "NonLinearResidual:=", 0.0001, "SmoothBHCurve:=", False, "HasSweepSetup:=", False])`.

## Solution parameters (force / torque)

```python
force = m3d.assign_force(["plugnut"], coordinate_system="Global", is_virtual=True, force_name="Force1")
torque = m3d.assign_torque(["rotor"], coordinate_system="Global", is_positive=True,
                           is_virtual=True, axis="Z", torque_name="Torque1")
```
Raw fallback: `oDesign.GetModule("MaxwellParameterSetup").AssignForce(["NAME:Force1", "Reference CS:=", "Global", "Is Virtual:=", True, "Objects:=", ["plugnut"]])` and `.AssignTorque(...)`.

## Run / analyze (verified)

```python
m3d.validate_simple()                     # returns int; nonzero = errors
m3d.analyze(setup="Setup1", cores=None, tasks=None, gpus=None, blocking=True)
```

## Post-processing (verified)

Field plots:
```python
fp = m3d.post.create_fieldplot_volume(objects, quantity="Mag_B", setup="Setup1 : LastAdaptive",
                                      intrinsics=None, plot_name="B_vol", field_type="DC R/L Fields")
fp = m3d.post.create_fieldplot_surface(objects, quantity="Mag_H", ..., plot_name="H_surf")
fp = m3d.post.create_fieldplot_cutplane(objects, quantity="Mag_J", ..., plot_name="J_cut")
fp.export_image(full_path="out/B_vol.png", width=1920, height=1080,
                orientation="isometric", show_region=False)          # PNG
m3d.post.export_field_plot("B_vol", out_dir, file_name="B_vol", file_format="aedtplt")  # solver data
```

`export_image()` can silently produce a **geometry-only** PNG (model wireframe with a length colorbar in mm) when the active plot has no valid field data, especially in `non_graphical=True` runs. Do not use the PNG as proof of a field result. For a reliable engineering image, export the data and render it yourself:
```python
gf = m3d.post.export_field_file_on_grid(
    quantity="Mag_B", solution="Setup1 : LastAdaptive",
    file_name=str(out_dir / "Mag_B_grid.txt"), grid_type="Cartesian",
    grid_start=[-40, -1, -20], grid_stop=[40, 1, 100],
    grid_step=[1, 1, 1], is_vector=False, export_with_sample_points=True)
# parse x y z value rows (SI units), then matplotlib tricontourf
```
For a transient model where field saving is unreliable, build a separate Magnetostatic design with the same geometry and export the grid there.

Reports / curves:
```python
rep = m3d.post.create_report(expressions=["Force1.Force_mag", "Force1.Force_z"],
                             setup_sweep_name="Setup1 : LastAdaptive", domain="Sweep",
                             primary_sweep_variable=None, plot_name="ForceReport",
                             plot_type="Rectangular Plot", show=False)
m3d.post.export_report_to_jpg(project_dir, "ForceReport", 800, 450)
m3d.post.export_report_to_csv(project_dir, "ForceReport")
m3d.post.export_report_to_file(out_dir, "ForceReport", extension=".csv")
```

Numeric extraction:
```python
sd = m3d.post.get_solution_data(expressions=["Force1.Force_mag"],
                                setup_sweep_name="Setup1 : LastAdaptive", domain="Sweep")
if sd:
    x, y = sd.get_expression_data("Force1.Force_mag")   # PyAEDT 1.3
    print(x, y)
```
PyAEDT 1.3's `SolutionData` has **no `data_real()`**; calling it raises `'SolutionData' object has no attribute 'data_real'`. Use `get_expression_data()`, or export the report and parse the CSV (the most version-stable option):
```python
m3d.post.export_report_to_csv(str(out_dir), "Force1_Report")
# read Force1_Report.csv with csv.reader
```

Field-plot quantities (official): `Mag_B`, `B_Vector`, `Mag_H`, `H_Vector`, `Mag_J`, `J_Vector`, `ComplexMag_J`, `Mag_Jc`, `Energy`, `coEnergy`, `Ohmic_Loss`, `Total_Loss`, `Hysteresis_Loss`, `Dielectric_Loss`, `Temperature`, `Volume_Force_Density`, `Surface_Force_Density`, `Mag_E`, `E_Vector`, `"Mesh"` (mesh plot).

Report expression patterns: `Force1.Force_mag`, `Force1.Force_x/y/z`, `Torque1.Torque_mag`, `Torque1.Torque_z`, `Matrix1.L(Winding1,Winding1)`, `Matrix1.R(Winding1,Winding2)`, `OhmicLoss`, `StrandedLoss`, `SolidLoss`, `AvgCoreLoss`, `PerWindingSolidLoss(Winding1)`, `PerWindingStrandedLoss(Winding1)`, `TerminalVoltage(Winding1)`, `TerminalCurrent(Winding1)`, `FluxLinkage(Winding1)`, `Inductance(Winding1,Winding2)`. For transient: expressions plus `domain="Sweep"` with `primary_sweep_variable="Time"`.

## Version guardrails

- Verify any method not listed here against the installed package before use:
  `python -c "import inspect, ansys.aedt.core as a; print(inspect.signature(a.Maxwell3d.<method>))"`
- If a PyAEDT call is missing or behaves differently, fall back to the raw AEDT command arrays above (they are stable across releases and match the official scripting guide).
- **Non-ASCII project paths**: AEDT 2026.1 can fail `save_project()` with `is it readonly? disk full?` when the path contains Chinese or other non-ASCII characters. Save to an ASCII working directory (e.g. `Documents\Ansoft\BatteryEM`), then copy `.aedt` and `.aedtresults` to the user-facing folder with `shutil`.
- **Transient field saving**: `set_save_fields(range_type="Custom", subrange_type="SinglePoints")` can leave `SaveSingleField=False`; `Every N Steps` can also hang. Do not enable field saving on a long transient without a 0.02 s smoke solve. Use a separate Magnetostatic design for field maps.
- **`validate_simple()` is not a solve**: it can pass while the solver rejects band surfaces, moving-object curvature, or mesh mapping. Run a short `analyze()` and read `GetMessages` level 2/1/0 before the full run.
- **Avoid raw `Chamfer` / polyline arrays**: malformed arrays cause `invalid parameters to createpolyline operation` or a PyAEDT logging recursion. Use native `create_box` / `create_cylinder` / `create_rectangle` / `subtract` / `unite`.
