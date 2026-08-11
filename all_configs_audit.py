#!/usr/bin/env python3
"""Assemble every STANDARD_CONFIG, check for assembly errors and program bugs.

Walks STANDARD_CONFIGS from module_registry, hits the engine for each one,
and reports any error.
"""
import json
import os
import sys

sys.path.insert(0, "/srv/reliable-generator-dev")
from composition.module_registry import STANDARD_CONFIGS, EQUIPMENT_FAMILIES, hwp_assemble, chwp_assemble  # noqa: E402
from composition.assembler import assemble  # noqa: E402
from composition.program_loader import inject_program_code  # noqa: E402


PLANT_FAMILIES = {"HW-PLANT", "CHW-PLANT-AIR", "CHW-PLANT-TOWER", "VVT-SYSTEM"}


def audit_one_config(cfg_id, cfg):
    fam = cfg["family"]
    mods = cfg.get("modules", [])
    if fam in PLANT_FAMILIES:
        return ("SKIP-plant", None)
    try:
        config = assemble(mods, equipment_family=fam, controller_model="auto")
        inject_program_code(config)
    except Exception as e:
        return ("FAIL-assemble", str(e))

    # Probe: every program references local points that exist in the config.
    local_names = set()
    for pt in config.inputs: local_names.add(pt.name)
    for pt in config.outputs: local_names.add(pt.name)
    for v in config.values: local_names.add(v.name)
    for l in config.loops: local_names.add(l.name)
    for t in config.tables: local_names.add(t.name)
    for s in config.schedules: local_names.add(s.name)

    import re
    missing = set()
    for prg in config.programs:
        if not prg.code:
            continue
        for m in re.finditer(r'\{device-name\}-([A-Za-z][A-Za-z0-9/\-_%@]*)', prg.code):
            name = m.group(1)
            if name not in local_names:
                missing.add(name)
    if missing:
        return ("FAIL-missing-ref", sorted(missing))
    return ("OK", None)


def main():
    total = len(STANDARD_CONFIGS)
    ok = 0
    skipped = 0
    failures = []
    for cid, cfg in STANDARD_CONFIGS.items():
        status, detail = audit_one_config(cid, cfg)
        if status == "OK":
            ok += 1
        elif status.startswith("SKIP"):
            skipped += 1
        else:
            failures.append((cid, status, detail))
    print(f"\nAudit summary: {ok}/{total - skipped} non-plant configs OK; {skipped} skipped (plant); {len(failures)} failures")
    if failures:
        print("\nFailures:")
        for cid, status, detail in failures:
            print(f"\n  {cid} — {status}")
            print(f"    {detail}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
