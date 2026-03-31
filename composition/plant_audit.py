#!/usr/bin/env python3
"""
SBS Composition Engine v2 — Plant Audit Tool

Enumerates all HW and CHW plant configurations, assembles each,
and checks for:
  TABLE 1: Missing point references in .bas programs
  TABLE 2: I/O row collisions
  TABLE 3: Program instance collisions
  TABLE 4: Programs with no .bas code
  TABLE 5: Assembly errors

Usage:
    cd /srv/reliable-generator-dev
    PYTHONPATH=. venv/bin/python -m composition.plant_audit [output_file]
"""

import re
import sys
from pathlib import Path
from collections import defaultdict
from composition.module_registry import hwp_assemble, chwp_assemble
from composition.hw_plant_test import merge_modules


# ──────────────────────────────────────────────────────────────────────
# Point name extraction from .bas code
# ──────────────────────────────────────────────────────────────────────

# Match {device-name}-POINTNAME allowing / inside the name (e.g. S/S, VLV-1/3)
# Point names: uppercase letters, digits, hyphens, and /
_POINT_REF_RE = re.compile(r'\{device-name\}-([A-Z0-9][A-Z0-9\-/]*[A-Z0-9/])')


def extract_point_refs(bas_code: str) -> set:
    """Extract all point name references from a .bas program.

    Handles point names containing / (e.g. BLR1-S/S, HX-VLV-1/3).
    Skips REM comment lines.
    """
    refs = set()
    for line in bas_code.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith('REM'):
            continue
        for m in _POINT_REF_RE.finditer(line):
            refs.add(m.group(1))
    return refs


# ──────────────────────────────────────────────────────────────────────
# Config enumeration — generates all HW + CHW plant parameter combos
# ──────────────────────────────────────────────────────────────────────

def generate_hw_configs():
    """Generate all HW plant parameter combinations."""
    configs = []

    for bt in ['cascade', 'full']:
        for nb in [1, 2, 3, 4]:
            # CS pumps: 1-4
            for np in [1, 2, 3, 4]:
                params = {
                    'boiler_type': bt,
                    'num_boilers': nb,
                    'pump_type': 'cs',
                    'num_pumps': np,
                }
                if bt == 'cascade':
                    params['spt_output'] = 'analog'
                    params['monitor_boiler_temps'] = False
                else:
                    params['monitor_boiler_temps'] = True
                name = f"HW {bt[:4]}-{nb}blr cs-{np}p"
                configs.append((name, params))

            # VFD pumps: 1-4
            for np in [1, 2, 3, 4]:
                params = {
                    'boiler_type': bt,
                    'num_boilers': nb,
                    'pump_type': 'vfd',
                    'num_pumps': np,
                }
                if bt == 'cascade':
                    params['spt_output'] = 'analog'
                    params['monitor_boiler_temps'] = False
                else:
                    params['monitor_boiler_temps'] = True
                name = f"HW {bt[:4]}-{nb}blr vfd-{np}p"
                configs.append((name, params))

            # Pri-sec: 1-2 primary × 1-2 secondary
            for npp in [1, 2]:
                for nps in [1, 2]:
                    params = {
                        'boiler_type': bt,
                        'num_boilers': nb,
                        'pump_type': 'pri-sec',
                        'num_primary': npp,
                        'num_secondary': nps,
                    }
                    if bt == 'cascade':
                        params['spt_output'] = 'analog'
                        params['monitor_boiler_temps'] = False
                    else:
                        params['monitor_boiler_temps'] = True
                    name = f"HW {bt[:4]}-{nb}blr ps-{npp}p{nps}s"
                    configs.append((name, params))

    # +opts configs: one cascade, one full — with iso, comb, hx, ahu, makeup
    opts_cascade = {
        'boiler_type': 'cascade', 'num_boilers': 2, 'spt_output': 'analog',
        'monitor_boiler_temps': False, 'pump_type': 'cs', 'num_pumps': 2,
        'iso_valves': True, 'comb_damper': True, 'heat_exchanger': True,
        'hx_valve_type': 'single_mod', 'ahu_integration': True, 'num_ahus': 2,
        'makeup_water': True,
    }
    configs.append(("HW casc-2blr cs-2p +opts", opts_cascade))

    opts_full = {
        'boiler_type': 'full', 'num_boilers': 3, 'monitor_boiler_temps': True,
        'pump_type': 'pri-sec', 'num_primary': 2, 'num_secondary': 2,
        'iso_valves': True, 'comb_damper': True, 'heat_exchanger': True,
        'hx_valve_type': 'third_twothird', 'ahu_integration': True, 'num_ahus': 4,
        'makeup_water': True,
    }
    configs.append(("HW full-3blr ps-2p2s +opts", opts_full))

    return configs


