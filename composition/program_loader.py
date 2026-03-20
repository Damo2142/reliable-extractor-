"""
SBS Composition Engine v2 — Program Loader

Loads .bas program text from the programs/reliable/ directory
and injects it into assembled ControllerConfig program definitions.
"""

import os
from pathlib import Path

PROGRAMS_DIR = Path(__file__).parent / "programs" / "reliable"


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


def inject_program_code(config):
    """
    Load .bas code for all programs in the config.
    Adds line numbers if missing (Control-BASIC requires them).
    """
    for prg in config.programs:
        if not prg.code:
            prg.code = load_program_code(prg.filename)
        # Add line numbers if the code doesn't have them
        if prg.code and not _has_line_numbers(prg.code):
            prg.code = add_line_numbers(prg.code)


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
