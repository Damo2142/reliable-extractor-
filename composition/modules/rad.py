"""
SBS-RAD-901..908 — Standalone Radiant Heater Modules

A standalone controller driving 1-8 radiant heating valves. Controller is
auto-selected by heater count (handled in assembler._select_controller):
  1-4 heaters -> MACH-ProZone 44 (MPZ-44)
  5-8 heaters -> MACH-ProZone 88 (MPZ-88)

Three control modes (mutually exclusive):
  Mode A — individual hard-wired sensor + independent loop + setpoint per heater
  Mode B — one shared sensor / one loop driving all valves to the same position
  Mode C — outdoor reset only, no space sensor (valve position = SLIDE of OAT)

Valve options per heater (same across all families):
  mod — modulating AO per heater (RAD-N-VLV)
  flt — floating point per heater (RAD-N-OPEN/RAD-N-CLOSE BOs, RAD-N-POS AV,
        RAD-N-FLOAT-SYNC BV), CBAS FLOAT() with POWER-LOSS sync trigger

Config points (all modes, in rad-core):
  CFG-RAD-ENABLE-OAT = 50 deg.F  (outdoor enable / reset cutoff)
  CFG-RAD-MIN-POS    = 0%        (minimum valve position)

The heaters module is built per-family by build_rad_heaters(num, mode, valve, sensor).
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, SystemGroupDef
)


_PRG01_OAT_ENABLE = """\
REM --- OAT-ENABLE ---
REM Outdoor enable: disable radiant above the enable temperature.
REM
IF OAT > CFG-RAD-ENABLE-OAT THEN RAD-ENABLE = 0 ELSE RAD-ENABLE = 1
"""


def build_rad_core():
    """Radiant heater core — OAT sensor, enable logic, shared config."""
    return Module(
        id="rad-core",
        name="Radiant Heater Core",
        category="core",
        description="Standalone radiant heater base: OAT sensor, outdoor enable, shared config",
        is_core=True,

        inputs=[
            InputPoint(1, "OAT", "AI", "10K -40 ->250", "Outside Air Temperature", "deg.F"),
        ],

        values=[
            ValuePoint(1, "RAD-ALL-POS",        "AV", 0.0,  "Radiant Valve Position (shared)",  "%"),
            ValuePoint(2, "CFG-RAD-ENABLE-OAT", "AV", 50.0, "Outdoor Enable / Reset Cutoff",    "deg.F"),
            ValuePoint(3, "CFG-RAD-MIN-POS",    "AV", 0.0,  "Minimum Valve Position",           "%"),
            ValuePoint(1, "RAD-ENABLE",         "BV", True, "Radiant Enable (OAT)"),
        ],

        programs=[
            ProgramDef(1, "OAT-ENABLE", "PRG01-OAT-ENABLE.bas", _PRG01_OAT_ENABLE, True,
                       "Outdoor enable — disable radiant above enable temp", exec_order=1),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-RADIANT", "Radiant heater system overview"),
            SystemGroupDef("{device-name}-SET-POINTS", "Setpoints and configuration"),
        ],

        soo_paragraph="""The standalone radiant heater controller shall enable radiant heating