def generate_chw_configs():
    """Generate all CHW plant parameter combinations."""
    configs = []

    # Air cooled: chillers 1-4 × pri 1-2 × sec 1-2
    for nc in [1, 2, 3, 4]:
        for npp in [1, 2]:
            for nps in [1, 2]:
                params = {
                    'num_chillers': nc,
                    'num_pri_pumps': npp,
                    'num_sec_pumps': nps,
                    'num_dp_sensors': 2,
                }
                name = f"CHW air {nc}chlr {npp}pri {nps}sec"
                configs.append((name, params))

    # Air cooled +opts
    air_opts = {
        'num_chillers': 2, 'num_pri_pumps': 2, 'num_sec_pumps': 2,
        'num_dp_sensors': 2, 'bypass_valve': True, 'iso_valves': True,
        'ahu_integration': True, 'num_ahus': 4,
    }
    configs.append(("CHW air 2c 2p 2s +opts", air_opts))

    # Tower: chillers 1-2 × towers 1-3 × cw pumps 1-3
    for nc in [1, 2]:
        for nt in [1, 2, 3]:
            for ncw in [1, 2, 3]:
                params = {
                    'num_chillers': nc,
                    'num_pri_pumps': nc,
                    'num_sec_pumps': nc,
                    'num_dp_sensors': 2,
                    'num_cw_pumps': ncw,
                    'num_towers': nt,
                    'tower_bypass': True,
                }
                name = f"CHW twr {nc}c {nt}t {ncw}cw"
                configs.append((name, params))

    # Tower +opts: 2 and 3 chiller configs
    twr_opts_2 = {
        'num_chillers': 2, 'num_pri_pumps': 2, 'num_sec_pumps': 2,
        'num_dp_sensors': 2, 'num_cw_pumps': 2, 'num_towers': 2,
        'tower_bypass': True, 'bypass_valve': True, 'iso_valves': True,
        'ahu_integration': True, 'num_ahus': 3, 'makeup_water': True,
    }
    configs.append(("CHW twr 2c 2t 2cw +opts", twr_opts_2))

    twr_opts_3 = {
        'num_chillers': 3, 'num_pri_pumps': 3, 'num_sec_pumps': 3,
        'num_dp_sensors': 2, 'num_cw_pumps': 3, 'num_towers': 3,
        'tower_bypass': True, 'bypass_valve': True, 'iso_valves': True,
        'ahu_integration': True, 'num_ahus': 4, 'makeup_water': True,
    }
    configs.append(("CHW twr 3c 3t 3cw +opts", twr_opts_3))

    return configs


# ──────────────────────────────────────────────────────────────────────
# Audit: assemble config, load .bas, check point references
# ──────────────────────────────────────────────────────────────────────

