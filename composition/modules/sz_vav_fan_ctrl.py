"""
Single Zone VAV Fan Speed Control Module

Per ASHRAE Guideline 36 Section 5.18: VFD fan modulates based on zone
temperature — NOT duct static pressure. No downstream VAV boxes.

Zone temp cascade resets SAT setpoint. Fan speed follows SAT PID loop
output, clamped between min and max speed.

In heating mode, fan runs at reduced speed (SZ-FAN-HTG-SPD) to avoid
cold drafts while heating coil warms the air.
"""

from composition.models import (
    Module, InputPoint, ValuePoint, LoopDef,
    ProgramDef
)


def build():
    return Module(
        id="sz-vav-fan-ctrl",
        name="Single Zone VAV Fan Control",
        category="sz-fan",
        description="Zone temp cascade → SAT reset → fan speed control for single zone VAV",

        inputs=[
            InputPoint(2, "ZNT", "AI", "10K -40 ->250",
                       "Zone Temperature", "°F"),
        ],

        values=[
            ValuePoint(89, "SZ-FAN-MIN-SPD",  "AV", 30.0,  "Minimum Fan Speed",       "%"),
            ValuePoint(90, "SZ-FAN-MAX-SPD",  "AV", 100.0, "Maximum Fan Speed",       "%"),
            ValuePoint(91, "SZ-FAN-HTG-SPD",  "AV", 50.0,  "Heating Mode Fan Speed",  "%"),
            ValuePoint(92, "ZNT-CLG-SP",      "AV", 75.0,  "Zone Cooling Setpoint",   "°F"),
            ValuePoint(93, "ZNT-HTG-SP",      "AV", 70.0,  "Zone Heating Setpoint",   "°F"),
            ValuePoint(94, "ZNT-DB",          "AV", 2.0,   "Zone Temp Deadband",      "°F"),
        ],

        loops=[
            LoopDef(1, "SZ-FAN-LOOP", "SAT", "ACT-SAT-SP", "SF-VFD-SPD",
                    p_band=12.0, integral=60.0, action="direct",
                    description="Single Zone Fan Speed — SAT Control"),
        ],

        programs=[
            ProgramDef(13, "SZ-FAN-SPD-PRG", "PRG13-SZ-FAN-SPD.bas", "", True,
                       "Single zone fan speed from SAT loop + zone cascade",
                       "sz-vav-fan-ctrl", exec_order=13),
        ],

        requires=["core", "fan-sf-vfd"],
        conflicts=["dsp-ctrl"],
    )
