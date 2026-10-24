# Maxwell / PyAEDT Troubleshooting Log

Hard-won lessons from real 3D magnetostatic, transient-motion, and eddy-current jobs
(AEDT 2026.1 + PyAEDT 1.3.0 on Windows). Each entry is **Symptom -> Root cause -> Correct pattern**.
Read this before inventing a new excitation, motion, or field-export approach.

## Quick index

| # | Symptom | Jump |
|---|---|---|
| 1 | `Illegal external terminal ... must border the edge of the problem region` | Internal sheet terminals |
| 2 | Current on a 3D object -> `Cannot apply Current Excitation to non planar entity` | 3D current needs faces |
| 3 | `Error in mesh mapping on band ... 114` | Periodic flag / band geometry |
| 4 | `Positive motion limit is too large` | Band length vs travel |
| 5 | `band can not have any curved surface` | Flat moving objects only |
| 6 | Non-model cosmetic parts still fail validation | Non-model is not invisible to validation |
| 7 | `validate_simple()` passes but `analyze()` fails | Run a short smoke solve |
| 8 | `.aedt` save fails with `is it readonly? disk full?` | Non-ASCII project path |
| 9 | Field plot PNG shows geometry only, colorbar in mm | Do not trust `export_image` |
| 10 | Transient solve hangs after enabling field saving | SaveFields / `SaveSingleField` trap |
| 11 | `SolutionData` has no `data_real` | PyAEDT 1.3 API change |
| 12 | Raw `Chamfer` / polyline commands cause recursion or invalid parameters | Use native primitives |
| 13 | Reference `.aedt` looks right but does not solve | Validate the reference first |
| 14 | Region becomes enormous after adding long leads | Absolute-position region |

---

## 1. Illegal external terminal

**Symptom**
```
Illegal external terminal 'CoilTerminal1': An external terminal must border
the edge of the problem region and coincides with the surface of a 3D object.
```

**Root cause**
A 3D `CoilTerminal` assigned to a face of a conductor that is fully inside the
solve region is classified as an *external* terminal. Extending leads to the
region wall works only if the terminal face is exactly coplanar with the region
boundary; small offsets still fail.

**Correct pattern**
For a closed conductor (ring, torus, solenoid), create one or two **sheet objects**
at an internal cross-section and assign the `CoilTerminal` to the **sheet object**,
not to a solid face:

```python
modeler.create_rectangle("YZ", [0, ri, 0], [ro - ri, L],
                         name="solenoid_coil_Section1", material=None)
modeler.create_rectangle("YZ", [0, -ro, 0], [ro - ri, L],
                         name="solenoid_coil_Section1_Separate1", material=None)

m3d.assign_coil(["solenoid_coil_Section1"], conductors_number=400,
                polarity="Positive", name="CoilTerminal1")
m3d.assign_coil(["solenoid_coil_Section1_Separate1"], conductors_number=400,
                polarity="Negative", name="CoilTerminal2")
m3d.assign_winding(name="Winding1", winding_type="Voltage", is_solid=False,
                   voltage=12, resistance=4, inductance=0, parallel_branches=1)
m3d.add_winding_coils("Winding1", ["CoilTerminal1", "CoilTerminal2"])
```

The two sheets must cut the **same closed conductor**; the conduction path then
closes through the conductor. This is the method used by the working `Project1`
reference and it validates without touching the region wall.

Do not waste iterations on: half-ring `section` + `separate_bodies`, face-based
terminals on cut faces, or long leads unless the sheet-object pattern is impossible.

## 2. 3D current on an object

**Symptom**
`Cannot apply Current Excitation to non planar entity` when calling
`assign_current(["coil"], ...)` in Maxwell 3D.

**Root cause**
In 3D, `Current` is a face excitation. Object-level current is a 2D-only form.

**Correct pattern**
Use faces with `assign_current`, or use the internal-sheet `CoilTerminal` +
`Winding` pattern above. Do not pass an object name to `assign_current` in 3D.

## 3. Band mesh mapping error 114

**Symptom**
```
Error in mesh mapping on band, please check the potential problem in band setting. 114
```
usually within seconds of starting a transient solve.

**Root cause**
`Maxwell3d.assign_translate_motion(...)` defaults to `periodic_translate=True`
in PyAEDT 1.3. Periodic translation expects Master/Slave boundaries and a
different band topology; a normal mechanical transient then fails mesh mapping.

**Correct pattern**
```python
m3d.assign_translate_motion(
    assignment="band", coordinate_system="Global", axis="Z",
    positive_movement=True, start_position=0,
    periodic_translate=False,          # <-- required for non-periodic travel
    negative_limit=0, positive_limit=78,
    mechanical_transient=True, mass=0.2, damping=0, load_force=0,
    motion_name="Motion1")
```
Also ensure the band itself is a closed solid and does not intersect stationary
objects. A box band is the safest choice.

