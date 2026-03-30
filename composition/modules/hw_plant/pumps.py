"""
HW-PLANT Pump Modules — Constant Speed, VFD, Primary/Secondary

All pump modules scale per number of pumps (1-4).
Lead/lag logic is only generated when N > 1.
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)

# I/O rows for pump module — after boiler module
# Inputs: pump status starts at row 11
_PUMP_STS_BASE = 11      # BI: HWP1-STS at IN11, HWP2 at IN12
# Outputs: pump S/S starts at row 9
_PUMP_SS_BASE = 9        # BO: HWP1-S/S at OUT9, HWP2 at OUT10
_PUMP_SPD_BASE = 11      # AO: HWP1-SPEED at OUT11, HWP2 at OUT12 (VFD only)
# DP sensor inputs
_DP_INPUT_1 = 15         # AI: HW-PRESS1 at IN15
_DP_INPUT_2 = 16         # AI: HW-PRESS2 at IN16


def build_pump_cs(num_pumps=2):
    """Constant speed pumps with lead/lag.

    Args:
        num_pumps: 1-4 pumps
    """
    inputs = []
    outputs = []
    values = []

    for n in range(1, num_pumps + 1):
        outputs.append(OutputPoint(
            _PUMP_SS_BASE + n - 1, f"HWP{n}-S/S", "BO", "Stop/Start",
            f"HW Pump {n} Start/Stop"))
        inputs.append(InputPoint(
            _PUMP_STS_BASE + n - 1, f"HWP{n}-STS", "BI", "Off/On",
            f"HW Pump {n} Status"))
        values.append(ValuePoint(
            51 + (n-1)*2, f"HWP{n}-FAIL", "BV", False,
            f"HW Pump {n} Failure"))
        values.append(ValuePoint(
            52 + (n-1)*2, f"HWP{n}-OOS", "BV", False,
            f"HW Pump {n} Out of Service"))

    # ANY-HWP-ON always needed (cascade boiler interlock requires it)
    values.append(ValuePoint(64, "ANY-HWP-ON", "BV", False, "Any Pump Running"))

    if num_pumps > 1:
        values.extend([
            ValuePoint(60, "LEAD-HWP",      "AV", 1.0,  "Lead Pump Number", "#"),
            ValuePoint(61, "LEAD-HWP-SS",   "BV", False, "Lead Pump Start/Stop"),
            ValuePoint(62, "LAG-HWP-SS",    "BV", False, "Lag Pump Start/Stop"),
            ValuePoint(63, "LEAD-HWP-FAIL", "BV", False, "Lead Pump Failure"),
        ])

    programs = [
        ProgramDef(16, "HW-HWP1-PRG", "HW-PRG16-HWP1.bas", "", True,
                   "HW pump 1 start/stop", "hw-pump-cs", exec_order=16),
    ]
    if num_pumps > 1:
        programs.append(ProgramDef(19, "HW-HWP2-PRG", "HW-PRG19-HWP2.bas", "", True,
                   "HW pump 2 start/stop", "hw-pump-cs", exec_order=19))
        programs.append(ProgramDef(17, "HW-LEAD-LAG-PRG", "HW-PRG17-LEAD-LAG.bas", "", True,
                   "Pump and boiler lead/lag rotation", "hw-pump-cs", exec_order=17))

    schedules = []
    if num_pumps > 1:
        schedules.append(ScheduleDef(3, "{device-name}-HWP-LEAD-SCHED", "Pump 1",
            [f"Pump {n}" for n in range(1, num_pumps + 1)], 10,
            "Pump lead rotation schedule"))

    return Module(
        id="hw-pump-cs",
        name=f"Constant Speed Pumps ({num_pumps})",
        category="hw-pump",
        description=f"{num_pumps} constant speed HW pump(s) with lead/lag",
        inputs=inputs, outputs=outputs, values=values,
        programs=programs, schedules=schedules,
        system_groups=[
            SystemGroupDef("{device-name}-PUMP-CTRL", "Pump status, lead/lag, failures"),
        ],
        soo_paragraph=f"""{num_pumps} constant speed hot water circulation pump(s) shall be provided.
{"Lead/lag rotation shall alternate the duty pump on a configurable schedule. If the lead pump fails (no status after 30 seconds), the lag pump shall start automatically." if num_pumps > 1 else "The pump shall start when the HW system is enabled and stop when disabled."}
Pump status shall be monitored via current switch or auxiliary contact.""",
        requires=["hw-core"],
        conflicts=["hw-pump-vfd", "hw-pump-pri-sec"],
        mutually_exclusive_group="hw-pump",
    )


def build_pump_vfd(num_pumps=2):
    """VFD pumps with differential pressure control.

    Args:
        num_pumps: 1-4 pumps
    """
    inputs = []
    outputs = []
    values = []

    for n in range(1, num_pumps + 1):
        outputs.append(OutputPoint(
            _PUMP_SS_BASE + n - 1, f"HWP{n}-S/S", "BO", "Stop/Start",
            f"HW Pump {n} Start/Stop"))
        inputs.append(InputPoint(
            _PUMP_STS_BASE + n - 1, f"HWP{n}-STS", "BI", "Off/On",
            f"HW Pump {n} Status"))
        outputs.append(OutputPoint(
            _PUMP_SPD_BASE + (n-1)*2, f"HWP{n}-SPEED", "AO", "0.0 ->100%",
            f"HW Pump {n} VFD Speed", 2.0, 10.0))
        values.append(ValuePoint(
            51 + (n-1)*2, f"HWP{n}-FAIL", "BV", False,
            f"HW Pump {n} Failure"))
        values.append(ValuePoint(
            52 + (n-1)*2, f"HWP{n}-OOS", "BV", False,
            f"HW Pump {n} Out of Service"))

    # DP sensors
    inputs.append(InputPoint(_DP_INPUT_1, "HW-PRESS1", "AI", "0 ->100% (0-5V)",
        "HW Differential Pressure 1", "PSI"))
    inputs.append(InputPoint(_DP_INPUT_2, "HW-PRESS2", "AI", "0 ->100% (0-5V)",
        "HW Differential Pressure 2", "PSI"))

    # Speed and DP setpoints
    values.extend([
        ValuePoint(64, "ANY-HWP-ON",     "BV", False, "Any Pump Running"),
        ValuePoint(65, "HWP-MIN-SPEED",   "AV", 30.0,  "Pump Minimum Speed",    "%"),
        ValuePoint(66, "HWP-MAX-SPEED",   "AV", 100.0, "Pump Maximum Speed",    "%"),
        ValuePoint(67, "AVG-DP",          "AV", 0.0,   "Average Differential Pressure", "PSI"),
        ValuePoint(68, "HWS-DP-SP",       "AV", 12.0,  "DP Setpoint",           "PSI"),
    ])

    if num_pumps > 1:
        values.extend([
            ValuePoint(60, "LEAD-HWP",      "AV", 1.0,  "Lead Pump Number",   "#"),
            ValuePoint(61, "LEAD-HWP-SS",   "BV", False, "Lead Pump Start/Stop"),
            ValuePoint(62, "LAG-HWP-SS",    "BV", False, "Lag Pump Start/Stop"),
            ValuePoint(63, "LEAD-HWP-FAIL", "BV", False, "Lead Pump Failure"),
        ])

    # DP PID loop
    loops = [
        LoopDef(1, "HW-DP-LOOP", "AVG-DP", "HWS-DP-SP", "HWP1-SPEED",
                p_band=5.0, integral=60.0, action="direct",
                description="HW Differential Pressure Control"),
    ]

    programs = [
        ProgramDef(16, "HW-HWP1-PRG", "HW-PRG16-HWP1.bas", "", True,
                   "HW pump 1 start/stop", "hw-pump-vfd", exec_order=16),
        ProgramDef(20, "HW-HWP-SPEED-PRG", "HW-PRG17-HWP-SPEED.bas", "", True,
                   "Pump VFD speed from DP loop", "hw-pump-vfd", exec_order=20),
    ]
    if num_pumps > 1:
        programs.append(ProgramDef(19, "HW-HWP2-PRG", "HW-PRG19-HWP2.bas", "", True,
                   "HW pump 2 start/stop", "hw-pump-vfd", exec_order=19))
        programs.append(ProgramDef(17, "HW-LEAD-LAG-PRG", "HW-PRG17-LEAD-LAG.bas", "", True,
                   "Pump and boiler lead/lag rotation", "hw-pump-vfd", exec_order=17))

    schedules = []
    if num_pumps > 1:
        schedules.append(ScheduleDef(3, "{device-name}-HWP-LEAD-SCHED", "Pump 1",
            [f"Pump {n}" for n in range(1, num_pumps + 1)], 10,
            "Pump lead rotation schedule"))

    return Module(
        id="hw-pump-vfd",
        name=f"VFD Pumps ({num_pumps})",
        category="hw-pump",
        description=f"{num_pumps} VFD HW pump(s) with DP control",
        inputs=inputs, outputs=outputs, values=values,
        loops=loops, programs=programs, schedules=schedules,
        system_groups=[
            SystemGroupDef("{device-name}-PUMP-CTRL", "Pump speed, DP, lead/lag, failures"),
        ],
        soo_paragraph=f"""{num_pumps} variable frequency drive hot water circulation pump(s)
