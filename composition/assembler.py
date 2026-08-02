"""
SBS Composition Engine v2 — Assembler

Takes a list of module IDs and assembles a complete ControllerConfig:
1. Resolves dependencies (adds required modules)
2. Checks for conflicts
3. Merges all points (inputs, outputs, values, loops, tables, programs, etc.)
4. Applies fixed I/O row assignments (never fills gaps)
5. Determines controller model + expansion boards needed
6. Generates trend logs for all points
7. Assembles SOO document from module paragraphs
"""

import copy
import json
from pathlib import Path
from composition.models import ControllerConfig, TrendDef, ProgramDef
from composition.module_registry import get_module, get_core_modules, FAMILY_CORES

# All core module IDs across all families — used to strip wrong-family cores
_ALL_CORES = set()
for _cores in FAMILY_CORES.values():
    _ALL_CORES.update(_cores)


def assemble(module_ids: list, device_name: str = "{device-name}",
             parent_name: str = "{parent}", equipment_family: str = "AHU-VAV",
             controller_model: str = "auto") -> ControllerConfig:
    """
    Assemble a complete controller configuration from selected modules.

    Args:
        module_ids: List of module IDs to include
        device_name: Device name template (default: {device-name})
        parent_name: Parent device name template (default: {parent})
        equipment_family: Equipment family for row map lookup

    Returns:
        ControllerConfig with all points merged and controller selected
    """

    # Step 1: Add core modules and enforce family isolation.
    # Strip any core modules that don't belong to this equipment family
    # (the frontend or caller may have sent wrong-family cores).
    allowed_cores = set(get_core_modules(equipment_family))
    all_ids = set()
    for mid in module_ids:
        if mid in _ALL_CORES and mid not in allowed_cores:
            continue  # wrong-family core — strip it
        all_ids.add(mid)
    for cid in allowed_cores:
        all_ids.add(cid)

    # Auto-add dsp-ctrl when fan-sf-vfd is selected on families that need DSP
    _DSP_WITH_VFD_FAMILIES = {'DOAS', 'DD-AHU', 'MZ-AHU'}
    if 'fan-sf-vfd' in all_ids and equipment_family in _DSP_WITH_VFD_FAMILIES:
        all_ids.add('dsp-ctrl')

    # Iteratively resolve dependencies
    resolved = set()
    to_resolve = list(all_ids)
    while to_resolve:
        mid = to_resolve.pop(0)
        if mid in resolved:
            continue
        mod = get_module(mid)
        resolved.add(mid)
        for req in mod.requires:
            if req not in resolved:
                to_resolve.append(req)
                all_ids.add(req)

    # Step 2: Check for conflicts
    errors = []
    warnings = []
    modules = {mid: get_module(mid) for mid in all_ids}
    for mid, mod in modules.items():
        for conflict in mod.conflicts:
            if conflict in all_ids:
                errors.append(f"Module '{mid}' conflicts with '{conflict}'")
    if errors:
        raise ValueError("Module conflicts detected:\n" + "\n".join(errors))

    # Step 3: Merge all points
    config = ControllerConfig(
        device_name=device_name,
        parent_name=parent_name,
        equipment_family=equipment_family,
        selected_modules=sorted(all_ids),
    )

    # Track by row/instance AND by name to prevent duplicates
    input_rows = {}   # row -> InputPoint
    input_names = set()  # mnemonic names already defined
    output_rows = {}  # row -> OutputPoint
    output_names = set()
    value_instances = {}  # instance -> ValuePoint
    value_names = set()
    loop_instances = {}
    table_instances = {}
    array_instances = {}
    program_instances = {}
    schedule_instances = {}
    system_group_names = {}

    # Stub-fallback modules are processed AFTER all real modules so their
    # points only fill gaps left by real modules. Within each bucket we keep
    # the existing alphabetical order so behavior is unchanged for non-stubs.
    def _mod_sort_key(mid):
        return (1 if getattr(modules[mid], "is_stub_fallback", False) else 0, mid)

    for mid in sorted(all_ids, key=_mod_sort_key):
        mod = modules[mid]
        is_stub = getattr(mod, "is_stub_fallback", False)

        # Deep-copy all module points before mutating (.row, .module, .instance)
        # to prevent corrupting the cached module singleton across requests.
        mod_inputs = copy.deepcopy(mod.inputs)
        mod_outputs = copy.deepcopy(mod.outputs)
        mod_values = copy.deepcopy(mod.values)
        mod_loops = copy.deepcopy(mod.loops)
        mod_tables = copy.deepcopy(mod.tables)
        mod_arrays = copy.deepcopy(mod.arrays)
        mod_programs = copy.deepcopy(mod.programs)
        mod_schedules = copy.deepcopy(mod.schedules)
        mod_system_groups = copy.deepcopy(mod.system_groups)

        for pt in mod_inputs:
            if pt.name in input_names:
                continue  # same mnemonic already exists — skip entirely
            # Stub fallback: never add an input whose name is already provided
            # by another module under any category (input/output/value).
            if is_stub and (pt.name in output_names or pt.name in value_names):
                continue
            if pt.row not in input_rows:
                if pt.module != "FACTORY": pt.module = mid
                input_rows[pt.row] = pt
                input_names.add(pt.name)
            else:
                existing = input_rows[pt.row]
                next_row = max(input_rows.keys()) + 1
                warnings.append(
                    f"I/O CONFLICT: Input row {pt.row} — '{existing.name}' ({existing.module}) "
                    f"and '{pt.name}' ({mid}). Moved '{pt.name}' to row {next_row}."
                )
                pt.row = next_row
                if pt.module != "FACTORY": pt.module = mid
                input_rows[next_row] = pt
                input_names.add(pt.name)

        for pt in mod_outputs:
            if pt.name in output_names:
                continue  # same mnemonic already exists — skip entirely
            if is_stub and (pt.name in input_names or pt.name in value_names):
                continue
            if pt.row not in output_rows:
                if pt.module != "FACTORY": pt.module = mid
                output_rows[pt.row] = pt
                output_names.add(pt.name)
            else:
                existing = output_rows[pt.row]
                next_row = max(output_rows.keys()) + 1
                warnings.append(
                    f"I/O CONFLICT: Output row {pt.row} — '{existing.name}' ({existing.module}) "
                    f"and '{pt.name}' ({mid}). Moved '{pt.name}' to row {next_row}."
                )
                pt.row = next_row
                if pt.module != "FACTORY": pt.module = mid
                output_rows[next_row] = pt
                output_names.add(pt.name)

        for pt in mod_values:
            if pt.name in value_names:
                continue  # same mnemonic already exists — skip entirely
            # Stub fallback: never add a value whose name is already provided
            # as an input or output by another module.
            if is_stub and (pt.name in input_names or pt.name in output_names):
                continue
            # Dedup key must include point_type — BACnet AV20, BV20 and MV20
            # are independent objects, so they must NOT collide.
            key = (pt.point_type, pt.instance)
            if key not in value_instances:
                if pt.module != "FACTORY": pt.module = mid
                value_instances[key] = pt
                value_names.add(pt.name)

        for lp in mod_loops:
            if lp.instance not in loop_instances:
                lp.module = mid
                loop_instances[lp.instance] = lp

        for tbl in mod_tables:
            if tbl.instance not in table_instances:
                tbl.module = mid
                table_instances[tbl.instance] = tbl

        for arr in mod_arrays:
            if arr.instance not in array_instances:
                arr.module = mid
                array_instances[arr.instance] = arr

        for prg in mod_programs:
            if prg.instance not in program_instances:
                prg.module = mid
                program_instances[prg.instance] = prg
            else:
                existing = program_instances[prg.instance]
                # ERROR if duplicate is from the SAME module (config error, not intentional variant)
                # WARN if duplicate is from DIFFERENT modules (intentional variant selection, keeping first)
                if existing.module == mid:
                    raise ValueError(
                        f"Configuration error in family {family_id}: "
                        f"Duplicate program instance {prg.instance} within same module {mid}. "
                        f"Programs: '{existing.name}' and '{prg.name}'. "
                        f"Each program in a module must have a unique instance number. "
                        f"This would silently drop '{prg.name}' from generated output."
                    )
                else:
                    # Different modules: this is intentional variant selection (e.g., HW vs ELEC heating)
                    # Silently keep the first variant that was selected
                    pass

        for sch in mod_schedules:
            if sch.instance not in schedule_instances:
                sch.module = mid
                schedule_instances[sch.instance] = sch

        for sg in mod_system_groups:
            if sg.name not in system_group_names:
                sg.module = mid
                system_group_names[sg.name] = sg

    # Sort by row/instance number
    config.inputs = [input_rows[r] for r in sorted(input_rows.keys())]
    config.outputs = [output_rows[r] for r in sorted(output_rows.keys())]
    # Values are keyed by (point_type, instance) — sort by type priority then instance
    _val_type_order = {"AV": 0, "BV": 1, "MV": 2}
    config.values = [
        value_instances[k] for k in sorted(
            value_instances.keys(),
            key=lambda k: (_val_type_order.get(k[0], 9), k[1]),
        )
    ]
    config.loops = [loop_instances[i] for i in sorted(loop_instances.keys())]
    config.tables = [table_instances[i] for i in sorted(table_instances.keys())]
    config.arrays = [array_instances[i] for i in sorted(array_instances.keys())]
    config.programs = [program_instances[i] for i in sorted(program_instances.keys())]
    config.schedules = [schedule_instances[i] for i in sorted(schedule_instances.keys())]
    config.system_groups = list(system_group_names.values())

    # Step 3a2: Flag programs that reference {parent}
    for prg in config.programs:
        if '{parent}' in prg.code:
            note = 'Requires parent device ID at commissioning'
            if note not in prg.description:
                prg.description = (prg.description + ' — ' + note).lstrip(' — ') if prg.description else note

    # Step 3b: Check for orphan point references
    all_point_names = set()
    for pt in config.inputs:
        all_point_names.add(pt.name)
    for pt in config.outputs:
        all_point_names.add(pt.name)
    for pt in config.values:
        all_point_names.add(pt.name)

    for lp in config.loops:
        if lp.input_ref and lp.input_ref not in all_point_names:
            warnings.append(
                f"ORPHAN REF: Loop {lp.instance} ({lp.name}) input '{lp.input_ref}' "
                f"has no matching point in Inputs or Values."
            )
        if lp.setpoint_ref and lp.setpoint_ref not in all_point_names:
            warnings.append(
                f"ORPHAN REF: Loop {lp.instance} ({lp.name}) setpoint '{lp.setpoint_ref}' "
                f"has no matching point in Values."
            )
        if lp.output_ref and lp.output_ref not in all_point_names:
            warnings.append(
                f"ORPHAN REF: Loop {lp.instance} ({lp.name}) output '{lp.output_ref}' "
                f"has no matching point in Outputs."
            )

    # Step 3b2: Warn on point names that collide with CBAS reserved words.
    # CBAS resolves bare identifiers against the function table first; a point
    # name like MIN-FLO can be parsed as MIN(-FLO) and break compilation.
    _CBAS_RESERVED = {
        "IF","THEN","ELSE","AND","OR","NOT","REM","FOR","NEXT",
        "GOTO","GOSUB","RETURN","END","STOP","LET","DIM",
        "INPUT","PRINT","READ","DATA","RESTORE","ON","STEP","TO","MOD",
        "ABS","INT","SQR","LOG","EXP","SIN","COS","TAN","ATN","SGN",
        "FIX","FRAC","MAX","MIN","AVG","SUM","ROUND","FLOOR","CEIL",
        "LIMIT","SLIDE","SWITCH","RAMP","ENTHALPY",
    }
    def _reserved_hit(name: str):
        u = name.upper()
        if u in _CBAS_RESERVED:
            return u
        for rw in _CBAS_RESERVED:
            if u.startswith(rw + "-"):
                return rw
            if u.startswith(rw) and len(u) > len(rw) and u[len(rw)].isdigit():
                return rw
        return None
    def _check_reserved(name: str, kind: str):
        rw = _reserved_hit(name)
        if rw:
            warnings.append(f"RESERVED WORD: {kind} '{name}' starts with CBAS reserved word '{rw}'")
    for pt in config.inputs:    _check_reserved(pt.name, "Input")
    for pt in config.outputs:   _check_reserved(pt.name, "Output")
    for v  in config.values:    _check_reserved(v.name,  "Value")
    for lp in config.loops:     _check_reserved(lp.name, "Loop")
    for ar in config.arrays:    _check_reserved(ar.name, "Array")
    for tb in config.tables:    _check_reserved(tb.name, "Table")
    for sc in config.schedules: _check_reserved(sc.name, "Schedule")

    # Step 3c: Generate alarm program and add to programs list
    from composition.alarm_gen import generate_alarm_bas
    alarm_code = generate_alarm_bas(config)
    if alarm_code:
        # Use instance after all other programs
        alarm_inst = max((p.instance for p in config.programs), default=0) + 1
        alarm_prg = ProgramDef(
            alarm_inst, "ALARMS-PRG", "PRG-ALARMS.bas", alarm_code, True,
            "Auto-generated alarm definitions",
            exec_order=alarm_inst,
        )
        alarm_prg.module = "core"
        config.programs.append(alarm_prg)
        program_instances[alarm_inst] = alarm_prg

    # Step 4: Generate trend logs for all points
    config.trends = _generate_trends(config)

    # Step 5: Controller selection
    # Exclude factory reserved points from controller selection — they come from blank
    user_input_rows = {r: p for r, p in input_rows.items() if p.module != "FACTORY"}
    user_output_rows = {r: p for r, p in output_rows.items() if p.module != "FACTORY"}
    config.highest_input_row = max(user_input_rows.keys()) if user_input_rows else 0
    config.highest_output_row = max(user_output_rows.keys()) if user_output_rows else 0
    # Display max includes factory points so UI shows all rows
    config.display_max_input_row = max(input_rows.keys()) if input_rows else 0
    config.display_max_output_row = max(output_rows.keys()) if output_rows else 0
    _select_controller(config, controller_model)

    # Step 6: Assemble SOO document
    config.soo_document = _assemble_soo(modules, all_ids)

    # Attach warnings
    config.warnings = warnings

    return config


