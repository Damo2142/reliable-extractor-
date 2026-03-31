"""
CHW-PLANT Tower Modules — Cooling Tower Fan + Bypass Valve

Tower:  VFD fan speed control via condenser water supply temp loop.
        Wet-bulb approach reset on CDWS-T-SP.
Bypass: CW bypass valve prevents condenser water from going too cold.
        Separate setpoint from tower fan control.
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)

# I/O layout — follows CW pumps, supports up to 4 towers
_CT_SS_BASE = 21       # BO: CT1-FAN-S/S at OUT21-24 (4 slots)
_CT_STS_BASE = 32      # BI: CT1-FAN-STS at IN32-35 (4 slots)
_CT_SPD_BASE = 25      # AO: CT1-FAN-SPEED at OUT25-28 (4 slots)
_CDW_TEMP_BASE = 36    # AI: CDW-ENT-T at IN36, CDW-LVG-T at IN37
_CT_BYP_ROW = 29       # AO: CT-BYP-VLV at OUT29


def build_tower(num_towers=2):
    """Cooling tower fan control with wet-bulb approach reset.

    Args:
        num_towers: 1-4 cooling towers
    """
    inputs = []
    outputs = []
    values = []
    programs = []
    schedules = []

    # Condenser water temps (system-level, not per-tower)
    inputs.append(InputPoint(
        _CDW_TEMP_BASE, "CDW-ENT-T", "AI", "10K -40 ->250",
        "Condenser Water Entering Temperature", "°F"))
    inputs.append(InputPoint(
        _CDW_TEMP_BASE + 1, "CDW-LVG-T", "AI", "10K -40 ->250",
        "Condenser Water Leaving Temperature", "°F"))

    # Per-tower I/O — renamed to match .bas (CT{N}-FAN-S/S, CT{N}-FAN-STS, CT{N}-FAN-SPEED)
    for n in range(1, num_towers + 1):
        outputs.append(OutputPoint(
            _CT_SS_BASE + n - 1, f"CT{n}-FAN-S/S", "BO", "Stop/Start",
            f"Cooling Tower {n} Fan Start/Stop"))
        inputs.append(InputPoint(
            _CT_STS_BASE + n - 1, f"CT{n}-FAN-STS", "BI", "Off/On",
            f"Cooling Tower {n} Fan Status"))
        outputs.append(OutputPoint(
            _CT_SPD_BASE + n - 1, f"CT{n}-FAN-SPEED", "AO", "0.0 ->100%",
            f"Cooling Tower {n} Fan VFD Speed", 2.0, 10.0))
        # Per tower: 4 values each starting at 221
        base = 221 + (n - 1) * 4
        values.append(ValuePoint(base,     f"CT{n}-FAIL", "BV", False,
            f"Cooling Tower {n} Fan Failure"))
        values.append(ValuePoint(base + 1, f"CT{n}-IN-SERVICE", "BV", True,
            f"Cooling Tower {n} In Service"))
        values.append(ValuePoint(base + 2, f"CT{n}-RUNTIME", "AV", 0.0,
            f"Cooling Tower {n} Runtime", "Hrs"))
        values.append(ValuePoint(base + 3, f"CT{n}-OOS", "BV", False,
            f"Cooling Tower {n} Out of Service"))

    # CDWS-T alias AV (referenced by .bas PRG34 as measured value)
    values.append(ValuePoint(233, "CDWS-T", "AV", 0.0,
        "Condenser Water Supply Temp (calculated/alias)", "°F"))

    # System values starting at 235
    values.append(ValuePoint(235, "CDWS-T-SP", "AV", 78.0,
        "Condenser Water Supply Temp Setpoint (leaving tower)", "°F"))
    values.append(ValuePoint(236, "OA-WET-BULB", "AV", 0.0,
        "Calculated OA Wet Bulb Temperature", "°F"))
    values.append(ValuePoint(237, "CFG-CT-APPROACH", "AV", 7.0,
        "Min Approach Temp Above Wet Bulb", "°F"))
    values.append(ValuePoint(238, "CFG-CT-MAX-CDWS-SP", "AV", 85.0,
        "Max Condenser Water Supply Setpoint", "°F"))
    values.append(ValuePoint(239, "CFG-CT-MIN-CDWS-SP", "AV", 65.0,
        "Min Condenser Water Supply Setpoint", "°F"))

    # Tower timing
    values.append(ValuePoint(240, "CT-MIN-ON", "AV", 5.0, "Tower Fan Min On Time", "Min"))
    values.append(ValuePoint(241, "CT-MIN-OFF", "AV", 5.0, "Tower Fan Min Off Time", "Min"))
    values.append(ValuePoint(242, "CT-FAN-MIN-SPEED", "AV", 20.0, "Tower Fan Min Speed", "%"))
    values.append(ValuePoint(243, "CT-FAN-MAX-SPEED", "AV", 100.0, "Tower Fan Max Speed", "%"))
    values.append(ValuePoint(244, "CT-FAN-RAMP-RATE", "AV", 3.33, "Tower Fan Ramp Rate", ""))
    values.append(ValuePoint(245, "CT-ROTATION-HOLD", "AV", 168.0,
        "Min Hours Before Tower Rotation", "Hrs"))

    if num_towers > 1:
        values.append(ValuePoint(246, "LEAD-CT", "AV", 1.0, "Lead Tower Number", "#"))
        values.append(ValuePoint(247, "LEAD-CT-SS", "BV", False, "Lead Tower Start/Stop"))
        values.append(ValuePoint(248, "LEAD-CT-FAIL", "BV", False, "Lead Tower Failure"))
        values.append(ValuePoint(249, "LAG-CT-SS", "BV", False, "Lag Tower Start/Stop"))
        values.append(ValuePoint(250, "ANY-CT-ON", "BV", False, "Any Tower Fan Running"))

    # Condenser water supply temp loop — fan speed controls leaving tower temp
    loops = [
        LoopDef(2, "CDWS-T-LOOP", "CDW-LVG-T", "CDWS-T-SP", "CT1-FAN-SPEED",
                4.0, 60.0, action="direct",
                description="Condenser water supply temp — fan speed (higher speed = cooler water)"),
    ]

    programs.append(ProgramDef(34, "CHW-CT-CTRL-PRG", "CHW-PRG34-CT-CTRL.bas", "", True,
        "Tower fan control, wet-bulb approach reset, staging", "chw-tower", exec_order=34))
    if num_towers > 1:
        programs.append(ProgramDef(35, "CHW-CT-LEAD-LAG-PRG", "CHW-PRG35-CT-LEAD-LAG.bas", "", True,
            "Tower lead/lag rotation", "chw-tower", exec_order=35))
        schedules.append(ScheduleDef(5, "{device-name}-CT-LEAD-SCHED",
            "Tower 1", [f"Tower {n}" for n in range(1, num_towers + 1)], 10,
            "Cooling tower lead rotation schedule"))

    return Module(
        id="chw-tower",
        name=f"Cooling Towers ({num_towers})",
        category="chw-tower",
        description=f"{num_towers} cooling tower(s) with VFD fan and wet-bulb approach reset",
        requires=["chw-core", "chw-cdwp"],
        mutually_exclusive_group="chw-tower",
        inputs=inputs, outputs=outputs, values=values,
        loops=loops, tables=[], programs=programs, schedules=schedules,
        system_groups=[
            SystemGroupDef("{device-name}-COOLING-TOWER-CTRL",
                "Tower fan speed, CW temps, wet-bulb reset, staging"),
        ],
        soo_paragraph=f"""Cooling tower fan(s) ({num_towers}) are VFD-controlled. Fan speed modulates
