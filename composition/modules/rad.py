"""
SBS-RAD — Standalone Radiant Heater Modules (Rebuilt)

A standalone controller driving 1-8 radiant heating valves. Controller is
auto-selected by heater count (handled in assembler._select_controller):
  1-4 heaters -> MACH-ProZone 44 (MPZ-44, 4 AI inputs, 4 BO outputs)
  5-8 heaters -> MACH-ProZone 88 (MPZ-88, 8 AI inputs, 8 BO outputs)

Three control modes (mutually exclusive):
  Mode A — individual sensor + independent loop + setpoint per heater
  Mode B — one shared sensor / one loop driving all valves to same position
  Mode C — outdoor reset only, no space sensor (valve position = SLIDE of OAT)

Valve options per heater (same across all families):
  mod — modulating AO per heater (RAD-N-VLV)
  flt — floating point per heater (RAD-N-OPEN/RAD-N-CLOSE BOs, RAD-N-POS AV),
        CBAS FLOAT() with POWER-LOSS sync trigger

Sensor options (modes A and B; mode C requires OAT only):
  SST3       — hardwired 10K AI input per heater
               Max heaters: 3 on MPZ44 (OAT+RMT uses 2 AIs, leaves 2), 7 on MPZ88 (OAT+RMT uses 2, leaves 6)
  SST-UD     — hardwired 10K AI per heater + AO setpoint adjust per heater
               Same AI limits as SST3; adds 1 AO per heater output
  SS3        — BACnet smart-stat per heater (communicating, no AI used)
               Max heaters: unlimited (no AI consumption)
  Network    — network AV point per heater (RAD-N-SPACE-TEMP), tech binds to source
               Max heaters: unlimited (no AI consumption)

Config points (all modes, in rad-core):
  CFG-RAD-ENABLE-OAT = 50 deg.F  (outdoor enable / reset cutoff; applies to ALL modes)
  CFG-RAD-MIN-POS    = 0%        (minimum valve position when OAT > enable)

Config points (mode-specific):
  Mode A: CFG-RAD-SP-N (individual setpoint per heater, 70F default)
  Mode B: CFG-RAD-SP (shared setpoint, 70F default)
  Floating: CFG-RAD-DRV-TIME (150s default), CFG-RAD-POS-DB (2% default)

The heaters module is built per-family by build_rad_heaters(num, mode, valve, sensor).
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, SystemGroupDef
)


_PRG00_OAT_SOURCE = """\
REM --- OAT-SOURCE ---
REM Read network outdoor temperature from parent controller with validation
REM Range check: -60°F to 140°F. Fallback 10°F (fails warm).
REM
IF {parent}AV1 < -60 OR {parent}AV1 > 140 THEN NET-OAT = 10 ELSE NET-OAT = {parent}AV1
"""

_PRG01_OAT_ENABLE = """\
REM --- OAT-ENABLE ---
REM Outdoor enable: disable radiant above the enable temperature.
REM
IF NET-OAT > CFG-RAD-ENABLE-OAT THEN RAD-ENABLE = 0 ELSE RAD-ENABLE = 1
"""


def build_rad_core():
    """Radiant heater core — network OAT, enable logic, shared config."""
    return Module(
        id="rad-core",
        name="Radiant Heater Core",
        category="core",
        description="Standalone radiant heater base: network OAT, outdoor enable, shared config",
        is_core=True,

        inputs=[],

        values=[
            ValuePoint(1, "RAD-ALL-POS",        "AV", 0.0,  "Radiant Valve Position (shared)",  "%"),
            ValuePoint(2, "CFG-RAD-ENABLE-OAT", "AV", 50.0, "Outdoor Enable / Reset Cutoff",    "deg.F"),
            ValuePoint(3, "CFG-RAD-MIN-POS",    "AV", 0.0,  "Minimum Valve Position",           "%"),
            ValuePoint(4, "RAD-ENABLE",         "BV", True, "Radiant Enable (OAT)"),
            ValuePoint(5, "NET-OAT",            "AV", 32.0, "Outside Air Temp — reads from network source at commissioning", "deg.F"),
        ],

        programs=[
            ProgramDef(1, "OAT-SOURCE", "PRG01-OAT-SOURCE.bas", _PRG00_OAT_SOURCE, True,
                       "Read network outdoor temperature from parent controller", exec_order=1),
            ProgramDef(2, "OAT-ENABLE", "PRG02-OAT-ENABLE.bas", _PRG01_OAT_ENABLE, True,
                       "Outdoor enable — disable radiant above enable temp", exec_order=2),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-RADIANT", "Radiant heater system overview"),
            SystemGroupDef("{device-name}-SET-POINTS", "Setpoints and configuration"),
        ],

        soo_paragraph="""The standalone radiant heater controller shall enable radiant heating
