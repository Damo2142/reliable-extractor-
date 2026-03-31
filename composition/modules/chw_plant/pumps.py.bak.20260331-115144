"""
CHW-PLANT Pump Modules — Primary, Secondary, Condenser Water

Primary:   Constant speed, one per chiller, lead/lag rotation.
Secondary: VFD with DP control, lag staging based on DP deviation.
CW Pump:   Constant speed, one per chiller (tower plants only), lead/lag.
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)

# Packed I/O layout — no gaps, minimize expansion modules
_PRI_SS_BASE = 3       # BO: PCHWP1-S/S at OUT3, PCHWP2 at OUT4
_PRI_STS_BASE = 12     # BI: PCHWP1-STS at IN12, PCHWP2 at IN13
_SEC_SS_BASE = 5       # BO: SCHWP1-S/S at OUT5, SCHWP2 at OUT6
_SEC_STS_BASE = 14     # BI: SCHWP1-STS at IN14, SCHWP2 at IN15
_SEC_SPD_BASE = 7      # AO: SCHWP1-SPEED at OUT7, SCHWP2 at OUT8
_DP_SENSOR_BASE = 16   # AI: CHW-PRESS1 at IN16, CHW-PRESS2 at IN17
_CW_SS_BASE = 9        # BO: CDWP1-S/S at OUT9, CDWP2 at OUT10
_CW_STS_BASE = 18      # BI: CDWP1-STS at IN18, CDWP2 at IN19


def build_pump_pri(num_pumps=2):
    """Primary CHW pumps — constant speed, lead/lag.

    Args:
        num_pumps: 1-4 primary pumps
    """
    inputs = []
    outputs = []
    values = []
    programs = []
    schedules = []

    for n in range(1, num_pumps + 1):
        outputs.append(OutputPoint(
            _PRI_SS_BASE + n - 1, f"PCHWP{n}-S/S", "BO", "Stop/Start",
            f"Primary CHW Pump {n} Start/Stop"))
        inputs.append(InputPoint(
            _PRI_STS_BASE + n - 1, f"PCHWP{n}-STS", "BI", "Off/On",
            f"Primary CHW Pump {n} Status"))
        # Per pump: 4 values each starting at 151
        base = 151 + (n - 1) * 4
        values.append(ValuePoint(base,     f"PCHWP{n}-FAIL", "BV", False,
            f"Primary Pump {n} Failure"))
        values.append(ValuePoint(base + 1, f"PCHWP{n}-OOS", "BV", False,
            f"Primary Pump {n} Out of Service"))
        values.append(ValuePoint(base + 2, f"PCHWP{n}-RUNTIME", "AV", 0.0,
            f"Primary Pump {n} Runtime", "Hrs"))
        values.append(ValuePoint(base + 3, f"PCHWP{n}-S", "BV", False,
            f"Primary Pump {n} Status (from .bas)"))

    values.append(ValuePoint(163, "ANY-PCHWP-ON", "BV", False, "Any Primary Pump Running"))

    if num_pumps > 1:
        values.append(ValuePoint(164, "LEAD-PCHWP", "AV", 1.0, "Lead Primary Pump Number", "#"))
        values.append(ValuePoint(165, "LEAD-PCHWP-SS", "BV", False, "Lead Primary Pump Start/Stop"))
        values.append(ValuePoint(166, "LAG-PCHWP-SS", "BV", False, "Lag Primary Pump Start/Stop"))
        values.append(ValuePoint(167, "LEAD-PCHWP-FAIL", "BV", False, "Lead Primary Pump Failure"))

    # Programs
    if num_pumps == 1:
        programs.append(ProgramDef(16, "CHW-PCHWP1-PRG", "CHW-PRG16-PCHWP1-SINGLE.bas", "", True,
            "Primary pump 1 start/stop (single pump)", "chw-pump-pri", exec_order=16))
    else:
        programs.append(ProgramDef(16, "CHW-PCHWP1-PRG", "CHW-PRG16-PCHWP1.bas", "", True,
            "Primary pump 1 start/stop", "chw-pump-pri", exec_order=16))
        programs.append(ProgramDef(19, "CHW-PCHWP2-PRG", "CHW-PRG19-PCHWP2.bas", "", True,
            "Primary pump 2 start/stop", "chw-pump-pri", exec_order=19))
        programs.append(ProgramDef(17, "CHW-PCHWP-LEAD-LAG-PRG", "CHW-PRG17-PCHWP-LEAD-LAG.bas", "", True,
            "Primary pump lead/lag rotation", "chw-pump-pri", exec_order=17))
        schedules.append(ScheduleDef(3, "{device-name}-PCHWP-LEAD-SCHED",
            "Pump 1", [f"Pump {n}" for n in range(1, num_pumps + 1)], 10,
            "Primary pump lead rotation schedule"))
        if num_pumps >= 3:
            programs.append(ProgramDef(20, "CHW-PCHWP3-PRG", "CHW-PRG20-PCHWP3.bas", "", True,
                "Primary pump 3 start/stop", "chw-pump-pri", exec_order=20))
        if num_pumps >= 4:
            programs.append(ProgramDef(21, "CHW-PCHWP4-PRG", "CHW-PRG21-PCHWP4.bas", "", True,
                "Primary pump 4 start/stop", "chw-pump-pri", exec_order=21))

    return Module(
        id="chw-pump-pri",
        name=f"Primary CHW Pumps ({num_pumps})",
        category="chw-pump-pri",
        description=f"{num_pumps} constant speed primary CHW pump(s) with lead/lag",
        requires=["chw-core"],
        mutually_exclusive_group="chw-pump-pri",
        inputs=inputs, outputs=outputs, values=values,
        loops=[], tables=[], programs=programs, schedules=schedules,
        system_groups=[
            SystemGroupDef("{device-name}-PRIMARY-PUMP-CTRL",
                "Primary pump status, lead/lag, failures"),
        ],
        soo_paragraph=f"""Primary CHW pumps ({num_pumps}) are constant speed. Each pump starts when
