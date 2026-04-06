"""
Supply Fan Modules — VFD, Constant Speed, 2-Speed

Based on A201: PRG33 (SF-PRG)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, ProgramDef, TrendDef
)


def build_sf_vfd():
    """Supply fan with VFD — most common for VAV AHUs"""
    return Module(
        id="fan-sf-vfd",
        name="Supply Fan VFD",
        category="fan",
        description="Supply fan with variable frequency drive, speed ramp, failure detection",

        outputs=[
            OutputPoint(9,  "SF",         "BO", "Stop/Start", "Supply Fan Command"),
            OutputPoint(10, "SF-VFD-SPD", "AO", "0.0 ->100%",   "Supply Fan VFD Speed", 0.0, 10.0),
        ],

        values=[
            ValuePoint(137, "SF-MIN-SPEED",   "AV", 30.0,  "SF Minimum Speed",     "%"),
            ValuePoint(138, "SF-MAX-SPEED",   "AV", 100.0, "SF Maximum Speed",     "%"),
            ValuePoint(139, "SF-SPEED-RAMP",  "AV", 1.0,   "SF Speed Ramp Time",   "Min."),
            ValuePoint(140, "SF-FAIL",        "BV", False,  "SF Failure Alarm"),
        ],

        programs=[
            ProgramDef(33, "SF-PRG", "PRG33-SF.bas", "", True,
                       "Supply fan VFD control with speed ramp and failure detection",
                       exec_order=33),
        ],

        soo_paragraph="""The supply fan shall be controlled by a variable frequency drive (VFD).
Fan speed shall modulate to maintain duct static pressure setpoint via PID loop.
Speed shall ramp between current and target at a configurable rate.
The fan shall start/stop based on occupancy mode (Occupied, Bypass, and extended modes).
Fan failure shall be alarmed if commanded on with no status after 30 seconds.
The fan shall be stopped immediately upon any safety shutdown condition.""",

        requires=["core"],
    )


def build_sf_cs():
    """Supply fan constant speed — simple start/stop"""
    return Module(
        id="fan-sf-cs",
        name="Supply Fan Constant Speed",
        category="fan",
        description="Supply fan constant speed — start/stop only, no VFD",

        outputs=[
            OutputPoint(9, "SF", "BO", "Stop/Start", "Supply Fan Command"),
        ],

        values=[
            ValuePoint(140, "SF-FAIL", "BV", False, "SF Failure Alarm"),
        ],

        programs=[
            ProgramDef(33, "SF-PRG", "PRG33-SF-CS.bas", "", True,
                       "Supply fan constant speed — start/stop with failure detection",
                       exec_order=33),
        ],

        soo_paragraph="""The supply fan shall operate at constant speed. The fan shall be
started and stopped based on occupancy mode. Fan failure shall be alarmed
if commanded on with no status after 30 seconds. The fan shall be stopped
immediately upon any safety shutdown condition.""",

        requires=["core"],
        conflicts=["fan-sf-vfd", "fan-sf-2spd"],
        mutually_exclusive_group="supply-fan",
    )


