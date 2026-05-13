"""
SBS Composition Engine v2 — Program Loader

Loads .bas program text from the programs/reliable/ directory
and injects it into assembled ControllerConfig program definitions.
"""

import os
import re
from pathlib import Path

PROGRAMS_DIR = Path(__file__).parent / "programs" / "reliable"


def _collect_local_point_names(config) -> set:
    """Return the set of point names defined locally on this controller.
    These are the names that should be prefixed with {device-name}- when
    referenced bare in program code, so .bas references match Excel names.
    """
    names = set()
    for pt in getattr(config, "inputs", []) or []:
        if getattr(pt, "name", None):
            names.add(pt.name)
    for pt in getattr(config, "outputs", []) or []:
        if getattr(pt, "name", None):
            names.add(pt.name)
    for v in getattr(config, "values", []) or []:
        if getattr(v, "name", None):
            names.add(v.name)
    for lp in getattr(config, "loops", []) or []:
        if getattr(lp, "name", None):
            names.add(lp.name)
    for tbl in getattr(config, "tables", []) or []:
        if getattr(tbl, "name", None):
            names.add(tbl.name)
    for arr in getattr(config, "arrays", []) or []:
        if getattr(arr, "name", None):
            names.add(arr.name)
    for sch in getattr(config, "schedules", []) or []:
        if getattr(sch, "name", None):
            names.add(sch.name)
    return names


def format_program_commas(programs) -> None:
    """Insert a space before every comma in program code — RC Control-BASIC
    syntax requires `arg , arg` style in function calls and statement lists,
    not `arg, arg`.

    Idempotent: commas that already have a space before them are left alone.
    Operates on any list of ProgramDef objects (config.programs or merged plant lists).
    """
    for prg in programs or []:
        code = getattr(prg, "code", None)
        if not code:
            continue
        # Add space before comma when the preceding char is not whitespace.
        prg.code = re.sub(r'(?<=\S),', ' ,', code)


def prefix_local_points(config) -> None:
    """Replace bare local-point references in every program's code with
    {device-name}-NAME so .bas point names match the Excel.

    Rules:
      - Only names defined on this controller (inputs/outputs/values/loops/
        tables/arrays/schedules) are touched.
      - Already-prefixed references ({device-name}-X, {parent}X) are left alone.
      - BASIC keywords/built-in functions are untouched because they are not
        in the local-name set.
      - Cross-controller references like AHU-SET-LIMITS are untouched because
        they are not in the local-name set.
    Idempotent: safe to call more than once.
    """
    local_names = _collect_local_point_names(config)
    if not local_names:
        return
    # Match longest names first so RMT-SP-CLG resolves before RMT or RMT-SP.
    sorted_names = sorted(local_names, key=len, reverse=True)
    for prg in getattr(config, "programs", []) or []:
        code = getattr(prg, "code", None)
        if not code:
            continue
        for name in sorted_names:
            # Identifier chars in Control-BASIC are A-Z, 0-9, _, -.
            # `}` is in the lookbehind exclusion so {device-name}- and {parent}
            # already-prefixed references don't get matched a second time.
            pattern = r'(?<![A-Za-z0-9_\-\}])' + re.escape(name) + r'(?![A-Za-z0-9_\-])'
            code = re.sub(pattern, '{device-name}-' + name, code)
        prg.code = code


def load_program_code(filename: str) -> str:
    """Load .bas program code from the programs directory."""
    filepath = PROGRAMS_DIR / filename
    if filepath.exists():
        return filepath.read_text()
    return f"REM ***** Program file not found: {filename} *****\n"


def add_line_numbers(code: str) -> str:
    """
    Add Control-BASIC line numbers to program code.
    Skips blank lines and existing numbered lines.
    Line numbers: 10, 20, 30, ... (standard BASIC convention)
    """
    lines = code.split("\n")
    numbered = []
    line_num = 10

    for line in lines:
        stripped = line.strip()
        # Skip blank lines — keep them but don't number
        if not stripped:
            numbered.append("")
            continue
        # Skip if already has a line number
        if stripped and stripped[0].isdigit():
            numbered.append(line)
            # Advance past this line number
            try:
                existing_num = int(stripped.split()[0])
                if existing_num >= line_num:
                    line_num = existing_num + 10
            except ValueError:
                pass
            continue
        # Add line number
        numbered.append(f"{line_num} {line}")
        line_num += 10

    return "\n".join(numbered)


def number_programs(programs):
    """
    Ensure every ProgramDef in a list has BASIC line numbers.
    Works on any list of ProgramDef objects — AHU config.programs,
    HW/CHW merged['programs'], or any other source.
    """
    for prg in programs:
        if prg.code and not _has_line_numbers(prg.code):
            prg.code = add_line_numbers(prg.code)


def inject_program_code(config):
    """
    Load .bas code for all programs in the config.
    Prefixes bare local-point references with {device-name}- so .bas
    names match the Excel, formats commas to RC CBAS syntax (` , `),
    then adds line numbers.
    """
    for prg in config.programs:
        if not prg.code:
            prg.code = load_program_code(prg.filename)
    prefix_local_points(config)
    format_program_commas(config.programs)
    number_programs(config.programs)


def _has_line_numbers(code: str) -> bool:
    """Check if code already has BASIC line numbers on most lines."""
    lines = [l.strip() for l in code.split("\n") if l.strip()]
    if not lines:
        return False
    numbered = sum(1 for l in lines if l and l[0].isdigit())
    return numbered > len(lines) * 0.5  # More than half have numbers


def export_bas_files(config, output_dir: str):
    """
    Export individual .bas files for each program.
    Substitutes {device-name} and {parent} with actual names if provided.
    """
    os.makedirs(output_dir, exist_ok=True)

    for prg in config.programs:
        code = prg.code or load_program_code(prg.filename)

        # Template substitution if actual device names provided
        if config.device_name != "{device-name}":
            code = code.replace("{device-name}", config.device_name)
        if config.parent_name != "{parent}":
            code = code.replace("{parent}", config.parent_name)

        filepath = os.path.join(output_dir, prg.filename)
        with open(filepath, "w") as f:
            f.write(code)

    return len(config.programs)


def list_available_programs():
    """List all .bas files in the programs directory."""
    if not PROGRAMS_DIR.exists():
        return []
    return sorted([f.name for f in PROGRAMS_DIR.glob("*.bas")])
