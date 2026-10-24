#!/usr/bin/env python
"""Validate a generated Maxwell PyAEDT script before running it.

Checks (all static, no AEDT/pyaedt required):
  1. Python syntax (py_compile).
  2. Required imports (ansys.aedt.core or pyaedt).
  3. A CONFIG dict exists and contains the expected top-level sections.
  4. Required pipeline calls present: validate_simple, analyze, save_project,
     and at least one post-processing/export call.
  5. Undefined-name scan over the module body (catches typos in CONFIG keys,
     renames, and arithmetic on unit strings).
  6. Unit hygiene: strings carrying units are used where AEDT expects them.

Usage:
    python validate_pyaedt_script.py <script.py> [--require-save] [--verbose]

Exit code 0 = all checks pass, 1 = any check failed.
"""

import argparse
import ast
import pathlib
import py_compile
import sys

EXPECTED_SECTIONS = (
    "project_name", "design_name", "solution_type", "version",
    "non_graphical", "geometry", "materials", "setup", "post_processing",
)

REQUIRED_CALLS = ("validate_simple", "analyze", "save_project")

POSTPROCESS_CALLS = (
    "create_fieldplot_volume", "create_fieldplot_surface", "create_fieldplot_cutplane",
    "create_report", "export_field_plot", "export_report_to_jpg",
    "export_report_to_csv", "get_solution_data", "export_image",
)


class Checker:
    def __init__(self, path, verbose=False):
        self.path = pathlib.Path(path)
        self.verbose = verbose
        self.errors = []
        self.warnings = []

    def report(self):
        for item in self.warnings:
            print(f"[warn ] {item}")
        for item in self.errors:
            print(f"[error] {item}")
        if not self.errors:
            print(f"[ok   ] {self.path.name}: all checks passed "
                  f"({len(self.warnings)} warnings)")
            return 0
        print(f"[fail ] {self.path.name}: {len(self.errors)} error(s), "
              f"{len(self.warnings)} warning(s)")
        return 1

    def check_syntax(self):
        try:
            py_compile.compile(str(self.path), doraise=True)
        except py_compile.PyCompileError as exc:
            self.errors.append(f"syntax error: {exc}")
            return None
        with open(self.path, encoding="utf-8") as fh:
            return ast.parse(fh.read(), filename=str(self.path))

    def check_imports(self, tree):
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        have_pyaedt = any("pyaedt" in i or "ansys.aedt.core" in i for i in imports)
        if not have_pyaedt:
            self.errors.append("missing import: expected 'ansys.aedt.core' or 'pyaedt'")
        elif self.verbose:
            print(f"[info ] imports: {', '.join(imports)}")

    def check_config(self, tree):
        config = None
        for node in ast.iter_child_nodes(tree):
            if (isinstance(node, ast.Assign) and node.targets
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == "CONFIG"
                    and isinstance(node.value, ast.Dict)):
                config = node.value
                break
        if config is None:
            self.errors.append("no CONFIG dict found at module level")
            return
        keys = [k.value for k in config.keys if isinstance(k, ast.Constant)
                and isinstance(k.value, str)]
        for section in EXPECTED_SECTIONS:
            if section not in keys:
                self.warnings.append(f"CONFIG missing expected section '{section}'")
        # Keys referenced in the body but absent from CONFIG (typo guard).
        referenced = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
                    and node.value.id == "CONFIG" and isinstance(node.slice, ast.Constant):
                referenced.add(str(node.slice.value))
        missing = referenced - set(keys)
        if missing:
            self.errors.append(f"CONFIG keys referenced but never defined: {sorted(missing)}")

    def check_pipeline(self, tree):
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
        for required in REQUIRED_CALLS:
            if required not in calls:
                self.errors.append(f"missing pipeline call '{required}'")
        if not any(c in calls for c in POSTPROCESS_CALLS):
            self.warnings.append("no post-processing/export call found "
                                 "(field plot, report, or solution data)")

    def check_undefined_names(self, tree):
        assigned = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Name, ast.arg)):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    assigned.add(node.id)
                elif isinstance(node, ast.arg):
                    assigned.add(node.arg)
            elif isinstance(node, ast.alias):
                assigned.add(node.asname or node.name.split(".")[0])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                assigned.add(node.name)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                assigned.add(node.name)
            elif isinstance(node, ast.comprehension):
                assigned.add(node.target.id if isinstance(node.target, ast.Name) else "")
            elif isinstance(node, (ast.Tuple, ast.List)) and isinstance(
                    getattr(node, "ctx", None), ast.Store):
                for el in node.elts:
                    if isinstance(el, ast.Name):
                        assigned.add(el.id)
        # Builtins and allowed globals.
        allowed = assigned | set(dir(__builtins__)) | {
            "CONFIG", "Maxwell3d", "Maxwell2d", "Path", "traceback", "os"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in allowed and not node.id.startswith("_"):
                    self.errors.append(
                        f"line {getattr(node, 'lineno', '?')}: undefined name '{node.id}'")

    def check_unit_hygiene(self, tree):
        """Heuristic: excitation/material/geometry string args should carry units."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("assign_current", "assign_voltage", "assign_winding",
                                      "assign_coil", "create_setup"):
                    for kw in node.keywords:
                        if kw.arg in ("amplitude", "current", "voltage", "resistance",
                                      "inductance", "stop_time", "time_step", "Frequency") \
                                and isinstance(kw.value, ast.Constant) \
                                and isinstance(kw.value.value, str) \
                                and not any(u in kw.value.value for u in
                                            ("A", "V", "ohm", "H", "Hz", "ms", "s", "deg", "mm", "mT", "T")):
                            self.warnings.append(
                                f"line {node.lineno}: '{kw.arg}' string value "
                                f"'{kw.value.value}' has no unit")


def main():
    parser = argparse.ArgumentParser(description="Validate a Maxwell PyAEDT script.")
    parser.add_argument("script", help="path to the generated script")
    parser.add_argument("--verbose", action="store_true", help="print extra info")
    args = parser.parse_args()

    checker = Checker(args.script, verbose=args.verbose)
    tree = checker.check_syntax()
    if tree is not None:
        checker.check_imports(tree)
        checker.check_config(tree)
        checker.check_pipeline(tree)
        checker.check_undefined_names(tree)
        checker.check_unit_hygiene(tree)
    sys.exit(checker.report())


if __name__ == "__main__":
    main()