def _generate_trends(config: ControllerConfig) -> list:
    """Generate STL trend logs for all points — standard SBS practice.
    Names truncated to 28 chars (30 max minus '-STL' suffix handled separately).
    Duplicates get a numeric suffix.
    """
    trends = []
    stl_num = 1
    used_names = set()

    # Abbreviations to shorten trend names
    _abbrev = [
        ('INITIAL', 'INIT'), ('LOCKOUT', 'LKO'), ('PRESTART', 'PRST'),
        ('RUNTIME', 'RT'), ('DEFROST', 'DFST'), ('SAFETIES', 'SFTY'),
        ('SAFETY', 'SFTY'), ('FREEZE', 'FRZ'), ('SETPOINT', 'SP'),
        ('INTERVAL', 'INTV'), ('INTRVL', 'INTV'), ('COMMAND', 'CMD'),
        ('STATUS', 'STS'), ('POSITION', 'POS'), ('TEMPERATURE', 'TMP'),
        ('DISCHARGE', 'DSCH'), ('OCCUPIED', 'OCC'), ('UNOCCUPIED', 'UNOCC'),
        ('ECONOMIZER', 'ECON'), ('VENTILATION', 'VENT'), ('BYPASS', 'BYP'),
        ('-MODE-FIRST-ON', '-1ST-ON'), ('-FIRST-START', '-1ST-ST'),
        ('-FIRST-ON', '-1ST-ON'),
    ]

    def _make_stl_name(base_name):
        """Create unique short trend name. Use -T suffix instead of -STL."""
        name = base_name
        # Apply abbreviations to shorten
        for long, short in _abbrev:
            name = name.replace(long, short)
        stl_name = f"{name}-T"
        # Hard cap at 16 chars (leaves room for {device-name}- prefix in 30-char limit)
        if len(stl_name) > 16:
            short = name[:14].rstrip('-')  # don't end on a dash
            stl_name = f"{short}-T"
        # Deduplicate
        if stl_name in used_names:
            for suffix in range(2, 100):
                candidate = f"{stl_name}{suffix}"
                if candidate not in used_names:
                    stl_name = candidate
                    break
        used_names.add(stl_name)
        return stl_name

    # Polled trends for physical AI sensors (15-minute interval)
    for inp in config.inputs:
        if inp.point_type == "AI":
            trends.append(TrendDef(
                instance=stl_num,
                name=_make_stl_name(inp.name),
                monitored_point=inp.name,
                trend_type="polled",
                interval="00:15:00",
            ))
            stl_num += 1

    # COV trends for BI status points
    for inp in config.inputs:
        if inp.point_type == "BI":
            trends.append(TrendDef(
                instance=stl_num,
                name=_make_stl_name(inp.name),
                monitored_point=inp.name,
                trend_type="cov",
                cov_delta=0.2,
            ))
            stl_num += 1

    # COV trends for all outputs
    for out in config.outputs:
        trends.append(TrendDef(
            instance=stl_num,
            name=_make_stl_name(out.name),
            monitored_point=out.name,
            trend_type="cov",
            cov_delta=0.2,
        ))
        stl_num += 1

    # COV trends for key AV/BV/MV values (modes, setpoints, status)
    for val in config.values:
        trends.append(TrendDef(
            instance=stl_num,
            name=_make_stl_name(val.name),
            monitored_point=val.name,
            trend_type="cov",
            cov_delta=0.2,
        ))
        stl_num += 1

    return trends


