"""
CHW-PLANT Optional Modules — Bypass Valve, Isolation Valves, Makeup Water, AHU Integration
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)

# I/O rows for optional modules
_BYP_VLV_AO_ROW = 26    # AO: CHW-BYP-VLV at OUT26
_BYP_T_AI_ROW = 32      # AI: CHW-BYP-T at IN32
_ISO_CHW_BO_BASE = 27   # BO: CHLR1-CHW-ISO at OUT27, CHLR2 at OUT28
_ISO_CHW_ES_BASE = 33   # BI: CHLR1-CHW-ISO-ES at IN33, CHLR2 at IN34
_ISO_CDW_BO_BASE = 29   # BO: CHLR1-CDW-ISO at OUT29 (tower only)
_ISO_CDW_ES_BASE = 35   # BI: CHLR1-CDW-ISO-ES at IN35 (tower only)
_MAKEUP_AI_ROW = 37      # AI: MAKEUP-WTR-FLOW at IN37


def build_bypass_valve():
    """CHW header bypass valve — decoupler/bypass on secondary header.

    Modulates based on secondary CHW supply temp deviation.
    Analogous to hw-mixing-valve in HW plant.
    """
    return Module(
        id="chw-bypass-valve",
        name="CHW Bypass Valve",
        category="chw-optional",
        description="CHW header bypass valve for secondary loop temperature control",
        requires=["chw-core"],

        inputs=[
            InputPoint(_BYP_T_AI_ROW, "CHW-BYP-T", "AI", "10K -40 ->250",
                "CHW Bypass Temperature", "°F"),
        ],

        outputs=[
            OutputPoint(_BYP_VLV_AO_ROW, "CHW-BYP-VLV", "AO", "0.0 ->100%",
                "CHW Bypass Valve", 2.0, 10.0),
        ],

        values=[
            ValuePoint(125, "CHW-BYP-SP", "AV", 44.0,
                "CHW Bypass Valve Setpoint", "°F"),
        ],

        loops=[
            LoopDef(4, "CHW-BYP-LOOP", "CHW-BYP-T", "CHW-BYP-SP", "CHW-BYP-VLV",
                    10.0, 40.0, action="reverse",
                    description="CHW bypass valve PID — valve opens when bypass temp rises above setpoint"),
        ],

        tables=[],

        programs=[
            ProgramDef(42, "CHW-BYP-VLV-PRG", "CHW-PRG42-BYP-VLV.bas", "", True,
                "CHW bypass valve control", "chw-bypass-valve", exec_order=42),
        ],

        schedules=[],

        system_groups=[],

        soo_paragraph="""The CHW bypass valve modulates to maintain secondary loop supply
temperature at setpoint. When secondary loop flow exceeds primary loop flow, excess
water recirculates through the bypass. The valve is reverse-acting — opens as
temperature rises above setpoint to increase bypass flow.""",
    )


def build_iso_valves(num_chillers=2, has_cdw_side=False):
    """Chiller isolation valves — CHW side always, CDW side for tower plants.

    Args:
        num_chillers: 1-4 chillers
        has_cdw_side: True for water-cooled plants (adds CDW isolation valves)
    """
    inputs = []
    outputs = []
    values = []

    for n in range(1, num_chillers + 1):
        # CHW side isolation (always)
        outputs.append(OutputPoint(
            _ISO_CHW_BO_BASE + n - 1, f"CHLR{n}-CHW-ISO", "BO", "Open/Close",
            f"Chiller {n} CHW Isolation Valve"))
        inputs.append(InputPoint(
            _ISO_CHW_ES_BASE + n - 1, f"CHLR{n}-CHW-ISO-ES", "BI", "Open/Closed",
            f"Chiller {n} CHW Isolation Valve End Switch"))

        # CDW side isolation (tower plants only)
        if has_cdw_side:
            outputs.append(OutputPoint(
                _ISO_CDW_BO_BASE + n - 1, f"CHLR{n}-CDW-ISO", "BO", "Open/Close",
                f"Chiller {n} CDW Isolation Valve"))
            inputs.append(InputPoint(
                _ISO_CDW_ES_BASE + n - 1, f"CHLR{n}-CDW-ISO-ES", "BI", "Open/Closed",
                f"Chiller {n} CDW Isolation Valve End Switch"))

    values.append(ValuePoint(126, "ISO-VLV-OPEN-DLY", "AV", 30.0,
        "Isolation Valve Open Delay", "Sec"))

    return Module(
        id="chw-iso-valves",
        name=f"Isolation Valves ({num_chillers}{'+ CDW' if has_cdw_side else ''})",
        category="chw-optional",
        description=f"Chiller isolation valves for {num_chillers} chiller(s)" +
                    (" with CDW side" if has_cdw_side else ""),
        requires=["chw-core", "chw-chlr"],

        inputs=inputs, outputs=outputs, values=values,
        loops=[], programs=[
            ProgramDef(40, "CHW-ISO-VLV-PRG", "CHW-PRG40-ISO-VLV.bas", "", True,
                "Chiller isolation valve sequencing", "chw-iso-valves", exec_order=40),
        ],
        tables=[
            TableDef(1, "ISO-VLV-POS", "Position", "Command",
                [[0, 0], [50, 0], [51, 1], [100, 1]],
                "Isolation valve position lookup"),
        ],
        schedules=[],

        system_groups=[],

        soo_paragraph=f"""Chiller isolation valves open before chiller enable and close after
