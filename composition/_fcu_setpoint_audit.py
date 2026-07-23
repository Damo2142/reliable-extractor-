#!/usr/bin/env python3
"""
FCU setpoint-refactor audit.

Assembles all FCU standard configs through the real server path
(assemble + inject_program_code) and checks the same failure classes the
UV setpoint audit checks, focused on the single-setpoint refactor:

  1. Assembly errors
  2. Programs with empty code
  3. Programs missing BASIC line numbers (number_programs must have run)
  4. Unresolved {device-name}- point references in .bas programs
  5. No lingering CFG-OCC-CLG-SP / CFG-OCC-HTG-SP references or defs
  6. RMT-SP + CFG-RMT-SP-DB are defined AND referenced in MODE-CTRL

Usage:
    cd /srv/reliable-generator-dev
    PYTHONPATH=. venv/bin/python -m composition._fcu_setpoint_audit
"""

import re
import sys

from composition.assembler import assemble
from composition.program_loader import inject_program_code
from composition.module_registry import STANDARD_CONFIGS

_POINT_REF_RE = re.compile(r'\{device-name\}-([A-Z0-9][A-Z0-9\-/]*[A-Z0-9/])')


def defined_names(cfg):
    names = set()
    for coll in (cfg.inputs, cfg.outputs, cfg.values, cfg.loops,
                 cfg.tables, cfg.arrays, cfg.schedules):
        for obj in coll:
            names.add(obj.name)
    return names


def prog_refs(code):
    refs = set()
    for line in code.splitlines():
        s = line.strip()
        s_norm = re.sub(r'^\d+\s+', '', s)
        if s_norm.upper().startswith('REM'):
            continue
        for m in _POINT_REF_RE.finditer(line):
            refs.add(m.group(1))
    return refs


def has_line_numbers(code):
    lines = [l.strip() for l in code.split("\n") if l.strip()]
    if not lines:
        return False
    numbered = sum(1 for l in lines if l and l[0].isdigit())
    return numbered > len(lines) * 0.5


def main():
    fcu_ids = sorted(c for c in STANDARD_CONFIGS if c.startswith("SBS-FCU-"))
    print(f"FCU standard configs found: {len(fcu_ids)} -> {fcu_ids}\n")

    total_fail = 0
    for cid in fcu_ids:
        spec = STANDARD_CONFIGS[cid]
        fam = spec.get("family", "")
        mods = spec["modules"]
        ctrl = spec.get("controller", "auto")
        fails = []

        try:
            cfg = assemble(mods, controller_model=ctrl, equipment_family=fam)
            inject_program_code(cfg)
        except Exception as e:  # noqa
            print(f"  {cid:14s} [{fam}]  ASSEMBLY ERROR: {e}")
            total_fail += 1
            continue

        names = defined_names(cfg)

        banned = {"CFG-OCC-CLG-SP", "CFG-OCC-HTG-SP"}
        banned_defs = banned & names
        if banned_defs:
            fails.append(f"banned point still DEFINED: {sorted(banned_defs)}")

        all_refs = set()
        for prg in cfg.programs:
            if not (prg.code and prg.code.strip()):
                fails.append(f"empty program: {prg.name}")
                continue
            if not has_line_numbers(prg.code):
                fails.append(f"program not line-numbered: {prg.name}")
            all_refs |= prog_refs(prg.code)

        banned_refs = banned & all_refs
        if banned_refs:
            fails.append(f"banned point still REFERENCED: {sorted(banned_refs)}")

        unresolved = sorted(r for r in all_refs if r not in names)
        if unresolved:
            fails.append(f"unresolved point refs: {unresolved}")

        for req in ("RMT-SP", "CFG-RMT-SP-DB"):
            if req not in names:
                fails.append(f"required new point missing: {req}")
            if req not in all_refs:
                fails.append(f"required new point never referenced: {req}")

        status = "OK  " if not fails else "FAIL"
        cnt = f"AI:{len(cfg.inputs)} AO/BO:{len(cfg.outputs)} AV/BV:{len(cfg.values)} LOOP:{len(cfg.loops)} PRG:{len(cfg.programs)}"
        print(f"  {cid:14s} [{fam:14s}] {status}  {cnt}")
        for f in fails:
            print(f"        - {f}")
        if fails:
            total_fail += 1

    print()
    if total_fail:
        print(f"AUDIT RESULT: FAIL — {total_fail}/{len(fcu_ids)} configs have issues")
        sys.exit(1)
    print(f"AUDIT RESULT: PASS — all {len(fcu_ids)} FCU configs assemble cleanly, "
          f"no unresolved refs, no banned setpoints, line numbers present")


if __name__ == "__main__":
    main()
