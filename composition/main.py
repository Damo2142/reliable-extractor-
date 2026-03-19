"""
SBS Composition Engine v2 — Standalone Server + CLI

FastAPI server for standalone UI (separate port from DFA platform).
Also runnable as CLI for testing.
"""

import sys
import json
import os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from composition.assembler import assemble
from composition.excel_gen import generate_excel
from composition.module_registry import (
    list_modules, list_by_category, get_module,
    STANDARD_CONFIGS
)


def cli_test():
    """Quick CLI test — assemble the A201-equivalent config and generate Excel."""
    print("=" * 60)
    print("SBS Composition Engine v2 — Test Build")
    print("=" * 60)

    # A201-equivalent: CHW + HW + ERW + Enthalpy Econ + EF-VFD + DCV-CO2
    config_name = "AHU-VAV-CHW-HW-ECON-ERW"
    std = STANDARD_CONFIGS[config_name]
    print(f"\nBuilding: {std['name']}")
    print(f"Modules: {', '.join(std['modules'])}")

    # Assemble
    config = assemble(std["modules"])

    print(f"\n--- ASSEMBLY RESULTS ---")
    print(f"Selected modules: {len(config.selected_modules)}")
    print(f"  {', '.join(config.selected_modules)}")
    print(f"\nInputs:  {len(config.inputs)} points (highest row: {config.highest_input_row})")
    for inp in config.inputs:
        print(f"  Row {inp.row:2d}: {inp.point_type} {inp.name:<20s} {inp.description}")

    print(f"\nOutputs: {len(config.outputs)} points (highest row: {config.highest_output_row})")
    for out in config.outputs:
        rev = " (REV)" if out.reverse else ""
        print(f"  Row {out.row:2d}: {out.point_type} {out.name:<20s} {out.description}{rev}")

    print(f"\nValues:  {len(config.values)} AV/BV/MV points")
    print(f"Loops:   {len(config.loops)} PID loops")
    print(f"Tables:  {len(config.tables)} scaling tables")
    print(f"Programs:{len(config.programs)} .bas programs")
    print(f"Schedules:{len(config.schedules)}")
    print(f"Trends:  {len(config.trends)} STL trend logs")
    print(f"System Groups: {len(config.system_groups)}")

    print(f"\n--- CONTROLLER SELECTION ---")
    print(f"Model:      {config.controller_model}")
    print(f"Expansion:  {config.expansion_count} x {config.expansion_model}" if config.expansion_count else "No expansion needed")
    print(f"Highest Input Row:  {config.highest_input_row}")
    print(f"Highest Output Row: {config.highest_output_row}")

    # Generate Excel
    print(f"\n--- GENERATING EXCEL ---")
    excel_data = generate_excel(config)
    out_path = "/srv/dfa/drops/composition-test-output.xlsx"
    with open(out_path, "wb") as f:
        f.write(excel_data)
    print(f"Excel saved: {out_path} ({len(excel_data):,} bytes)")

    # Generate SOO
    soo_path = "/srv/dfa/drops/composition-test-soo.txt"
    with open(soo_path, "w") as f:
        f.write(config.soo_document)
    print(f"SOO saved: {soo_path}")

    # Summary JSON
    summary = {
        "config_name": config_name,
        "modules": config.selected_modules,
        "controller": config.controller_model,
        "expansion": f"{config.expansion_count}x {config.expansion_model}" if config.expansion_count else "none",
        "inputs": len(config.inputs),
        "outputs": len(config.outputs),
        "values": len(config.values),
        "loops": len(config.loops),
        "tables": len(config.tables),
        "programs": len(config.programs),
        "trends": len(config.trends),
        "highest_input_row": config.highest_input_row,
        "highest_output_row": config.highest_output_row,
    }
    summary_path = "/srv/dfa/drops/composition-test-summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved: {summary_path}")

    print(f"\n--- AVAILABLE MODULES ---")
    by_cat = list_by_category()
    for cat, mods in sorted(by_cat.items()):
        print(f"\n  {cat.upper()}:")
        for m in mods:
            core_tag = " [CORE]" if m["is_core"] else ""
            print(f"    {m['id']:<20s} {m['name']}{core_tag}")

    print(f"\n--- STANDARD CONFIGS ---")
    for cid, cdef in STANDARD_CONFIGS.items():
        print(f"  {cid}: {cdef['name']}")

    print("\nDone!")


if __name__ == "__main__":
    cli_test()