def audit_config(name, params, is_chw=False):
    """Assemble one config and check for issues.

    Returns dict with:
        missing_refs: [(prg_name, point_name), ...]
        io_collisions: [(type, row, name1, name2), ...]
        prg_collisions: [(inst, name1, name2), ...]
        no_code_progs: [prg_name, ...]
        error: str or None
    """
    result = {
        'missing_refs': [],
        'io_collisions': [],
        'prg_collisions': [],
        'no_code_progs': [],
        'error': None,
    }

    try:
        if is_chw:
            modules = chwp_assemble(params)
            prg_dir = Path(__file__).parent / "programs" / "chw_plant"
        else:
            modules = hwp_assemble(params)
            prg_dir = Path(__file__).parent / "programs" / "hw_plant"

        merged = merge_modules(modules)
    except Exception as e:
        result['error'] = str(e)
        return result

    # Load .bas code for programs that don't have dynamic code
    for prg in merged['programs']:
        if prg.code and len(prg.code) > 50:
            continue
        bas_path = prg_dir / prg.filename
        if bas_path.exists():
            prg.code = bas_path.read_text()

    # Build alarm program
    from composition.hw_plant_test import generate_alarm_bas
    from composition.models import ProgramDef
    alarm_code = generate_alarm_bas(merged)
    if alarm_code:
        alarm_prg = ProgramDef(50, "ALARMS-PRG", "PRG-ALARMS.bas", alarm_code, True,
                               "Auto-generated alarm definitions", "alarm-gen", exec_order=50)
        merged['programs'].append(alarm_prg)

    # Collect all defined point names
    all_points = set()
    for pt in merged['inputs']:
        all_points.add(pt.name)
    for pt in merged['outputs']:
        all_points.add(pt.name)
    for pt in merged['values']:
        all_points.add(pt.name)

    # Also add loop names (programs reference loop output via loop name)
    for lp in merged['loops']:
        all_points.add(lp.name)

    # Check point references in each .bas program
    for prg in merged['programs']:
        if not prg.code or len(prg.code) < 10:
            result['no_code_progs'].append(prg.name)
            continue

        refs = extract_point_refs(prg.code)
        for ref in sorted(refs):
            if ref not in all_points:
                result['missing_refs'].append((prg.name, ref))

    # Check I/O row collisions
    input_rows = {}
    for pt in merged['inputs']:
        if pt.row in input_rows:
            existing = input_rows[pt.row]
            if existing.name != pt.name:
                result['io_collisions'].append(('INPUT', pt.row, existing.name, pt.name))
        else:
            input_rows[pt.row] = pt

    output_rows = {}
    for pt in merged['outputs']:
        if pt.row in output_rows:
            existing = output_rows[pt.row]
            if existing.name != pt.name:
                result['io_collisions'].append(('OUTPUT', pt.row, existing.name, pt.name))
        else:
            output_rows[pt.row] = pt

    # Check program instance collisions
    prg_insts = {}
    for prg in merged['programs']:
        if prg.instance in prg_insts:
            existing = prg_insts[prg.instance]
            if existing.name != prg.name:
                result['prg_collisions'].append((prg.instance, existing.name, prg.name))
        else:
            prg_insts[prg.instance] = prg

    return result


# ──────────────────────────────────────────────────────────────────────
# Main — run all configs and produce report
# ──────────────────────────────────────────────────────────────────────

