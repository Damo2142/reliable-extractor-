"""
Energy Recovery Wheel Module — FIXED SPEED ONLY

Based on A201: PRG44 (ERW), PRG48 (ERW-BYP-DMP), PRG8 (DEFROST)
ERW is start/stop with bypass damper for capacity control.
NO variable speed — this is a hard rule.
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, ProgramDef, SystemGroupDef
)


def build():
    return Module(
        id="erw",
        name="Energy Recovery Wheel",
        category="energy-recovery",
        description="ERW fixed speed — start/stop + OA/EA bypass dampers + defrost logic",

        inputs=[
            InputPoint(11, "ERW-EA-EAT", "AI", "10K -40 ->250", "ERW Exhaust Entering Air Temp", "°F"),
            InputPoint(24, "ERW-STATUS", "BI", "Off/On",       "ERW Status Feedback"),
            InputPoint(29, "ERW-OA-DAT", "AI", "10K -40 ->250", "ERW OA Leaving Air Temp",       "°F"),
            InputPoint(30, "ERW-EA-DAT", "AI", "10K -40 ->250", "ERW Exhaust Leaving Air Temp",  "°F"),
        ],

        outputs=[
            OutputPoint(6,  "ERW-OA-BYP-DMP", "AO", "0.0 ->100%", "ERW OA Bypass Damper",  2.0, 10.0),
            OutputPoint(7,  "ERW-EA-BYP-DMP", "AO", "0.0 ->100%", "ERW EA Bypass Damper",  2.0, 10.0),
            OutputPoint(13, "ERW",             "BO", "Stop/Start", "Energy Recovery Wheel Command"),
        ],

        values=[
            ValuePoint(67, "ERW-DEFROST-SP",     "AV", 15.0,  "ERW Defrost OAT Setpoint",     "°F"),
            ValuePoint(68, "ERW-DEFROST-MODE",   "BV", False, "ERW Defrost Mode Active"),
            ValuePoint(69, "ERW-DEFROST-MIN-RT", "AV", 10.0,  "ERW Defrost Min Runtime",      "Min."),
            ValuePoint(157,"ERW-FAIL",           "BV", False, "ERW Failure Alarm"),
            ValuePoint(175,"OA-BYP-SP",          "AV", 20.0,  "OA Bypass Damper SP",          "°F"),
            ValuePoint(176,"EA-BYP-SP",          "AV", 20.0,  "EA Bypass Damper SP",          "°F"),
        ],

        loops=[
            LoopDef(11, "OA-BYP-LOOP", "MAT", "OA-BYP-SP", "ERW-OA-BYP-DMP",
                    p_band=12.0, integral=40.0, action="direct",
                    description="ERW OA Bypass Damper"),
            LoopDef(12, "EA-BYP-LOOP", "ERW-EA-DAT", "EA-BYP-SP", "ERW-EA-BYP-DMP",
                    p_band=12.0, integral=40.0, action="direct",
                    description="ERW EA Bypass Damper"),
        ],

        programs=[
            ProgramDef(44, "ERW-PRG", "PRG44-ERW.bas", "", True,
                       "ERW start/stop with failure detection",
                       exec_order=44),
            ProgramDef(48, "ERW-BYP-DMP-PRG", "PRG48-ERW-BYP-DMP.bas", "", True,
                       "ERW OA & EA bypass damper modulation",
                       exec_order=48),
            ProgramDef(8, "DEFROST-MODE-PRG", "PRG08-DEFROST-MODE.bas", "", True,
                       "ERW defrost mode determination",
                       exec_order=8),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-ENERGY-RECOVERY", "ERW status, bypass, defrost", conditional=True),
        ],

        soo_paragraph="""An energy recovery wheel (ERW) shall be provided for heat recovery between
the exhaust and outdoor air streams. The wheel shall operate at fixed speed
(start/stop only — no variable speed modulation).

Capacity control shall be achieved through modulating OA and EA bypass dampers.
The bypass dampers shall modulate via PID loops to prevent overcooling or
overheating of the supply air.

Defrost mode shall activate when the ERW exhaust air leaving temperature falls
below the defrost setpoint. During defrost, bypass dampers shall modulate to
maintain mixed air temperature above the defrost setpoint plus offset. A minimum
defrost runtime shall be enforced before returning to normal operation.

ERW failure shall be alarmed if commanded on with no status feedback after 60 seconds.
The ERW shall not operate during economizer mode (free cooling available).""",

        requires=["core"],
    )