chiller shutdown. Valve open is verified via end switch with configurable delay.
Chiller will not enable until isolation valve is confirmed open.
{'Both CHW and CDW side isolation valves are sequenced together.' if has_cdw_side else ''}""",
    )


def build_makeup_water():
    """Makeup water flow monitoring and totalization."""
    return Module(
        id="chw-makeup-water",
        name="Makeup Water Monitoring",
        category="chw-optional",
        description="Makeup water flow monitoring and totalization",
        requires=["chw-core"],

        inputs=[
            InputPoint(_MAKEUP_AI_ROW, "MAKEUP-WTR-FLOW", "AI", "0 ->100% (0-5V)",
                "Makeup Water Flow Rate", "GPM"),
        ],

        outputs=[],

        values=[
            ValuePoint(131, "MAKEUP-WTR-TTL", "AV", 0.0, "Makeup Water Total", "Gal"),
            ValuePoint(132, "MAKEUP-WTR-ALARM", "BV", False, "Excessive Makeup Water Alarm"),
            ValuePoint(133, "MAKEUP-WTR-HI-SP", "AV", 50.0, "Makeup Water High Flow SP", "GPM"),
            ValuePoint(134, "MAKEUP-WTR-RESET", "BV", False, "Reset Makeup Water Total"),
        ],

        loops=[],

        tables=[
            TableDef(2, "MAKEUP-WTR-TBL", "Volts", "GPM",
                [[0.0, 0.0], [5.0, 50.0], [10.0, 100.0]],
                "Makeup water flow sensor scaling"),
        ],

        programs=[
            ProgramDef(43, "CHW-MAKEUP-WTR-PRG", "CHW-PRG43-MAKEUP-WTR.bas", "", True,
                "Makeup water monitoring and totalization", "chw-makeup-water", exec_order=43),
        ],

        schedules=[],
        system_groups=[],

        soo_paragraph="""Makeup water flow is monitored and totalized. High flow alarm activates
when flow rate exceeds setpoint, indicating a potential system leak. Total can be
reset via the MAKEUP-WTR-RESET command.""",
    )


def build_ahu_integration(num_ahus=2):
    """AHU zone data integration — network reads from served AHUs.

    Args:
        num_ahus: 1-8 AHUs to integrate
    """
    values = []
    programs = []

    # System-level aggregated values
    values.append(ValuePoint(139, "SNOW-DAY", "BV", False, "Snow Day Override"))
    values.append(ValuePoint(140, "TOTAL-CLG-REQS", "AV", 0.0, "Total Cooling Requests", "#"))

    # Per-AHU zone data (base = 141 + (n-1)*10)
    for n in range(1, num_ahus + 1):
        base = 141 + (n - 1) * 10
        values.extend([
            ValuePoint(base + 0, f"AHU{n}-NET-OCC-CMD", "BV", False,
                f"AHU {n} Occupancy Command"),
            ValuePoint(base + 1, f"AHU{n}-NET-OK", "BV", False,
                f"AHU {n} Network OK"),
            ValuePoint(base + 2, f"AHU{n}-COOL-MODE", "BV", False,
                f"AHU {n} Cooling Mode"),
            ValuePoint(base + 3, f"AHU{n}-HIGH-RMT", "AV", 72.0,
                f"AHU {n} Highest Room Temp", "°F"),
            ValuePoint(base + 4, f"AHU{n}-AVG-RMT", "AV", 70.0,
                f"AHU {n} Average Room Temp", "°F"),
            ValuePoint(base + 5, f"AHU{n}-LOW-RMT", "AV", 68.0,
                f"AHU {n} Lowest Room Temp", "°F"),
            ValuePoint(base + 6, f"AHU{n}-CLG-REQS", "AV", 0.0,
                f"AHU {n} Cooling Requests", "#"),
            ValuePoint(base + 7, f"AHU{n}-CLG-DMD", "AV", 0.0,
                f"AHU {n} Cooling Demand", "%"),
            ValuePoint(base + 8, f"AHU{n}-CHV-POS", "AV", 0.0,
                f"AHU {n} CHW Valve Position", "%"),
        ])

    programs.append(ProgramDef(45, "CHW-NET-DATA-PRG", "CHW-PRG45-NET-DATA.bas", "", True,
        "Network data reads from AHU controllers", "chw-ahu-integ", exec_order=45))
    for n in range(1, num_ahus + 1):
        programs.append(ProgramDef(45 + n, f"CHW-AHU{n}-CFG-PRG",
            f"CHW-PRG{45 + n}-AHU{n}-CFG.bas", "", True,
            f"AHU {n} configuration and data exchange", "chw-ahu-integ",
            exec_order=45 + n))

    return Module(
        id="chw-ahu-integ",
        name=f"AHU Integration ({num_ahus})",
        category="chw-optional",
        description=f"Network integration with {num_ahus} AHU(s) for valve feedback and zone data",
        requires=["chw-core"],

        inputs=[], outputs=[], values=values,
        loops=[], tables=[], programs=programs, schedules=[],

        system_groups=[
            SystemGroupDef("{device-name}-AHU-DATA",
                "AHU zone data, cooling requests, valve positions"),
        ],

        soo_paragraph=f"""The controller integrates with {num_ahus} air handling unit(s) via
BACnet network reads. Zone data includes room temperatures, cooling demand,
and CHW valve positions. Aggregated valve position data feeds back to the CHW
supply temperature reset logic in the core module. When AHU integration is
active, NET-CHV-POS-MIN/MAX/AVG are populated from real-time valve data.""",
    )
