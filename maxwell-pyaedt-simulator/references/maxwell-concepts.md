# Maxwell Simulation Concepts

Domain background distilled from the Ansys Maxwell help (`Maxwell.pdf`, release 2026 R1). Use this to interpret natural-language requests correctly before translating to code.

## Solver types and formulations

Choosing the solver happens before drawing anything; changing it later invalidates all setups and solutions.

| Solver | Solves for | Sources | Derived quantities | Notes |
|---|---|---|---|---|
| Magnetostatic | H, J (B computed from H) | DC currents, static external H-field boundaries, permanent magnets | force, torque, energy, inductance | 2D/3D |
| AC Magnetic (Eddy Current) | H (frequency domain) | AC currents, time-harmonic boundary H | force, torque, energy, losses, impedance | 3D: T-Omega or A-Phi; 2D: A-Phi only. Optional displacement current, optional DC bias ("AC Magnetic with DC", T-Omega) |
| Transient | H, J (time domain) | time-varying currents/voltages, moving magnets/coils, external circuit coupling | force, torque, energy, speed, position, winding flux linkage, induced voltage | 3D: T-Omega default; A-Phi for mixed excitations on one conduction path / capacitive effects / ECAD-PCB; A-Phi does NOT support motion |
| Electrostatic | E (and potential) | voltages/charges | force, torque, capacitance | 2D/3D |
| DC Conduction / Electric DC Conduction | J, E, potential | currents/voltages | resistance, ohmic loss | 2D/3D; 3D option with insulator field |
| AC Conduction | J, E (frequency domain) | currents/voltages | resistance, impedance, loss | 2D/3D |
| Electric Transient | time-domain electric fields | time-varying voltages/currents | loss, force | 3D |

T-Omega vs A-Phi (3D transient/AC): T-Omega is efficient for electrical machines, ignores displacement current, supports motion; A-Phi supports mixed excitation types on the same conduction path and displacement current, but no motion. Choose A-Phi only when the user explicitly needs those capabilities.

## Standard model workflow (from the 2D Solenoid tutorial)

1. Insert design (`Maxwell2D`/`Maxwell3D`), pick solver type and (2D) geometry mode: Cartesian XY or Cylindrical about Z.
2. Set model units.
3. Draw geometry (core, coil, yoke, bonnet, plugnut...). In 2D, draw cross-section faces; in 3D, solids.
4. Assign materials (magnetic steel with BH curve, copper windings, vacuum/air background).
5. Assign boundaries and excitations (insulating, flux tangential, vector potential, current/voltage/winding).
6. Assign solution parameters (force on plugnut, torque, matrix).
7. Mesh operations (length-based, skin depth, mesh region).
8. Add solution setup with convergence criteria.
9. Analyze.
10. Post-process: field plots (saturation levels, equipotential contours), reports (force value), export.

## Boundaries and excitations (applicability)

### Boundaries
| Boundary | Applies to | Purpose |
|---|---|---|
| Insulating | 2D/3D | no current flow normal to surface |
| Vector Potential | 2D edges | fixes magnetic vector potential (flux-normal default is automatic) |
| Zero Tangential H | 3D (mag static/AC/transient) | tangential H = 0 on boundary; models flux-normal outer boundary / external field |
| Integrated Zero Tangential H | 3D | zero tangential H integrated over the face (external field excitation) |
| Flux Tangential | 2D/3D | sets tangential field to zero on boundary |
| Symmetry | 2D/3D | even/odd symmetry plane to reduce model |
| Resistive Sheet | 3D | thin resistive layer |
| Thin Layer | 3D | layered materials approximation |
| Impedance | 3D | complex impedance wall |
| Dependent/Independent | 2D/3D | magnetic circuit coupling between matching faces |

### Excitations
| Excitation | Solutions | Notes |
|---|---|---|
| Current | magnetostatic, AC magnetic, transient, conduction | on faces (solid conductors, total current) or objects (stranded, current per object) |
| Current Density | conduction/AC | vector J excitation on objects |
| Voltage | transient, conduction, electrostatic | on terminals/faces; for transient: winding or terminal voltage |
| Voltage Drop | conduction/AC/DC | across a solid conductor |
| Winding | AC magnetic (incl. DC), transient | group: Current / Voltage / External type; solid or stranded; parallel branches; phase (AC) |
| Coil / Coil Terminal | 2D transient & AC, 3D transient A-Phi | terminal on conductor cross-section; ordered terminals define conduction path |
| Permanent Magnet Field | magnetostatic/transient | link field from another design |
| Floating / Sink | electrostatic/conduction | floating conductor / current sink |
| Charge / Volume Charge Density | electrostatic | surface charge / volume charge |