via PID loop to maintain condenser water leaving temperature at setpoint.
CDWS-T-SP resets based on outdoor wet bulb temperature: setpoint = OA-WET-BULB +
CFG-CT-APPROACH, clamped between CFG-CT-MIN-CDWS-SP and CFG-CT-MAX-CDWS-SP.
{'Lead/lag rotation via schedule. Lag tower stages with chiller staging.' if num_towers > 1 else ''}
Tower fan minimum speed is configurable to prevent icing in cold weather.""",
    )


def build_tower_bypass():
    """Cooling tower CW bypass valve.

    Prevents condenser water from getting too cold for the chiller.
    CT-BYPASS-SPT is the MINIMUM CW temp entering the chiller condenser.
    This is a separate setpoint from CDWS-T-SP (tower leaving temp).

    CDWS-T-SP = target leaving tower water temp (fan loop drives DOWN toward this)
    CT-BYPASS-SPT = minimum entering chiller CW temp (bypass valve prevents going BELOW this)
    """
    return Module(
        id="chw-tower-bypass",
        name="Tower CW Bypass Valve",
        category="chw-tower-opt",
        description="Condenser water bypass valve — prevents CW from going too cold for chiller",
        requires=["chw-tower"],

        inputs=[],

        outputs=[
            OutputPoint(_CT_BYP_ROW, "CT-BYP-VLV", "AO", "0.0 ->100%",
                "Tower CW Bypass Valve", 2.0, 10.0),
        ],

        values=[
            # CT-BYPASS-SPT: Min entering CW temp at chiller condenser.
            # NOT the same as CDWS-T-SP (leaving tower temp).
            # Bypass opens when CW entering chiller drops below this setpoint.
            ValuePoint(251, "CT-BYPASS-SPT", "AV", 65.0,
                "Min CW Entering Chiller Temp (bypass opens below this)", "°F"),
        ],

        loops=[
            LoopDef(3, "CT-BYP-LOOP", "CDW-ENT-T", "CT-BYPASS-SPT", "CT-BYP-VLV",
                    10.0, 40.0, action="reverse",
                    description="CW bypass — valve opens when entering CW temp drops below setpoint"),
        ],

        tables=[],

        programs=[
            ProgramDef(39, "CHW-CT-BYP-VLV-PRG", "CHW-PRG39-CT-BYP-VLV.bas", "", True,
                "Tower CW bypass valve control", "chw-tower-bypass", exec_order=39),
        ],

        schedules=[],
        system_groups=[],

        soo_paragraph="""The condenser water bypass valve prevents condenser water entering the
chiller from dropping below the minimum temperature setpoint (CT-BYPASS-SPT, default
65°F). When entering condenser water temperature (CDW-ENT-T) approaches the setpoint,
the bypass valve modulates open to mix warm return water with cold tower water.
This is independent of the tower fan CDWS-T-SP which controls leaving tower temp.""",
    )