CHW system is enabled and the pump is designated as lead. Proof of flow via
status contact with configurable delay. Failure detected via proof timeout.
{'Lead/lag rotation via schedule with automatic failover on lead pump failure.' if num_pumps > 1 else 'Single pump operation.'}""",
    )


def build_pump_sec(num_pumps=2, num_dp_sensors=2):
    """Secondary CHW pumps — VFD with DP control, lag staging.

    Args:
        num_pumps: 1-4 secondary pumps
        num_dp_sensors: 1 or 2 DP sensors (default 2, averaged)
    """
    inputs = []
    outputs = []
    values = []
    programs = []
    schedules = []

    for n in range(1, num_pumps + 1):
        outputs.append(OutputPoint(
            _SEC_SS_BASE + n - 1, f"SCHWP{n}-S/S", "BO", "Stop/Start",
            f"Secondary CHW Pump {n} Start/Stop"))
        inputs.append(InputPoint(
            _SEC_STS_BASE + n - 1, f"SCHWP{n}-STS", "BI", "Off/On",
            f"Secondary CHW Pump {n} Status"))
        outputs.append(OutputPoint(
            _SEC_SPD_BASE + n - 1, f"SCHWP{n}-SPEED", "AO", "0.0 ->100%",
            f"Secondary CHW Pump {n} VFD Speed", 2.0, 10.0))
        # Per pump: 4 values each starting at 171
        base = 171 + (n - 1) * 4
        values.append(ValuePoint(base,     f"SCHWP{n}-FAIL", "BV", False,
            f"Secondary Pump {n} Failure"))
        values.append(ValuePoint(base + 1, f"SCHWP{n}-OOS", "BV", False,
            f"Secondary Pump {n} Out of Service"))
        values.append(ValuePoint(base + 2, f"SCHWP{n}-RUNTIME", "AV", 0.0,
            f"Secondary Pump {n} Runtime", "Hrs"))
        values.append(ValuePoint(base + 3, f"SCHWP{n}-S", "BV", False,
            f"Secondary Pump {n} Status (from .bas)"))

    # DP sensors
    inputs.append(InputPoint(
        _DP_SENSOR_BASE, "CHW-PRESS1", "AI", "0 ->100% (0-5V)",
        "CHW Differential Pressure 1", "PSI"))
    if num_dp_sensors >= 2:
        inputs.append(InputPoint(
            _DP_SENSOR_BASE + 1, "CHW-PRESS2", "AI", "0 ->100% (0-5V)",
            "CHW Differential Pressure 2", "PSI"))

    # System values starting at 185
    values.append(ValuePoint(185, "ANY-SCHWP-ON", "BV", False, "Any Secondary Pump Running"))
    values.append(ValuePoint(186, "AVG-DP", "AV", 0.0, "Average Differential Pressure", "PSI"))
    values.append(ValuePoint(187, "CHWS-DP-SP", "AV", 12.0, "CHW DP Setpoint", "PSI"))
    values.append(ValuePoint(188, "SCHWP-MIN-SPEED", "AV", 30.0, "Secondary Pump Min Speed", "%"))
    values.append(ValuePoint(189, "SCHWP-MAX-SPEED", "AV", 100.0, "Secondary Pump Max Speed", "%"))
    values.append(ValuePoint(190, "SCHWP-LAG-START-SP", "AV", 8.0,
        "Lag Pump Start DP Threshold", "PSI"))
    values.append(ValuePoint(191, "SCHWP-LAG-STOP-SP", "AV", 14.0,
        "Lag Pump Stop DP Threshold", "PSI"))
    values.append(ValuePoint(192, "SCHWP-STOP-DELAY", "AV", 30.0,
        "Secondary Pump Stop Delay", "Sec"))
    values.append(ValuePoint(193, "SCHWP-RAMP-RATE", "AV", 3.33,
        "Secondary Pump Ramp Rate", ""))
    values.append(ValuePoint(194, "SCHWP-ROTATION-HOLD", "AV", 168.0,
        "Min Hours Before Secondary Pump Rotation", "Hrs"))
    values.append(ValuePoint(195, "SCHWP-LAG-START-DLY", "AV", 5.0,
        "Lag Pump Start Delay", "Min"))
    values.append(ValuePoint(196, "SCHWP-LAG-STOP-DLY", "AV", 5.0,
        "Lag Pump Stop Delay", "Min"))

    if num_pumps > 1:
        values.append(ValuePoint(197, "LEAD-SCHWP", "AV", 1.0,
            "Lead Secondary Pump Number", "#"))
        values.append(ValuePoint(198, "LEAD-SCHWP-SS", "BV", False,
            "Lead Secondary Pump Start/Stop"))
        values.append(ValuePoint(199, "LAG-SCHWP-SS", "BV", False,
            "Lag Secondary Pump Start/Stop"))
        values.append(ValuePoint(200, "LEAD-SCHWP-FAIL", "BV", False,
            "Lead Secondary Pump Failure"))

    # DP control loop
    loops = [
        LoopDef(1, "CHW-DP-LOOP", "AVG-DP", "CHWS-DP-SP", "SCHWP1-SPEED",
                5.0, 60.0, action="direct", description="CHW Secondary DP Control"),
    ]

    # Programs
    programs.append(ProgramDef(22, "CHW-SCHWP1-PRG", "CHW-PRG22-SCHWP1.bas", "", True,
        "Secondary pump 1 start/stop", "chw-pump-sec", exec_order=22))
    programs.append(ProgramDef(24, "CHW-SCHWP1-SPEED-PRG", "CHW-PRG24-SCHWP1-SPEED.bas", "", True,
        "Secondary pump 1 VFD speed from DP loop", "chw-pump-sec", exec_order=24))

    if num_pumps > 1:
        programs.append(ProgramDef(23, "CHW-SCHWP2-PRG", "CHW-PRG23-SCHWP2.bas", "", True,
            "Secondary pump 2 start/stop", "chw-pump-sec", exec_order=23))
        programs.append(ProgramDef(25, "CHW-SCHWP2-SPEED-PRG", "CHW-PRG25-SCHWP2-SPEED.bas", "", True,
            "Secondary pump 2 VFD speed from DP loop", "chw-pump-sec", exec_order=25))
        programs.append(ProgramDef(26, "CHW-SCHWP-LEAD-LAG-PRG", "CHW-PRG26-SCHWP-LEAD-LAG.bas", "", True,
            "Secondary pump lead/lag rotation", "chw-pump-sec", exec_order=26))
        schedules.append(ScheduleDef(4, "{device-name}-SCHWP-LEAD-SCHED",
            "Pump 1", [f"Pump {n}" for n in range(1, num_pumps + 1)], 10,
            "Secondary pump lead rotation schedule"))

    programs.append(ProgramDef(27, "CHW-SCHWP-LAG-PRG", "CHW-PRG27-SCHWP-LAG.bas", "", True,
        "Secondary pump lag staging logic", "chw-pump-sec", exec_order=27))

    return Module(
        id="chw-pump-sec",
        name=f"Secondary CHW Pumps ({num_pumps}, {num_dp_sensors}DP)",
        category="chw-pump-sec",
        description=f"{num_pumps} VFD secondary CHW pump(s) with DP control ({num_dp_sensors} sensor{'s' if num_dp_sensors > 1 else ''})",
        requires=["chw-core"],
        mutually_exclusive_group="chw-pump-sec",
        inputs=inputs, outputs=outputs, values=values,
        loops=loops, tables=[], programs=programs, schedules=schedules,
        system_groups=[
            SystemGroupDef("{device-name}-SECONDARY-PUMP-CTRL",
                "Secondary pump speed, DP, lead/lag, lag staging"),
        ],
        soo_paragraph=f"""Secondary CHW pumps ({num_pumps}) are VFD-controlled with differential pressure