A-Phi transient supports only Flux Tangential, Insulating, Symmetry, Independent/Dependent Matching, Resistive Sheet boundaries and Winding (via Coil Terminal), Voltage, Current excitations. Coil terminals must be ordered to match the physical conductor connection; consecutive intermediate terminals are made equipotential.

**3D closed-coil terminals.** For a 3D ring/solenoid that is fully inside the solve region, do not put a `CoilTerminal` on a solid face: it is classified as an external terminal and fails with `Illegal external terminal ... must border the edge of the problem region`. Instead, create one or two **sheet objects** at an internal cross-section of the conductor (e.g. rectangles on the x=0 plane spanning the coil radial thickness), assign the `CoilTerminal` to those sheet objects, and connect them with one Winding. The conduction path closes through the conductor and validates without touching the region wall.

## Motion (transient only)

- The moving object must be enclosed in a **band**; band is assigned in `MotionSetup.AssignBand`.
- Move types: Rotate (about an axis, optional limits, optional non-cylindrical about a point) or Translate (with negative/positive limits or periodic).
- Mechanical transient: solver integrates motion from force + user mass, damping, load force.
- Compute force/torque parameters on the moving object for motion results.
- **Non-periodic translation must set `periodic_translate=False`.** The PyAEDT helper defaults to `True`; leaving it causes `Error in mesh mapping on band. 114`.
- **Every moving object inside the band must have only planar faces.** AEDT rejects a cylindrical battery, a cylinder band, a `num_sides` prism, a swept polygonal prism, or a chamfered solid with `band can not have any curved surface`. Boxes are the reliable choice. Non-model cosmetic cylinders do not bypass this and still fail geometry-intersection validation.
- **Band length** must provide rear clearance at least equal to the positive travel; otherwise validation reports `Positive motion limit is too large`. Size it as object length + travel + clearances.
- **The region must contain the band at its maximum travel position**, not only at t=0.

## Mesh operations

| Operation | Purpose |
|---|---|
| Length-based | max element length / element count in a volume |
| Skin-depth | layered refinement on conductor surfaces for AC |
| Surface mesh | surface refinement level |
| Mesh region | refine a box/cylinder region around critical geometry |
| Model resolution | defeature small features |
| Curvilinear elements | higher-order curved elements |
| Edge cut / cylindrical gap / density control | clone/refinement utilities |

## Post-processing

- **Field plots** visualize quantities on volumes/surfaces/cut planes; exportable as images (PNG) and solver files (`.aedtplt`). Quantities: `Mag_B`, `Mag_H`, `Mag_J`, `ComplexMag_J`, `Mag_E`, `E_Vector`, `Energy`, `Ohmic_Loss`, `Total_Loss`, `Hysteresis_Loss`, `Dielectric_Loss`, `Temperature`, `Volume_Force_Density`, `Surface_Force_Density`, `Mesh`.
- **Reports** plot expressions vs a sweep (frequency, time, position) or as data tables. Common Maxwell report categories: Transient, Fields, Matrix, DC R/L Fields, AC R/L Fields, C Fields, Harmonic Force, Noise Vibration.
- **Solution parameters** (force/torque/matrix) are computed during the solve and appear in reports.

## 2D vs 3D differences

- 2D has a geometry mode: Cartesian XY (in-plane fields, z-extrusion ignored) or Cylindrical about Z (axisymmetric, r-z plane).
- 2D models are cross-sections; "thickness" for XY is set via model depth; axisymmetric has implicit 360-degree revolution.
- Boundaries/excitations in 2D are applied to edges/objects in the cross-section plane.
- 3D adds: T-Omega/A-Phi choice, ECAD 3D layout component integration, HPC partitioning (domains/cores), more material models.

## HPC (brief)

- Maxwell supports distributed solving (domains, cores, GPUs for sparse LU) via HPC licensing. PyAEDT `analyze(setup=..., cores=..., tasks=..., gpus=...)` can request resources. See `HPC_Admin.pdf` in the source documentation for licensing and machine configuration; keep defaults unless the user explicitly asks for HPC settings.

## Source documentation

The skill is grounded in these documents (original location: `C:\Users\30571\Desktop\Maxwell help`):
- `Maxwell.pdf` — main user guide (solver types, boundaries/excitations, mesh, solution settings, post-processing, optimetrics).
- `MaxwellScriptingGuide.pdf` — scripting API (chapters 10, 12-20) and PyAEDT introduction.
- Tutorial PDFs: 2D Magnetostatic Solenoid, Rotational Actuator, Transient Problem, Skin Depth Seeding, ECAD Integration.
- `HPC_Admin.pdf` — HPC administration.