CONTROLLER_SPECS = {
    "MPS":     {"base_in": 12, "base_out": 8,  "max_exp": 7, "family": "MACH-ProSys"},
    "MPWS":    {"base_in": 12, "base_out": 8,  "max_exp": 7, "family": "MACH-ProWebSys"},
    "MPV-LCD": {"base_in": 12, "base_out": 8,  "max_exp": 7, "family": "MACH-ProView LCD"},
    "MP2":     {"base_in": 12, "base_out": 8,  "max_exp": 3, "family": "MACH-Pro2"},
    "MP1":     {"base_in": 12, "base_out": 8,  "max_exp": 0, "family": "MACH-Pro1"},
    "MPC":     {"base_in": 0,  "base_out": 0,  "max_exp": 8, "family": "MACH-ProCom"},
    "MPWC":    {"base_in": 0,  "base_out": 0,  "max_exp": 8, "family": "MACH-ProWebCom"},
    "MPA-36":  {"base_in": 3,  "base_out": 6,  "max_exp": 0, "family": "MACH-ProAir"},
    "MPA-35":  {"base_in": 3,  "base_out": 5,  "max_exp": 0, "family": "MACH-ProAir"},
    "MPA-34":  {"base_in": 3,  "base_out": 4,  "max_exp": 0, "family": "MACH-ProAir"},
    "MPA-33":  {"base_in": 3,  "base_out": 3,  "max_exp": 0, "family": "MACH-ProAir"},
    "MPZ-88":  {"base_in": 8,  "base_out": 8,  "max_exp": 0, "family": "MACH-ProZone"},
    "MPZ-44":  {"base_in": 4,  "base_out": 4,  "max_exp": 0, "family": "MACH-ProZone"},
    # RC-FLEXair VAV controllers — factory AI4/AI5/BI6/BO8 reserved
    "RCFA-12": {"base_in": 1,  "base_out": 1,  "max_exp": 0, "family": "RC-FLEXair"},
    "RCFA-34": {"base_in": 3,  "base_out": 4,  "max_exp": 0, "family": "RC-FLEXair"},
    "RCFA-35": {"base_in": 3,  "base_out": 5,  "max_exp": 0, "family": "RC-FLEXair"},
    "RCFA-36": {"base_in": 3,  "base_out": 6,  "max_exp": 0, "family": "RC-FLEXair"},
}


