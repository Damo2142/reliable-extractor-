"""
Dual Duct AHU Modules — Hot deck + Cold deck

Dual duct AHUs have two parallel air paths:
- Hot deck: heated air (HW valve, electric, or gas)
- Cold deck: cooled air (CHW valve or DX)

Downstream dual-duct mixing boxes blend hot and cold air per zone.
Each deck has its own SAT sensor and control loop.
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, ProgramDef, SystemGroupDef
)


def build_dd_cold_chw():
    """Dual duct cold deck — CHW cooling"""
    return Module(
        id="dd-cold-chw",
        name="DD Cold Deck CHW",
        category="cooling",
        description="Dual duct cold deck — CHW cooling coil with SAT control",

        inputs=[
            InputPoint(6, "COLD-DECK-T", "AI", "10K -40 ->250", "Cold Deck Temperature", "°F"),
            InputPoint(33, "CHWC-SUPW-T", "AI", "10K -40 ->250", "CHW Coil Supply Water Temp", "°F"),
            InputPoint(34, "CHWC-RETW-T", "AI", "10K -40 ->250", "CHW Coil Return Water Temp", "°F"),
        ],

        outputs=[
            OutputPoint(5, "CHW-VLV", "AO", "0.0 ->100%", "Cold Deck CHW Valve", 2.0, 10.0),
        ],

        values=[
            ValuePoint(77, "COLD-DECK-SAT-SP", "AV", 55.0,  "Cold Deck SAT Setpoint", "°F"),
            ValuePoint(152, "CHW-AVAIL",        "BV", False, "Chilled Water Available"),
            ValuePoint(153, "CLG-RAMP",         "AV", 0.5,   "Cooling Valve Ramp Time", "Min."),
        ],

        loops=[
            LoopDef(8, "CHW-VLV-LOOP", "COLD-DECK-T", "COLD-DECK-SAT-SP", "CHW-VLV",
                    p_band=12.0, integral=40.0, action="direct",
                    description="Cold Deck CHW Valve SAT Control"),
        ],

        programs=[
            ProgramDef(42, "DD-COLD-CHW-PRG", "PRG42-DD-COLD-CHW.bas", "", True,
                       "Dual duct cold deck CHW valve control",
                       exec_order=42),
        ],

        soo_paragraph="""The cold deck shall be equipped with a chilled water cooling coil
controlled by a modulating 2-way valve. The valve shall modulate to
maintain the cold deck supply air temperature setpoint. Cold deck
setpoint shall be reset based on zone cooling demands.""",

        requires=["core"],
        conflicts=["clg-chw", "clg-dx", "clg-dx-2", "clg-dx-vfd", "dd-cold-dx"],
        mutually_exclusive_group="cooling",
    )


def build_dd_hot_hw():
    """Dual duct hot deck — HW heating"""
    return Module(
        id="dd-hot-hw",
        name="DD Hot Deck HW",
        category="heating",
        description="Dual duct hot deck — HW heating coil with SAT control",

        inputs=[
            InputPoint(8, "HOT-DECK-T", "AI", "10K -40 ->250", "Hot Deck Temperature", "°F"),
            InputPoint(31, "HWC-SUPW-T", "AI", "10K -40 ->250", "HW Coil Supply Water Temp", "°F"),
            InputPoint(32, "HWC-RETW-T", "AI", "10K -40 ->250", "HW Coil Return Water Temp", "°F"),
        ],

        outputs=[
            OutputPoint(4, "HW-VLV", "AO", "0.0 ->100%", "Hot Deck HW Valve (reverse)", 10.0, 2.0, True),
        ],

        values=[
            ValuePoint(76, "HOT-DECK-SAT-SP",  "AV", 85.0,  "Hot Deck SAT Setpoint",      "°F"),
            ValuePoint(55, "HTG-LO-SP",         "AV", 65.0,  "Heating Lockout OAT SP",     "°F"),
            ValuePoint(56, "HTG-LOCKOUT",        "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",          "AV", 55.0,  "Cooling Lockout OAT SP",     "°F"),
            ValuePoint(59, "CLG-LOCKOUT",         "BV", False, "Cooling Lockout Active"),
            ValuePoint(52, "FRZ-PRTC-SP",        "AV", 25.0,  "Freeze Protection OAT SP",   "°F"),
            ValuePoint(53, "FRZ-PRTC-MODE",      "BV", False, "Freeze Protection Mode"),
            ValuePoint(150,"HTG-RAMP",            "AV", 0.5,   "Heating Valve Ramp Time",    "Min."),
            ValuePoint(151,"HW-AVAIL",            "BV", False, "Hot Water Available"),
        ],

        loops=[
            LoopDef(7, "HW-VLV-LOOP", "HOT-DECK-T", "HOT-DECK-SAT-SP", "HW-VLV",
                    p_band=12.0, integral=40.0, action="reverse",
                    description="Hot Deck HW Valve SAT Control"),
            LoopDef(9, "FRZ-LOOP", "HOT-DECK-T", "HTG-VLV-FREEZE-SP", "HW-VLV",
                    p_band=12.0, integral=40.0, action="reverse",
                    description="Freeze Protection Valve Override"),
        ],

        programs=[
            ProgramDef(39, "DD-HOT-HW-PRG", "PRG39-DD-HOT-HW.bas", "", True,
                       "Dual duct hot deck HW valve control",
                       exec_order=39),
            ProgramDef(5, "FRZ-PRTN-MODE-PRG", "PRG05-FRZ-PRTN-MODE.bas", "", True,
                       "Freeze protection mode determination",
                       exec_order=5),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout determination",
                       exec_order=6),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-HOT-DECK", "Hot deck status, valve, setpoint"),
            SystemGroupDef("{device-name}-COLD-DECK", "Cold deck status, valve, setpoint"),
        ],

        soo_paragraph="""The hot deck shall be equipped with a hot water heating coil