based on outside air temperature, disabling the valves above the configured enable
temperature and driving them to the minimum position. Heater control shall follow
the selected mode: individual hard-wired sensor per heater, a single shared sensor
driving all heaters, or outdoor reset only.""",
    )


def _float_drive(n, pos_cmd, sync):
    """Per-heater FLOAT() drive block (floating valves)."""
    return (
        f"IF+ POWER-LOSS THEN START {sync}\n"
        f"IF+ RAD-ENABLE = 0 THEN START {sync}\n"
        f"IF TIME-ON( {sync} ) > 0:00:05 THEN STOP {sync}\n"
        f"RAD-{n}-POS = FLOAT( RAD-{n}-OPEN , RAD-{n}-CLOSE , {pos_cmd} , "
        f"CFG-RAD-DRV-TIME , CFG-RAD-POS-DB , {sync} )\n"
    )


def build_rad_heaters(num_heaters, mode, valve, sensor="hardwired"):
    """Composite heaters module for one RAD family configuration.

    Args:
        num_heaters: 1-8
        mode: 'a' (individual), 'b' (shared sensor), 'c' (outdoor reset)
        valve: 'mod' (modulating AO) | 'flt' (floating BO pair)
        sensor: 'hardwired' | 'comm' (Mode A/B space sensor source)
    """
    mode = mode.lower()
    valve = valve.lower()
    floating = (valve == "flt")

    inputs, outputs, values, loops, programs = [], [], [], [], []

    # ── Shared config points ──
    if mode == "b":
        values.append(ValuePoint(5, "CFG-RAD-SP", "AV", 70.0, "Shared Radiant Setpoint", "deg.F"))
    if floating:
        values.append(ValuePoint(6, "CFG-RAD-DRV-TIME", "AV", 150.0, "Radiant Valve Full Stroke Time", "Sec."))
        values.append(ValuePoint(7, "CFG-RAD-POS-DB",   "AV", 2.0,   "Radiant Float Position Deadband", "%"))

    # ── Mode B shared sensor (hard-wired only adds an AI; comm arrives via BACnet) ──
    if mode == "b" and sensor == "hardwired":
        inputs.append(InputPoint(2, "RAD-RMT", "AI", "10K -40 ->250", "Radiant Zone Temperature", "deg.F"))
    if mode == "b":
        loops.append(LoopDef(1, "RAD-LOOP", "RAD-RMT", "CFG-RAD-SP", "RAD-ALL-POS",
                             p_band=4.0, integral=10.0, action="reverse",
                             description="Shared radiant demand from zone temp"))

    # ── Per-heater hardware + Mode A per-heater sensor/loop ──
    for n in range(1, num_heaters + 1):
        b = 10 * n  # per-heater instance block base
        if floating:
            outputs.append(OutputPoint(2 * n - 1, f"RAD-{n}-OPEN",  "BO", "Off/On", f"Radiant {n} Valve Open",  units=""))
            outputs.append(OutputPoint(2 * n,     f"RAD-{n}-CLOSE", "BO", "Off/On", f"Radiant {n} Valve Close", units=""))
            values.append(ValuePoint(b + 1, f"RAD-{n}-POS",        "AV", 0.0,   f"Radiant {n} Valve Position",     "%"))
            values.append(ValuePoint(b + 3, f"RAD-{n}-FLOAT-SYNC", "BV", False, f"Radiant {n} Float Sync Trigger"))
            if mode == "a":
                values.append(ValuePoint(b + 2, f"RAD-{n}-POS-CMD", "AV", 0.0, f"Radiant {n} Commanded Position", "%"))
        else:
            outputs.append(OutputPoint(n, f"RAD-{n}-VLV", "AO", "0.0 ->100%", f"Radiant {n} Valve", 2.0, 10.0, False, "%"))

        if mode == "a":
            if sensor == "hardwired":
                inputs.append(InputPoint(1 + n, f"RAD-{n}-RMT", "AI", "10K -40 ->250", f"Radiant {n} Zone Temperature", "deg.F"))
            values.append(ValuePoint(b, f"RAD-{n}-SP", "AV", 70.0, f"Radiant {n} Setpoint", "deg.F"))
            out_ref = f"RAD-{n}-POS-CMD" if floating else f"RAD-{n}-VLV"
            loops.append(LoopDef(n, f"RAD-{n}-LOOP", f"RAD-{n}-RMT", f"RAD-{n}-SP", out_ref,
                                 p_band=4.0, integral=10.0, action="reverse",
                                 description=f"Radiant {n} demand from its own zone temp"))

    # ── Programs ──
    if mode == "a":
        for n in range(1, num_heaters + 1):
            if floating:
                code = (
                    f"REM --- RAD-{n} ---\n"
                    f"REM Heater {n}: independent loop drives its own floating valve.\n"
                    f"RAD-{n}-POS-CMD = RAD-{n}-LOOP\n"
                    f"IF RAD-ENABLE = 0 THEN RAD-{n}-POS-CMD = CFG-RAD-MIN-POS\n"
                    + _float_drive(n, f"RAD-{n}-POS-CMD", f"RAD-{n}-FLOAT-SYNC")
                )
            else:
                code = (
                    f"REM --- RAD-{n} ---\n"
                    f"REM Heater {n}: independent loop drives its own modulating valve.\n"
                    f"IF RAD-ENABLE = 0 THEN RAD-{n}-VLV = CFG-RAD-MIN-POS\n"
                    f"IF RAD-ENABLE = 0 THEN END\n"
                    f"RAD-{n}-VLV = RAD-{n}-LOOP\n"
                )
            programs.append(ProgramDef(10 + n, f"RAD-{n}", f"PRG{10 + n:02d}-RAD-{n}.bas", code, True,
                                       f"Radiant heater {n} — individual sensor control", exec_order=10 + n))
    else:
        # Mode B / Mode C — one program drives all valves
        if mode == "b":
            head = (
                "REM --- RAD-ALL ---\n"
                "REM Shared sensor: one loop drives all radiant valves to one position.\n"
                "IF RAD-ENABLE = 0 THEN RAD-ALL-POS = CFG-RAD-MIN-POS\n"
            )
            if floating:
                body = "RAD-ALL-POS = RAD-LOOP\nIF RAD-ENABLE = 0 THEN RAD-ALL-POS = CFG-RAD-MIN-POS\n"
            else:
                body = "IF RAD-ENABLE = 0 THEN END\nRAD-ALL-POS = RAD-LOOP\n"
        else:  # mode == 'c'
            head = (
                "REM --- RAD-ALL ---\n"
                "REM Outdoor reset only: valve position from OAT, no space sensor.\n"
                "REM OAT 0 deg.F = 100%, OAT at enable temp = minimum position.\n"
                "IF OAT > CFG-RAD-ENABLE-OAT THEN RAD-ALL-POS = CFG-RAD-MIN-POS\n"
            )
            if floating:
                body = (
                    "RAD-ALL-POS = SLIDE( OAT , 0 , CFG-RAD-ENABLE-OAT , 100 , CFG-RAD-MIN-POS )\n"
                    "IF OAT > CFG-RAD-ENABLE-OAT THEN RAD-ALL-POS = CFG-RAD-MIN-POS\n"
                )
            else:
                body = (
                    "IF OAT > CFG-RAD-ENABLE-OAT THEN END\n"
                    "RAD-ALL-POS = SLIDE( OAT , 0 , CFG-RAD-ENABLE-OAT , 100 , CFG-RAD-MIN-POS )\n"
                )

        if floating:
            drive = ""
            for n in range(1, num_heaters + 1):
                drive += _float_drive(n, "RAD-ALL-POS", f"RAD-{n}-FLOAT-SYNC")
            code = head + body + drive
        else:
            assigns = " : ".join(f"RAD-{n}-VLV = RAD-ALL-POS" for n in range(1, num_heaters + 1))
            code = head + body + assigns + "\n"

        programs.append(ProgramDef(5, "RAD-ALL", "PRG05-RAD-ALL.bas", code, True,
                                   "All radiant valves driven from shared position", exec_order=5))

    mode_name = {"a": "Individual Sensor", "b": "Shared Sensor", "c": "Outdoor Reset"}[mode]
    valve_name = "Floating" if floating else "Modulating"

    return Module(
        id=f"rad-htrs-{num_heaters}-{mode}-{valve}",
        name=f"Radiant Heaters x{num_heaters} ({mode_name}, {valve_name})",
        category="radiant",
        description=f"{num_heaters} radiant heater(s) — {mode_name} mode, {valve_name} valves",
        is_core=False,
        inputs=inputs,
        outputs=outputs,
        values=values,
        loops=loops,
        programs=programs,
        system_groups=[SystemGroupDef("{device-name}-RADIANT-CTRL", "Radiant heater control")],
        soo_paragraph=f"""The controller shall operate {num_heaters} radiant heating valve(s) in
{mode_name.lower()} mode using {valve_name.lower()} valve control.""",
        requires=["rad-core"],
    )