shall be provided. Pump speed shall be controlled by a PID loop maintaining
differential pressure setpoint. {"Lead/lag rotation shall alternate the duty pump. If the lead pump fails, the lag pump shall start automatically." if num_pumps > 1 else ""}
Minimum and maximum speed limits shall be configurable.""",
        requires=["hw-core"],
        conflicts=["hw-pump-cs", "hw-pump-pri-sec"],
        mutually_exclusive_group="hw-pump",
    )


def build_pump_pri_sec(num_primary=2, num_secondary=2):
    """Primary/secondary pumping arrangement.

    Args:
        num_primary: 1-4 primary pumps (constant speed)
        num_secondary: 1-4 secondary pumps (VFD)
    """
    inputs = []
    outputs = []
    values = []

    # Primary loop temps — right after pump status inputs
    inputs.append(InputPoint(16, "PRI-HWS-T", "AI", "10K -40 ->250",
        "Primary Loop HW Supply Temperature", "°F"))
    inputs.append(InputPoint(17, "PRI-HWR-T", "AI", "10K -40 ->250",
        "Primary Loop HW Return Temperature", "°F"))

    # Secondary loop temps
    inputs.append(InputPoint(18, "SEC-HWS-T", "AI", "10K -40 ->250",
        "Secondary Loop HW Supply Temperature", "°F"))
    inputs.append(InputPoint(19, "SEC-HWR-T", "AI", "10K -40 ->250",
        "Secondary Loop HW Return Temperature", "°F"))

    # Primary pumps — constant speed, S/S outputs start at OUT9
    for n in range(1, num_primary + 1):
        outputs.append(OutputPoint(
            _PUMP_SS_BASE + n - 1, f"PHWP{n}", "BO", "Stop/Start",
            f"Primary HW Pump {n}"))
        inputs.append(InputPoint(
            _PUMP_STS_BASE + n - 1, f"PHWP{n}-STS", "BI", "Off/On",
            f"Primary HW Pump {n} Status"))
        values.append(ValuePoint(
            51 + (n-1)*2, f"PHWP{n}-FAIL", "BV", False,
            f"Primary Pump {n} Failure"))
        values.append(ValuePoint(
            52 + (n-1)*2, f"PHWP{n}-OOS", "BV", False,
            f"Primary Pump {n} Out of Service"))

    # Secondary pumps — VFD
    # S/S outputs continue after primary: OUT11, OUT12, ...
    sec_ss_base = _PUMP_SS_BASE + num_primary
    # Status inputs continue after primary: IN13, IN14, ...
    sec_sts_base = _PUMP_STS_BASE + num_primary
    # Speed AO outputs at separate rows: OUT15, OUT16, ...
    sec_spd_base = 15
    for n in range(1, num_secondary + 1):
        outputs.append(OutputPoint(
            sec_ss_base + n - 1, f"SHWP{n}", "BO", "Stop/Start",
            f"Secondary HW Pump {n}"))
        inputs.append(InputPoint(
            sec_sts_base + n - 1, f"SHWP{n}-STS", "BI", "Off/On",
            f"Secondary HW Pump {n} Status"))
        outputs.append(OutputPoint(
            sec_spd_base + n - 1, f"SHWP{n}-SPEED", "AO", "0.0 ->100%",
            f"Secondary HW Pump {n} VFD Speed", 2.0, 10.0))
        values.append(ValuePoint(
            59 + (n-1)*2, f"SHWP{n}-FAIL", "BV", False,
            f"Secondary Pump {n} Failure"))
        values.append(ValuePoint(
            60 + (n-1)*2, f"SHWP{n}-OOS", "BV", False,
            f"Secondary Pump {n} Out of Service"))

    # DP sensor
    inputs.append(InputPoint(15, "HW-PRESS1", "AI", "0 ->100% (0-5V)",
        "HW Differential Pressure", "PSI"))

    # System values
    values.extend([
        ValuePoint(67, "HWS-DP-SP",       "AV", 12.0,  "Secondary DP Setpoint",  "PSI"),
        ValuePoint(68, "HWP-MIN-SPEED",   "AV", 30.0,  "Secondary Min Speed",    "%"),
        ValuePoint(69, "HWP-MAX-SPEED",   "AV", 100.0, "Secondary Max Speed",    "%"),
        ValuePoint(73, "PRI-DELTA-T",     "AV", 0.0,   "Primary Loop Delta T",   "°F"),
        ValuePoint(74, "SEC-DELTA-T",     "AV", 0.0,   "Secondary Loop Delta T", "°F"),
    ])

    loops = [
        LoopDef(1, "HW-DP-LOOP", "HW-PRESS1", "HWS-DP-SP", "SHWP1-SPEED",
                p_band=5.0, integral=60.0, action="direct",
                description="Secondary HW Pump DP Control"),
    ]

    # Lead/lag values for secondary pumps (same pattern as CS/VFD pumps)
    if num_secondary > 1:
        values.extend([
            ValuePoint(65, "LEAD-SHWP",       "AV", 1.0,  "Lead Secondary Pump Number", "#"),
            ValuePoint(66, "LEAD-SHWP-SS",    "BV", False, "Lead Secondary Pump S/S"),
            ValuePoint(70, "LAG-SHWP-SS",     "BV", False, "Lag Secondary Pump S/S"),
            ValuePoint(71, "LEAD-SHWP-FAIL",  "BV", False, "Lead Secondary Pump Failure"),
            ValuePoint(72, "ANY-SHWP-ON",     "BV", False, "Any Secondary Pump Running"),
        ])

    programs = [
        # Primary: one program handles all primary pumps (simple standby, not lead/lag)
        ProgramDef(16, "HW-PHWP-PRG", "HW-PRG16-PHWP.bas", "", True,
                   "Primary pump control", "hw-pump-pri-sec", exec_order=16),
        # Secondary: per-pump S/S program (same pattern as CS/VFD)
        ProgramDef(21, "HW-SHWP1-PRG", "HW-PRG21-SHWP1.bas", "", True,
                   "Secondary pump 1 start/stop", "hw-pump-pri-sec", exec_order=21),
        # Secondary speed: per-pump VFD speed from DP
        ProgramDef(23, "HW-SHWP1-SPEED-PRG", "HW-PRG23-SHWP1-SPEED.bas", "", True,
                   "Secondary pump 1 VFD speed", "hw-pump-pri-sec", exec_order=23),
    ]
    if num_secondary > 1:
        programs.append(ProgramDef(22, "HW-SHWP2-PRG", "HW-PRG22-SHWP2.bas", "", True,
                   "Secondary pump 2 start/stop", "hw-pump-pri-sec", exec_order=22))
        programs.append(ProgramDef(24, "HW-SHWP2-SPEED-PRG", "HW-PRG24-SHWP2-SPEED.bas", "", True,
                   "Secondary pump 2 VFD speed", "hw-pump-pri-sec", exec_order=24))
        programs.append(ProgramDef(25, "HW-SHWP-LEAD-LAG-PRG", "HW-PRG25-SHWP-LEAD-LAG.bas", "", True,
                   "Secondary pump lead/lag rotation", "hw-pump-pri-sec", exec_order=25))

    schedules = []
    if num_secondary > 1:
        schedules.append(ScheduleDef(3, "{device-name}-SHWP-LEAD-SCHED", "Pump 1",
            [f"Pump {n}" for n in range(1, num_secondary + 1)], 10,
            "Secondary pump lead rotation schedule"))

    return Module(
        id="hw-pump-pri-sec",
        name=f"Primary/Secondary Pumps ({num_primary}P+{num_secondary}S)",
        category="hw-pump",
        description=f"{num_primary} primary + {num_secondary} secondary VFD pumps",
        inputs=inputs, outputs=outputs, values=values,
        loops=loops, programs=programs, schedules=schedules,
        system_groups=[
            SystemGroupDef("{device-name}-PUMP-CTRL", "Primary/secondary pumps, DP, speed"),
        ],
        soo_paragraph=f"""{num_primary} constant speed primary pump(s) shall circulate water through
the boiler loop. {num_secondary} variable frequency drive secondary pump(s) shall distribute
water to the building loop. Secondary pump speed shall be controlled by a PID loop
maintaining differential pressure setpoint in the distribution header.
Primary pumps shall run whenever any boiler is active. Secondary pump lead/lag rotation
shall alternate the duty pump on a configurable schedule.""",
        requires=["hw-core"],
        conflicts=["hw-pump-cs", "hw-pump-vfd"],
        mutually_exclusive_group="hw-pump",
    )