def _select_controller(config: ControllerConfig, model_override: str = "auto"):
    """
    Select controller model and expansion boards based on highest occupied rows.
    Rule: row number = terminal number. Never fill gaps.

    model_override: "auto" for automatic selection, or a specific model ID
    """
    hi_in = config.highest_input_row
    hi_out = config.highest_output_row
    exp_in_per = 12  # MPP-IO-U inputs
    exp_out_per = 8  # MPP-IO-U outputs

    if model_override and model_override != "auto" and model_override in CONTROLLER_SPECS:
        # User selected a specific controller
        spec = CONTROLLER_SPECS[model_override]
        base_in = spec["base_in"]
        base_out = spec["base_out"]
        max_exp = spec["max_exp"]

        if max_exp > 0:
            exp_for_in = max(0, (hi_in - base_in + exp_in_per - 1) // exp_in_per) if hi_in > base_in else 0
            exp_for_out = max(0, (hi_out - base_out + exp_out_per - 1) // exp_out_per) if hi_out > base_out else 0
            expansion_count = max(exp_for_in, exp_for_out)
            if expansion_count > max_exp:
                expansion_count = max_exp  # Cap at max — user chose this model
        else:
            expansion_count = 0

        config.controller_model = model_override
        config.expansion_count = expansion_count
        config.expansion_model = "MPP-IO-U" if expansion_count > 0 else ""
        return

    # Auto-select: families with a fixed MACH-ProZone controller.
    # RHC (duct reheat coil) is always MPZ-44. RAD (radiant heater) uses
    # MPZ-44 for 1-4 heaters (SBS-RAD-901..904) and MPZ-88 for 5-8 (905..908).
    fam = config.equipment_family
    fixed_model = None
    if fam == "SBS-RHC-801":
        fixed_model = "MPZ-44"
    elif fam.startswith("SBS-RAD-90"):
        try:
            n = int(fam[len("SBS-RAD-90"):])  # heater count: SBS-RAD-90N -> N
            fixed_model = "MPZ-44" if n <= 4 else "MPZ-88"
        except (ValueError, IndexError):
            fixed_model = "MPZ-88"
    if fixed_model and fixed_model in CONTROLLER_SPECS:
        spec = CONTROLLER_SPECS[fixed_model]
        max_exp = spec["max_exp"]
        if max_exp > 0:
            exp_for_in = max(0, (hi_in - spec["base_in"] + exp_in_per - 1) // exp_in_per) if hi_in > spec["base_in"] else 0
            exp_for_out = max(0, (hi_out - spec["base_out"] + exp_out_per - 1) // exp_out_per) if hi_out > spec["base_out"] else 0
            expansion_count = min(max(exp_for_in, exp_for_out), max_exp)
        else:
            expansion_count = 0
        config.controller_model = fixed_model
        config.expansion_count = expansion_count
        config.expansion_model = "MPP-IO-U" if expansion_count > 0 else ""
        return

    # Auto-select: VAV terminal unit families use RC-FLEXair
    # VAV-AHU is an AHU family (not a terminal unit) — exclude it
    _VAV_TERMINAL_FAMILIES = ("VAV-SD-", "VAV-PF-", "VAV-SF-", "VAV-DD-")
    if config.equipment_family.startswith(_VAV_TERMINAL_FAMILIES):
        # Check if any AO outputs exist — RCFA-12 has no AO
        has_ao = any(o.point_type == "AO" for o in config.outputs)
        # Check if any reheat module present — force RCFA-34 minimum
        # Reheat variants almost always get upgraded, need room for expansion
        has_reheat = any(m for m in config.selected_modules if 'rh-' in m)
        # Pick smallest RCFA that fits the IO count
        for model in ["RCFA-12", "RCFA-34", "RCFA-35", "RCFA-36"]:
            # RCFA-12 has 1 AI + 1 BO only — skip if AO needed or reheat present
            if model == "RCFA-12" and (has_ao or has_reheat):
                continue
            spec = CONTROLLER_SPECS[model]
            if hi_in <= spec["base_in"] and hi_out <= spec["base_out"]:
                config.controller_model = model
                config.expansion_count = 0
                config.expansion_model = ""
                return
        # Fallback to largest RCFA
        config.controller_model = "RCFA-36"
        config.expansion_count = 0
        config.expansion_model = ""
        return

    # Auto-select: prefer MPS family for AHU
    for model in ["MPS", "MPWS", "MP2"]:
        spec = CONTROLLER_SPECS[model]
        base_in = spec["base_in"]
        base_out = spec["base_out"]
        max_exp = spec["max_exp"]

        exp_for_in = max(0, (hi_in - base_in + exp_in_per - 1) // exp_in_per) if hi_in > base_in else 0
        exp_for_out = max(0, (hi_out - base_out + exp_out_per - 1) // exp_out_per) if hi_out > base_out else 0
        expansion_count = max(exp_for_in, exp_for_out)

        if expansion_count <= max_exp:
            config.controller_model = model
            config.expansion_count = expansion_count
            config.expansion_model = "MPP-IO-U" if expansion_count > 0 else ""
            return

    # Fallback to MPS with max expansion
    config.controller_model = "MPS"
    config.expansion_count = 7
    config.expansion_model = "MPP-IO-U"


def _assemble_soo(modules: dict, module_ids: set) -> str:
    """Assemble SOO document from module paragraphs in logical order."""

    # Define section order
    section_order = [
        ("GENERAL", ["core"]),
        ("SUPPLY FAN", ["fan-sf-vfd", "fan-sf-cs", "fan-sf-2spd"]),
        ("RETURN/EXHAUST FAN", ["fan-rf-vfd", "fan-rf-cs", "fan-ef-vfd", "fan-ef-cs",
                                 "fan-rlf-vfd", "fan-rlf-cs"]),
        ("ECONOMIZER", ["econ-db", "econ-enth", "econ-diff", "econ-diff-db"]),
        ("VENTILATION", ["vent-fix", "vent-ams", "dcv-co2", "dcv-occ", "vent-100"]),
        ("ENERGY RECOVERY", ["erw"]),
        ("COOLING", ["clg-chw", "clg-dx", "clg-dx-2", "clg-dx-vfd"]),
        ("HEATING", ["htg-hw", "htg-elec", "htg-elec-2", "htg-elec-3",
                      "htg-elec-scr", "htg-gas", "htg-gas-mod"]),
        ("PREHEAT", ["ph-hw", "ph-elec", "ph-glycol"]),
        ("HUMIDITY CONTROL", ["hum-stm", "hum-elec", "hum-ultra", "dehum-sc"]),
        ("OPTIMUM START", ["opt-start"]),
        ("SAFETY", ["safe-freeze", "safe-smoke", "safe-hi-static", "safe-filter",
                     "safe-filter-oa", "safe-filter-final", "safe-filter-ea",
                     "safe-fire-sd", "safe-cond-ovf", "safe-freeze-dp"]),
    ]

    lines = [
        "SEQUENCE OF OPERATION",
        "=" * 60,
        "",
        "Generated by SBS Composition Engine v2",
        "",
    ]

    for section_name, possible_ids in section_order:
        active = [mid for mid in possible_ids if mid in module_ids]
        if not active:
            continue

        lines.append(f"\n{section_name}")
        lines.append("-" * len(section_name))
        for mid in active:
            mod = modules[mid]
            if mod.soo_paragraph:
                lines.append(mod.soo_paragraph.strip())
                lines.append("")

    return "\n".join(lines)