controlled by a modulating 2-way valve. The valve actuator shall be
reverse-acting (fail-open) for freeze protection. The valve shall
modulate to maintain the hot deck supply air temperature setpoint.
Hot deck setpoint shall be reset based on outdoor air temperature
and zone heating demands. Upon low temperature cutout, the hot deck
valve shall drive to 100% open.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-gas", "dd-hot-elec"],
        mutually_exclusive_group="heating",
    )


def build_dd_hot_elec():
    """Dual duct hot deck — electric heat"""
    return Module(
        id="dd-hot-elec",
        name="DD Hot Deck Electric",
        category="heating",
        description="Dual duct hot deck — 2-stage electric heat with SAT control",

        inputs=[
            InputPoint(8, "HOT-DECK-T", "AI", "10K -40 ->250", "Hot Deck Temperature", "°F"),
        ],

        outputs=[
            OutputPoint(22, "ELEC-HTR-1", "BO", "Stop/Start", "Hot Deck Electric Stage 1"),
            OutputPoint(23, "ELEC-HTR-2", "BO", "Stop/Start", "Hot Deck Electric Stage 2"),
        ],

        values=[
            ValuePoint(76, "HOT-DECK-SAT-SP", "AV", 85.0,  "Hot Deck SAT Setpoint", "°F"),
            ValuePoint(55, "HTG-LO-SP",        "AV", 65.0,  "Heating Lockout OAT SP", "°F"),
            ValuePoint(56, "HTG-LOCKOUT",       "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",         "AV", 55.0,  "Cooling Lockout OAT SP", "°F"),
            ValuePoint(59, "CLG-LOCKOUT",        "BV", False, "Cooling Lockout Active"),
        ],

        programs=[
            ProgramDef(39, "DD-HOT-ELEC-PRG", "PRG39-DD-HOT-ELEC.bas", "", True,
                       "Dual duct hot deck electric heat staging",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout",
                       exec_order=6),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-HOT-DECK", "Hot deck status, staging, setpoint"),
            SystemGroupDef("{device-name}-COLD-DECK", "Cold deck status, valve, setpoint"),
        ],

        soo_paragraph="""The hot deck shall be equipped with 2-stage electric heating.
Stages shall be sequenced to maintain hot deck supply air temperature
setpoint. Heat shall be locked out based on outdoor air temperature.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-gas", "dd-hot-hw"],
        mutually_exclusive_group="heating",
    )