based on outside air temperature, disabling the valves above the configured enable
temperature and driving them to the minimum position. Heater control shall follow
the selected mode: individual sensor per heater (hardwired or communicating), a single
shared sensor driving all heaters, or outdoor reset only.""",
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


def build_rad_heaters(num_heaters, mode, valve, sensor="sst3"):
    """Composite heaters module for one RAD family configuration.

    Args:
        num_heaters: 1-8
        mode: 'a' (individual), 'b' (shared sensor), 'c' (outdoor reset)
        valve: 'mod' (modulating AO) | 'flt' (floating BO pair)
        sensor: 'sst3' (hardwired AI) | 'sst-ud' (hardwired + AO adjust) |
                'ss3' (BACnet smart stat) | 'network' (AV point, tech binds)
    """
    mode = mode.lower()
    valve = valve.lower()
    sensor = sensor.lower()
    floating = (valve == "flt")

    # ── Validate heater count limits for sensor type ──
    ai_limited = sensor in ("sst3", "sst-ud")
    if ai_limited:
        # SST3 / SST-UD: sensor uses AI (1 per heater in mode A, 1 in mode B)
        # OAT is now network AV (NET-OAT), freeing all AIs for zone sensors
        # SST3: 1 AI per heater
        #   MPZ44: 4 AIs total, max 4 heaters
        #   MPZ88: 8 AIs total, max 8 heaters
        # SST-UD: 2 AIs per heater (AI + AO setpoint adjust)
        #   MPZ44: 4 AIs ÷ 2 = max 2 heaters
        #   MPZ88: 8 AIs ÷ 2 = max 4 heaters
        if sensor == "sst3":
            max_mpz44 = 4
            max_mpz88 = 8
        else:  # sst-ud
            max_mpz44 = 2
            max_mpz88 = 4
    else:
        # SS3 / Network: no AI consumed (BACnet or AV points)
        max_mpz44 = 8
        max_mpz88 = 8

    mpz = "MPZ-44" if num_heaters <= 4 else "MPZ-88"
    max_allowed = max_mpz44 if num_heaters <= 4 else max_mpz88
    if ai_limited and num_heaters > max_allowed:
        raise ValueError(
            f"{sensor.upper()} sensor on {mpz}: max {max_allowed} heaters (AI limit). "
            f"Requested {num_heaters}. Use SS3 or Network sensor for unlimited heater count."
        )

    inputs, outputs, values, loops, programs = [], [], [], [], []

    # ── Shared config points ──
    if mode == "b":
        values.append(ValuePoint(5, "CFG-RAD-SP", "AV", 70.0, "Shared Radiant Setpoint", "deg.F"))
    if floating:
        values.append(ValuePoint(6, "CFG-RAD-DRV-TIME", "AV", 150.0, "Radiant Valve Full Stroke Time", "Sec."))
        values.append(ValuePoint(7, "CFG-RAD-POS-DB",   "AV", 2.0,   "Radiant Float Position Deadband", "%"))

    # ── Mode B shared sensor (sensor-type specific) ──
    if mode == "b":
        if sensor == "sst3":
            inputs.append(InputPoint(2, "RAD-RMT", "AI", "10K -40 ->250", "Radiant Zone Temperature", "deg.F"))
        elif sensor == "sst-ud":
            inputs.append(InputPoint(2, "RAD-RMT", "AI", "10K -40 ->250", "Radiant Zone Temperature", "deg.F"))
            outputs.append(OutputPoint(8, "RAD-SP-ADJ", "AO", "0.0 ->100%", "Radiant Setpoint Adjust", 2.0, 10.0, False, "%"))
            values.append(ValuePoint(8, "RAD-SP-ADJ-IN", "AV", 50.0, "Radiant Setpoint Adjust (Input)", "%"))
        elif sensor == "ss3":
            # BACnet smart stat: no AI, reads RMT-N from network
            values.append(ValuePoint(9, "RAD-RMT", "AV", 70.0, "Radiant Zone Temp (from SS3 sensor)", "deg.F"))
        elif sensor == "network":
            # Network source: tech binds RAD-SPACE-TEMP to network AV point
            values.append(ValuePoint(10, "RAD-SPACE-TEMP", "AV", 70.0, "Radiant Zone Temp (network source)", "deg.F"))

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
            # Mode A: individual sensor + loop per heater
            if sensor == "sst3":
                inputs.append(InputPoint(1 + n, f"RAD-{n}-RMT", "AI", "10K -40 ->250", f"Radiant {n} Zone Temp", "deg.F"))
            elif sensor == "sst-ud":
                inputs.append(InputPoint(1 + n, f"RAD-{n}-RMT", "AI", "10K -40 ->250", f"Radiant {n} Zone Temp", "deg.F"))
                outputs.append(OutputPoint(20 + n, f"RAD-{n}-SP-ADJ", "AO", "0.0 ->100%", f"Radiant {n} SP Adjust", 2.0, 10.0, False, "%"))
                values.append(ValuePoint(50 + n, f"RAD-{n}-SP-ADJ-IN", "AV", 50.0, f"Radiant {n} SP Adjust (Input)", "%"))
            elif sensor == "ss3":
                # BACnet smart stat: reads RMT-N from network, no AI
                values.append(ValuePoint(b + 4, f"RAD-{n}-RMT", "AV", 70.0, f"Radiant {n} Zone Temp (from SS3)", "deg.F"))
            elif sensor == "network":
                # Network source: tech binds RAD-N-RMT to network AV at commissioning
                values.append(ValuePoint(b + 4, f"RAD-{n}-RMT", "AV", 70.0, f"Radiant {n} Zone Temp (network)", "deg.F"))

            values.append(ValuePoint(b, f"CFG-RAD-SP-{n}", "AV", 70.0, f"Radiant {n} Setpoint", "deg.F"))
            out_ref = f"RAD-{n}-POS-CMD" if floating else f"RAD-{n}-VLV"
            loops.append(LoopDef(n, f"RAD-{n}-LOOP", f"RAD-{n}-RMT", f"CFG-RAD-SP-{n}", out_ref,
                                 p_band=4.0, integral=10.0, action="reverse",
                                 description=f"Radiant {n} demand from its own zone temp"))

    # ── Programs ──
    if mode == "a":
        # For network sensor: add REM-only NETWORK-SHARE program with binding instructions
        if sensor == "network":
            share_code = "REM ***** NETWORK-SHARE *****\n"
            share_code += "REM **** Map each zone temp from network source at commissioning\n"
            for n in range(1, num_heaters + 1):
                share_code += f"REM **** {{device-name}}-RAD-{n}-RMT = [network device].[zone temp point]\n"
            programs.append(ProgramDef(2, "NETWORK-SHARE", "PRG02-NETWORK-SHARE.bas", share_code, True,
                                       f"Network binding instructions for tech commissioning", exec_order=2))

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
                    f"IF RAD-ENABLE = 0 THEN RAD-{n}-VLV = CFG-RAD-MIN-POS , END\n"
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
            )
            if floating:
                body = "IF RAD-ENABLE = 0 THEN RAD-ALL-POS = CFG-RAD-MIN-POS\nRAD-ALL-POS = RAD-LOOP\n"
            else:
                body = "IF RAD-ENABLE = 0 THEN RAD-ALL-POS = CFG-RAD-MIN-POS , END\nRAD-ALL-POS = RAD-LOOP\n"
        else:  # mode == 'c'
            head = (
                "REM --- RAD-ALL ---\n"
                "REM Outdoor reset only: valve position from OAT, no space sensor.\n"
                "REM NET-OAT 0 deg.F = 100%, NET-OAT at enable temp = minimum position.\n"
            )
            if floating:
                body = (
                    "IF NET-OAT > CFG-RAD-ENABLE-OAT THEN RAD-ALL-POS = CFG-RAD-MIN-POS\n"
                    "RAD-ALL-POS = SLIDE( NET-OAT , 0 , CFG-RAD-ENABLE-OAT , 100 , CFG-RAD-MIN-POS )\n"
                )
            else:
                body = (
                    "IF NET-OAT > CFG-RAD-ENABLE-OAT THEN END\n"
                    "RAD-ALL-POS = SLIDE( NET-OAT , 0 , CFG-RAD-ENABLE-OAT , 100 , CFG-RAD-MIN-POS )\n"
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

    # ── Build descriptor ──
    mode_name = {"a": "Individual Sensor", "b": "Shared Sensor", "c": "Outdoor Reset"}[mode]
    valve_name = "Floating" if floating else "Modulating"
    sensor_name = {
        "sst3": "SST3 (Hardwired)",
        "sst-ud": "SST-UD (Hardwired + Adjust)",
        "ss3": "SS3 (Smart Stat)",
        "network": "Network (AV Point)",
        "oat": "OAT Reset"
    }[sensor]

    return Module(
        id=f"rad-htrs-{num_heaters}-{mode}-{valve}-{sensor}",
        name=f"Radiant Heaters x{num_heaters} ({mode_name}, {valve_name}, {sensor_name})",
        category="radiant",
        description=f"{num_heaters} radiant heater(s) — {mode_name} mode, {valve_name} valves, {sensor_name}",
        is_core=False,
        inputs=inputs,
        outputs=outputs,
        values=values,
        loops=loops,
        programs=programs,
        system_groups=[SystemGroupDef("{device-name}-RADIANT-CTRL", "Radiant heater control")],
        soo_paragraph=f"""The controller shall operate {num_heaters} radiant heating valve(s) in
{mode_name.lower()} mode using {valve_name.lower()} valve control and {sensor_name.lower()} sensor.""",
        requires=["rad-core"],
    )