feedback from {num_dp_sensors} sensor{'s averaged' if num_dp_sensors > 1 else ''}. DP PID loop modulates pump speed between
configurable min/max. Lag pump stages on when DP drops below lag start threshold,
stages off when DP exceeds lag stop threshold. {'Lead/lag rotation via schedule.' if num_pumps > 1 else ''}""",
    )


def build_cdwp(num_pumps=2):
    """Condenser water pumps — constant speed, lead/lag.
    Tower plants only.

    Args:
        num_pumps: 1-4 CW pumps
    """
    inputs = []
    outputs = []
    values = []
    programs = []
    schedules = []

    for n in range(1, num_pumps + 1):
        outputs.append(OutputPoint(
            _CW_SS_BASE + n - 1, f"CDWP{n}-S/S", "BO", "Stop/Start",
            f"Condenser Water Pump {n} Start/Stop"))
        inputs.append(InputPoint(
            _CW_STS_BASE + n - 1, f"CDWP{n}-STS", "BI", "Off/On",
            f"Condenser Water Pump {n} Status"))
        # Per pump: 3 values each starting at 201
        base = 201 + (n - 1) * 3
        values.append(ValuePoint(base,     f"CDWP{n}-FAIL", "BV", False,
            f"CW Pump {n} Failure"))
        values.append(ValuePoint(base + 1, f"CDWP{n}-OOS", "BV", False,
            f"CW Pump {n} Out of Service"))
        values.append(ValuePoint(base + 2, f"CDWP{n}-RUNTIME", "AV", 0.0,
            f"CW Pump {n} Runtime", "Hrs"))

    values.append(ValuePoint(213, "ANY-CDWP-ON", "BV", False, "Any CW Pump Running"))
    values.append(ValuePoint(214, "CDWP-STOP-DELAY", "AV", 30.0, "CW Pump Stop Delay", "Sec"))

    if num_pumps > 1:
        values.append(ValuePoint(215, "LEAD-CDWP", "AV", 1.0, "Lead CW Pump Number", "#"))
        values.append(ValuePoint(216, "LEAD-CDWP-SS", "BV", False, "Lead CW Pump Start/Stop"))
        values.append(ValuePoint(217, "LAG-CDWP-SS", "BV", False, "Lag CW Pump Start/Stop"))
        values.append(ValuePoint(218, "LEAD-CDWP-FAIL", "BV", False, "Lead CW Pump Failure"))

    programs.append(ProgramDef(30, "CHW-CDWP1-PRG", "CHW-PRG30-CDWP1.bas", "", True,
        "CW pump 1 start/stop", "chw-cdwp", exec_order=30))
    if num_pumps > 1:
        programs.append(ProgramDef(31, "CHW-CDWP2-PRG", "CHW-PRG31-CDWP2.bas", "", True,
            "CW pump 2 start/stop", "chw-cdwp", exec_order=31))
        programs.append(ProgramDef(32, "CHW-CDWP-LEAD-LAG-PRG", "CHW-PRG32-CDWP-LEAD-LAG.bas", "", True,
            "CW pump lead/lag rotation", "chw-cdwp", exec_order=32))
    if num_pumps >= 3:
        programs.append(ProgramDef(33, "CHW-CDWP3-PRG", "CHW-PRG33-CDWP3.bas", "", True,
            "CW pump 3 start/stop", "chw-cdwp", exec_order=33))

    return Module(
        id="chw-cdwp",
        name=f"CW Pumps ({num_pumps})",
        category="chw-cw-pump",
        description=f"{num_pumps} constant speed condenser water pump(s) with lead/lag",
        requires=["chw-core"],
        mutually_exclusive_group="chw-cw-pump",
        inputs=inputs, outputs=outputs, values=values,
        loops=[], tables=[], programs=programs, schedules=schedules,
        system_groups=[
            SystemGroupDef("{device-name}-CW-PUMP-CTRL",
                "CW pump status, lead/lag, failures"),
        ],
        soo_paragraph=f"""Condenser water pumps ({num_pumps}) are constant speed. Each CW pump starts
paired with its chiller when the chiller is enabled. {'Lead/lag rotation follows chiller lead/lag.' if num_pumps > 1 else ''}
Proof of flow via status contact. Failure detected via proof timeout.""",
    )
