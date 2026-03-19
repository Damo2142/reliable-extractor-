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


def inject_program_code(config):
    """
    Load .bas code for all programs in the config.
    Also substitutes {device-name} and {parent} templates.
    """
    for prg in config.programs:
        if not prg.code:
            prg.code = load_program_code(prg.filename)


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
