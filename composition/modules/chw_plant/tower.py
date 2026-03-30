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

_CT_SS_BASE = 21       # BO: CT1-S/S at OUT21, CT2 at OUT22
_CT_STS_BASE = 28      # BI: CT1-STS at IN28, CT2 at IN29
_CT_SPD_BASE = 23      # AO: CT1-SPD at OUT23, CT2 at OUT24
_CDW_TEMP_BASE = 30    # AI: CDW-ENT-T at IN30, CDW-LVG-T at IN31
_CT_BYP_ROW = 25       # AO: CT-BYP-VLV at OUT25


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

    # Per-tower I/O
    for n in range(1, num_towers + 1):
        outputs.append(OutputPoint(
            _CT_SS_BASE + n - 1, f"CT{n}-S/S", "BO", "Stop/Start",
            f"Cooling Tower {n} Fan Start/Stop"))
        inputs.append(InputPoint(
            _CT_STS_BASE + n - 1, f"CT{n}-STS", "BI", "Off/On",
            f"Cooling Tower {n} Fan Status"))
        outputs.append(OutputPoint(
            _CT_SPD_BASE + n - 1, f"CT{n}-SPD", "AO", "0.0 ->100%",
            f"Cooling Tower {n} Fan VFD Speed", 2.0, 10.0))
        values.append(ValuePoint(121 + (n - 1) * 3, f"CT{n}-FAIL", "BV", False,
            f"Cooling Tower {n} Fan Failure"))
        values.append(ValuePoint(122 + (n - 1) * 3, f"CT{n}-IN-SERVICE", "BV", True,
            f"Cooling Tower {n} In Service"))
        values.append(ValuePoint(123 + (n - 1) * 3, f"CT{n}-RUNTIME", "AV", 0.0,
            f"Cooling Tower {n} Runtime", "Hrs"))

    # System values
    # CDWS-T-SP: Condenser water LEAVING tower temp setpoint.
    # Tower fan loop modulates fan speed to hit this target.
    # Resets based on OA wet bulb + approach temperature.
    values.append(ValuePoint(131, "CDWS-T-SP", "AV", 78.0,
        "Condenser Water Supply Temp Setpoint (leaving tower)", "°F"))

    # Wet-bulb approach reset parameters
    # OA-WET-BULB is calculated in the tower program from OAT + OAH
    values.append(ValuePoint(132, "OA-WET-BULB", "AV", 0.0,
        "Calculated OA Wet Bulb Temperature", "°F"))
    values.append(ValuePoint(133, "CFG-CT-APPROACH", "AV", 7.0,
        "Min Approach Temp Above Wet Bulb", "°F"))
    values.append(ValuePoint(134, "CFG-CT-MAX-CDWS-SP", "AV", 85.0,
        "Max Condenser Water Supply Setpoint", "°F"))
    values.append(ValuePoint(135, "CFG-CT-MIN-CDWS-SP", "AV", 65.0,
        "Min Condenser Water Supply Setpoint", "°F"))

    # Tower timing
    values.append(ValuePoint(136, "CT-MIN-ON", "AV", 5.0, "Tower Fan Min On Time", "Min"))
    values.append(ValuePoint(137, "CT-MIN-OFF", "AV", 5.0, "Tower Fan Min Off Time", "Min"))
    values.append(ValuePoint(138, "CT-FAN-MIN-SPEED", "AV", 20.0, "Tower Fan Min Speed", "%"))
    values.append(ValuePoint(139, "CT-FAN-MAX-SPEED", "AV", 100.0, "Tower Fan Max Speed", "%"))

    if num_towers > 1:
        values.append(ValuePoint(140, "LEAD-CT", "AV", 1.0, "Lead Tower Number", "#"))
        values.append(ValuePoint(141, "LEAD-CT-SS", "BV", False, "Lead Tower Start/Stop"))
        values.append(ValuePoint(142, "LEAD-CT-FAIL", "BV", False, "Lead Tower Failure"))

    # Condenser water supply temp loop — fan speed controls leaving tower temp
    loops = [
        LoopDef(2, "CDWS-T-LOOP", "CDW-LVG-T", "CDWS-T-SP", "CT1-SPD",
                4.0, 60.0, "direct",
                "Condenser water supply temp — fan speed (higher speed = cooler water)"),
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
            ValuePoint(143, "CT-BYPASS-SPT", "AV", 65.0,
                "Min CW Entering Chiller Temp (bypass opens below this)", "°F"),
        ],

        loops=[
            LoopDef(3, "CT-BYP-LOOP", "CDW-ENT-T", "CT-BYPASS-SPT", "CT-BYP-VLV",
                    10.0, 40.0, "reverse",
                    "CW bypass — valve opens when entering CW temp drops below setpoint"),
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
