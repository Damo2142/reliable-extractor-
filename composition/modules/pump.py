"""
Pump Modules — Standard pump control pattern for all coil pumps.

ALL PUMPS FOLLOW THE SAME PATTERN:
- ON: valve output > 0% OR (heating coils only: OAT < freeze SP)
- OFF: valve closed AND (heating: OAT > freeze SP + deadband)
- Every pump: BO command, BI status, BV failure alarm
- Failure: commanded on + no status after 30s = pump fail alarm
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, ProgramDef
)


def build_hw_pump():
    """HW coil pump — standard pattern"""
    return Module(
        id="htg-hw-pump",
        name="HW Coil Pump",
        category="pump",
        description="Hot water coil pump — valve open OR freeze triggers pump",

        outputs=[
            OutputPoint(18, "HW-PMP", "BO", "Stop/Start", "HW Coil Pump Command"),
        ],

        values=[
            ValuePoint(260, "HW-PMP-STS",    "BV", False, "HW Pump Status"),
            ValuePoint(261, "HW-PMP-FAIL",   "BV", False, "HW Pump Failure Alarm"),
            ValuePoint(262, "HW-PMP-DLY",    "AV", 30.0,  "HW Pump Fail Delay", "Sec"),
        ],

        programs=[
            ProgramDef(41, "HW-PMP-PRG", "PRG41-HW-PMP.bas", "", True,
                       "HW coil pump — valve open or freeze protection",
                       exec_order=41),
        ],

        soo_paragraph="""A dedicated hot water coil pump shall be provided. The pump shall
run whenever the hot water valve output is greater than 0%, or when outdoor
air temperature is below the freeze protection setpoint (heating coil freeze
protection). The pump shall stop when the valve is closed and outdoor
temperature is above the freeze setpoint plus deadband. Pump failure shall
be alarmed if commanded on with no status confirmation after 30 seconds.""",

        requires=["htg-hw"],
    )


def build_chw_pump():
    """CHW coil pump — standard pattern (no freeze logic)"""
    return Module(
        id="clg-chw-pump",
        name="CHW Coil Pump",
        category="pump",
        description="Chilled water coil pump — valve open triggers pump",

        outputs=[
            OutputPoint(19, "CHW-PMP", "BO", "Stop/Start", "CHW Coil Pump Command"),
        ],

        values=[
            ValuePoint(265, "CHW-PMP-STS",   "BV", False, "CHW Pump Status"),
            ValuePoint(266, "CHW-PMP-FAIL",  "BV", False, "CHW Pump Failure Alarm"),
            ValuePoint(267, "CHW-PMP-DLY",   "AV", 30.0,  "CHW Pump Fail Delay", "Sec"),
        ],

        programs=[
            ProgramDef(43, "CHW-PMP-PRG", "PRG43-CHW-PMP.bas", "", True,
                       "CHW coil pump — valve open triggers pump",
                       exec_order=43),
        ],

        soo_paragraph="""A dedicated chilled water coil pump shall be provided. The pump shall
run whenever the chilled water valve output is greater than 0%. The pump
shall stop when the valve is fully closed. Pump failure shall be alarmed
if commanded on with no status confirmation after 30 seconds.""",

        requires=["clg-chw"],
    )


def build_ph_pump():
    """Preheat coil pump — standard pattern with freeze"""
    return Module(
        id="ph-hw-pump",
        name="Preheat Pump",
        category="pump",
        description="Preheat coil pump — valve open OR freeze triggers pump",

        outputs=[
            OutputPoint(17, "PH-PMP", "BO", "Stop/Start", "Preheat Pump Command"),
        ],

        values=[
            ValuePoint(270, "PH-PMP-STS",    "BV", False, "Preheat Pump Status"),
            ValuePoint(271, "PH-PMP-FAIL",   "BV", False, "Preheat Pump Failure Alarm"),
            ValuePoint(272, "PH-PMP-DLY",    "AV", 30.0,  "Preheat Pump Fail Delay", "Sec"),
        ],

        programs=[
            ProgramDef(40, "PH-PMP-PRG", "PRG40-PH-PMP.bas", "", True,
                       "Preheat pump — valve open or freeze protection",
                       exec_order=40),
        ],

        soo_paragraph="""A dedicated preheat coil pump shall be provided. The pump shall run
whenever the preheat valve output is greater than 0%, or when outdoor air
temperature is below the freeze protection setpoint. Pump failure shall
be alarmed if commanded on with no status after 30 seconds.""",

        requires=["ph-hw"],
    )