## 4. Positive motion limit is too large

**Symptom**
`Positive motion limit is too large` during validation.

**Root cause**
The band is not long enough in the travel direction. The limit check effectively
needs rear clearance between the rearmost moving object and the band's rear face
to be at least the requested positive travel.

**Correct pattern**
Size the band as:
```
band_length >= moving_object_length + travel + front_clearance + rear_clearance
```
For a 75-80 mm object and 78 mm travel, a 200 mm band (z -10..190) is safe.
After lengthening the band, the region must also contain the band at its maximum
position; set the region's +Z boundary above `band_zmax + travel`.

## 5. Band can not have any curved surface

**Symptom**
```
In the project with non-periodic translational motion or non-cylindrical
rotational motion, the band can not have any curved surface.
```

**Root cause**
AEDT checks **all objects inside the band**, not just the band object. Any
cylindrical battery, cylindrical magnet, swept polyline prism, or chamfered
solid with a curved face causes the error. A 24-sided `create_cylinder(num_sides=24)`
is still treated as curved by the solver even though `validate_simple()` passes.

**Correct pattern**
Every moving object inside the band must be a **box** (or a native polyhedron
with only planar faces). Use boxes for the battery, magnets, and band. If the
reference model uses cylinders for visual appearance, keep those cylinders
**out of the motion model** (static design or post-processing figure), or accept
a box approximation and document the deviation. Do not rely on `num_sides`,
swept polygons, or chamfers to bypass the check.

## 6. Non-model parts and validation

**Symptom**
A cosmetic non-model cylinder added for appearance causes:
`Parts band and battery_body_visual intersect`.

**Root cause**
`non_model=True` removes an object from the solve mesh, but **not** from the
geometry validation intersection checks. A non-model object inside/overlapping
the band is still reported.

**Correct pattern**
Do not use non-model overlays to fake a curved moving part. Either use boxes, or
produce the visual with a separate static design / post-processing figure.
If a non-model decoration is required, keep it completely outside all solve
objects with a real gap.

## 7. Validate passes but solve fails

**Symptom**
`validate_simple()` returns `True`, then `analyze()` fails in <30 s.

**Root cause**
Validation covers excitation/conduction-path syntax, not every solver constraint
(band surface type, moving-object curvature, mesh mapping).

**Correct pattern**
Before a long transient run, do a **smoke solve** with a short stop time:
```python
setup.props["StopTime"] = "0.02s"
setup.props["TimeStep"] = "0.002s"
ok = m3d.analyze("Setup1")
```
Print `GetMessages(project, design, 2/1/0)` immediately and only extend the run
after the smoke test passes.

## 8. Non-ASCII project path

**Symptom**
`save_project()` returns `False` and AEDT logs
`an error occured while writing to the file. is it readonly? disk full?`
even though the folder is writable and the disk has space.

**Root cause**
AEDT 2026.1 on Windows cannot reliably save a project whose full path contains
non-ASCII characters (e.g. a Chinese Desktop folder). Python can write there;
AEDT cannot.

**Correct pattern**
Save the `.aedt` to an ASCII-only working directory, then copy the project and
`.aedtresults` to the user-facing folder with Python:
```python
AEDT_ROOT = Path(r"C:\Users\<user>\Documents\Ansoft\BatteryEM")
PROJECT_DIR = AEDT_ROOT / "Task2"
...
shutil.copy2(aedt, deliverable_dir / aedt.name)
shutil.copytree(aedt.with_suffix(".aedtresults"),
                deliverable_dir / aedt.with_suffix(".aedtresults").name,
                dirs_exist_ok=True)
```
Use an ASCII path for diagnostics too; otherwise a failed save silently reopens
the old project and creates a **new design with a suffix**, making diagnostics
misleading.

## 9. Field plot PNG is geometry-only

**Symptom**
`create_fieldplot_volume(...).export_image(...)` produces a PNG that shows the
model in wireframe with a **length** colorbar (0-300 mm), not a B-field contour.

**Root cause**
In non-graphical mode / some AEDT builds, the field plot image export falls back
to a model image when the active plot has no valid field data or when the plot
is not the active view. The file exists, so the failure is silent.

**Correct pattern**
Export field data and render it yourself:
```python
gf = m3d.post.export_field_file_on_grid(
    quantity="Mag_B", solution="Setup1 : LastAdaptive",
    file_name=str(out_dir / "Mag_B_grid.txt"), grid_type="Cartesian",
    grid_start=[-40, -1, -20], grid_stop=[40, 1, 100],
    grid_step=[1, 1, 1], is_vector=False, export_with_sample_points=True)
```
Parse the `x y z value` rows (SI units), filter the symmetry plane, and plot with
matplotlib `tricontourf`/`pcolormesh`. This produced the only reliable field maps
in the project. For transient models where field saving is unreliable, build a
**separate Magnetostatic design** with the same geometry and export the grid there.