def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else '/srv/dfa/drops/plant-audit.txt'

    hw_configs = generate_hw_configs()
    chw_configs = generate_chw_configs()
    total = len(hw_configs) + len(chw_configs)

    print(f"Running {len(hw_configs)} HW configs + {len(chw_configs)} CHW configs...")

    # Aggregate results across all configs
    # key = (prg_name, point_name) -> set of config names
    missing_by_ref = defaultdict(set)
    io_collisions_by_key = defaultdict(set)
    prg_collisions_by_key = defaultdict(set)
    no_code_by_prg = defaultdict(set)
    errors = {}
    ok_count = 0
    err_count = 0

    all_configs = [(name, params, False) for name, params in hw_configs] + \
                  [(name, params, True) for name, params in chw_configs]

    for i, (name, params, is_chw) in enumerate(all_configs):
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{total}...")

        result = audit_config(name, params, is_chw)

        if result['error']:
            errors[name] = result['error']
            err_count += 1
            continue
        ok_count += 1

        for prg_name, point_name in result['missing_refs']:
            missing_by_ref[(prg_name, point_name)].add(name)

        for typ, row, name1, name2 in result['io_collisions']:
            io_collisions_by_key[(typ, row, name1, name2)].add(name)

        for inst, name1, name2 in result['prg_collisions']:
            prg_collisions_by_key[(inst, name1, name2)].add(name)

        for prg_name in result['no_code_progs']:
            no_code_by_prg[prg_name].add(name)

    # ── Build report ──
    lines = [f"Running {len(hw_configs)} HW configs + {len(chw_configs)} CHW configs...", ""]

    # TABLE 1: Missing point references
    lines.append("=" * 100)
    lines.append("TABLE 1: MISSING POINT REFERENCES — .bas file × point name × configs affected")
    lines.append("=" * 100)
    lines.append("")

    sorted_missing = sorted(missing_by_ref.keys())
    for prg_name, point_name in sorted_missing:
        cfgs = missing_by_ref[(prg_name, point_name)]
        cfg_list = sorted(cfgs)
        if len(cfg_list) == total:
            cfg_str = "ALL CONFIGS"
        elif len(cfg_list) > 6:
            cfg_str = ", ".join(cfg_list[:6]) + "..."
        else:
            cfg_str = ", ".join(cfg_list)
        lines.append(f"  {prg_name:<40s} {point_name:<30s} {len(cfgs)}/{total}: {cfg_str}")

    # TABLE 2: I/O row collisions
    lines.append("")
    lines.append("=" * 100)
    lines.append("TABLE 2: I/O ROW COLLISIONS")
    lines.append("=" * 100)
    lines.append("")

    sorted_io = sorted(io_collisions_by_key.keys(), key=lambda x: (x[0], x[1]))
    for typ, row, name1, name2 in sorted_io:
        cfgs = io_collisions_by_key[(typ, row, name1, name2)]
        cfg_list = sorted(cfgs)
        if len(cfg_list) > 6:
            cfg_str = ", ".join(cfg_list[:6]) + "..."
        else:
            cfg_str = ", ".join(cfg_list)
        lines.append(f"  {typ} row {row:3d}: {name1:<25s} vs {name2:<25s} in {len(cfgs)} configs: {cfg_str}")

    # TABLE 3: Program instance collisions
    lines.append("")
    lines.append("=" * 100)
    lines.append("TABLE 3: PROGRAM INSTANCE COLLISIONS")
    lines.append("=" * 100)
    lines.append("")

    if prg_collisions_by_key:
        for (inst, name1, name2), cfgs in sorted(prg_collisions_by_key.items()):
            cfg_list = sorted(cfgs)
            cfg_str = ", ".join(cfg_list[:6])
            if len(cfg_list) > 6:
                cfg_str += "..."
            lines.append(f"  PRG inst {inst:3d}: {name1:<40s} vs {name2:<25s} in {len(cfgs)} configs: {cfg_str}")
    else:
        lines.append("  None.")

    # TABLE 4: Programs with no code
    lines.append("")
    lines.append("=" * 100)
    lines.append("TABLE 4: PROGRAMS WITH NO CODE (no .bas file found)")
    lines.append("=" * 100)
    lines.append("")

    if no_code_by_prg:
        for prg_name in sorted(no_code_by_prg.keys()):
            cfgs = no_code_by_prg[prg_name]
            cfg_list = sorted(cfgs)
            if len(cfg_list) > 6:
                cfg_str = ", ".join(cfg_list[:6]) + "..."
            else:
                cfg_str = ", ".join(cfg_list)
            lines.append(f"  {prg_name:<40s} in {len(cfgs)} configs: {cfg_str}")
    else:
        lines.append("  None.")

    # TABLE 5: Assembly errors
    lines.append("")
    lines.append("=" * 100)
    lines.append("TABLE 5: ASSEMBLY ERRORS")
    lines.append("=" * 100)
    lines.append("")

    if errors:
        for name, err in sorted(errors.items()):
            lines.append(f"  {name}: {err}")
    else:
        lines.append("  None.")

    # SUMMARY
    lines.append("")
    lines.append("=" * 100)
    lines.append("SUMMARY")
    lines.append("=" * 100)
    lines.append(f"  Total configs attempted:  {total}")
    lines.append(f"  Assembled OK:             {ok_count}")
    lines.append(f"  Assembly errors:          {err_count}")
    lines.append(f"  Unique missing point refs: {len(missing_by_ref)}")
    lines.append(f"  Unique I/O collisions:    {len(io_collisions_by_key)}")
    lines.append(f"  Unique PRG collisions:    {len(prg_collisions_by_key)}")
    lines.append(f"  Programs with no code:    {len(no_code_by_prg)}")

    report = "\n".join(lines) + "\n"

    Path(output_file).write_text(report)
    print(f"\nReport written to {output_file}")
    print(f"\n{'='*60}")
    print(f"  RESULTS:")
    print(f"  Configs: {ok_count}/{total} OK, {err_count} errors")
    print(f"  Missing point refs: {len(missing_by_ref)}")
    print(f"  I/O collisions: {len(io_collisions_by_key)}")
    print(f"  PRG collisions: {len(prg_collisions_by_key)}")
    print(f"  Programs without code: {len(no_code_by_prg)}")
    print(f"{'='*60}")

    return len(missing_by_ref)


if __name__ == '__main__':
    main()