## 10. Transient field saving hangs

**Symptom**
After `setup.set_save_fields(...)`, the transient solve sits for tens of minutes
with near-zero solver CPU and no progress; killing it leaves a lock file.

**Root cause**
`set_save_fields` with `range_type="Custom", subrange_type="SinglePoints"` sets
`SaveFieldsType=Custom` but can leave `SaveSingleField=False`. `Every N Steps`
can also trigger very large field output. In this environment both paths hung
on a transient solve.

**Correct pattern**
Do not enable transient field saving unless the field plot is essential. Use a
separate Magnetostatic design for field maps (entry 9). If field saving is
required, use a short smoke solve and verify `SaveFieldsType`, `SaveSingleField`,
and the saved field directory (`fldplt`) before committing to the full run.

## 11. SolutionData API change

**Symptom**
`'SolutionData' object has no attribute 'data_real'` after a successful solve.

**Root cause**
PyAEDT 1.3 removed/renamed the convenience accessor. The report data itself is
valid.

**Correct pattern**
Use one of:
```python
x, y = sd.get_expression_data("Force1.Force_z")
```
or export the report and parse the CSV:
```python
m3d.post.export_report_to_csv(str(out_dir), "Force1_Report")
# then read Force1_Report.csv with csv.reader
```
Prefer the CSV path for numeric summaries: it is stable across PyAEDT versions
and works even when the report object API changes.

## 12. Raw modeling commands

**Symptom**
`invalid parameters to createpolyline operation`, or a Python logging recursion
after `oeditor.Chamfer(...)` with four edge IDs.

**Root cause**
The raw command arrays and `segment_type` handling differ between PyAEDT
versions; a malformed array can also leave the object in a state that breaks
PyAEDT's object refresh/logging.

**Correct pattern**
Use native PyAEDT primitives (`create_box`, `create_cylinder`,
`create_rectangle`, `subtract`, `unite`). If a raw command is unavoidable,
inspect the exact signature/array format in the installed AEDT scripting guide
and run it in a throwaway diagnostic project first. Do not build production
geometry with unverified raw `Chamfer`/polyline arrays.

## 13. Reference project is not necessarily solvable

**Symptom**
A hand-built reference `.aedt` looks correct but `validate_simple()` reports
intersecting parts, `Positive motion limit is too large`, or a curved band.

**Root cause**
A model can be visually complete without being solver-valid. Reference projects
often contain overlapping vacuum bodies or a cylindrical band that the solver
rejects.

**Correct pattern**
Before copying a reference:
1. Open it read-only and print every object's `material_name`, `bounding_box`,
   `volume`, and `object_type`.
2. Run `validate_simple()` and read the full log.
3. Reproduce only the **validated** excitation topology; fix geometry conflicts
   and band sizing rather than copying them.

## 14. Percentage-pad region explosion

**Symptom**
A 100% `Percentage Offset` region becomes hundreds of mm across after adding
long leads or a long band, slowing the solve dramatically.

**Root cause**
Percentage padding is relative to the model's largest dimension. Long thin
leads dominate the bounding box and inflate the region in every direction.

**Correct pattern**
Use absolute coordinates for a controlled region:
```python
modeler.create_region(
    pad_value=[80, -80, 80, -80, 200, -80],
    pad_type=["Absolute Position"] * 6, name="Region")
```
Keep the region large enough for field decay and for the band's full travel, but
do not let a lead length drive the whole domain size.

---

## Pre-flight checklist for 3D transient motion

- [ ] Coil excitation uses **internal sheet** `CoilTerminal` + `Winding`, or a
      validated alternative; `validate_simple()` passes.
- [ ] `periodic_translate=False`.
- [ ] Band is a closed **box**; all moving objects are boxes; no cylinders,
      swept polygons, chamfers, or non-model overlays inside the band.
- [ ] Band length covers object length + travel + rear clearance.
- [ ] Region contains the band at its maximum travel position.
- [ ] Battery/band use distinct materials if they overlap; avoid vacuum-on-vacuum
      overlap.
- [ ] Project path is ASCII-only; deliverable copy happens after `save_project()`.
- [ ] A 0.02 s smoke solve passes before the full run.
- [ ] Field maps come from `export_field_file_on_grid` + matplotlib, not
      `export_image`.
- [ ] Numeric summaries come from exported CSV, not `SolutionData.data_real()`.
