"""
Return Fan / Exhaust Fan / Relief Fan Modules

Based on A201: PRG37 (EF-PRG) with building pressure control
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef, ProgramDef
)


def build_rf_vfd():
    """Return fan with VFD — tracks supply fan for building pressure"""
    return Module(
        id="fan-rf-vfd",
        name="Return Fan VFD",
        category="fan",
        description="Return fan VFD with building pressure tracking",

        inputs=[
            InputPoint(2,  "RF-S",        "BI", "Off/On",       "Return Fan Status"),
            InputPoint(14, "BLDG-PRESS",  "AI", "Table4", "Building Static Pressure", "WC", "BLDG-P-TBL"),
        ],

        outputs=[
            OutputPoint(11, "RF",         "BO", "Stop/Start",  "Return Fan Command"),
            OutputPoint(12, "RF-VFD-SPD", "AO", "0.0 ->100%",    "Return Fan VFD Speed", 0.0, 10.0),
        ],

        values=[
            ValuePoint(7,   "AVG-BLDG-PRESS", "AV", 0.0,   "Avg Building Pressure",  "WC"),
            ValuePoint(160, "RF-MIN-SPEED",    "AV", 30.0,  "RF Minimum Speed",       "%"),
            ValuePoint(161, "RF-MAX-SPEED",    "AV", 100.0, "RF Maximum Speed",       "%"),
            ValuePoint(162, "RF-SPEED-RAMP",   "AV", 1.0,   "RF Speed Ramp Time",     "Min."),
            ValuePoint(166, "RF-FAIL",         "BV", False,  "RF Failure Alarm"),
        ],

        loops=[
            LoopDef(5, "BLDG-P-LOOP", "AVG-BLDG-PRESS", "BLDG-P-SP", "RF-VFD-SPD",
                    p_band=10.0, integral=20.0, action="direct",
                    description="Building Pressure"),
        ],

        tables=[
            TableDef(4, "BLDG-P-TBL", "Volts", "WC",
                     [[0.0, -0.25], [5.0, 0.0], [10.0, 0.25]],
                     "Building pressure sensor scaling"),
        ],

        programs=[
            ProgramDef(37, "RF-PRG", "PRG37-RF.bas", "", True,
                       "Return fan VFD with building pressure control",
                       exec_order=37),
        ],

        soo_paragraph="""A return fan shall track supply airflow to maintain building static
pressure setpoint. Return fan speed shall modulate via PID loop based on
building pressure sensor. Fan failure shall be alarmed if commanded on
with no status after 30 seconds.""",

        requires=["core"],
        conflicts=["fan-ef-vfd", "fan-ef-cs", "fan-rlf-vfd", "fan-rlf-cs"],
        mutually_exclusive_group="return-exhaust-fan",
    )


def build_rf_cs():
    """Return fan constant speed"""
    return Module(
        id="fan-rf-cs",
        name="Return Fan Constant Speed",
        category="fan",
        description="Return fan constant speed — start/stop with supply fan",

        inputs=[
            InputPoint(2, "RF-S", "BI", "Off/On", "Return Fan Status"),
        ],

        outputs=[
            OutputPoint(11, "RF", "BO", "Stop/Start", "Return Fan Command"),
        ],

        values=[
            ValuePoint(166, "RF-FAIL", "BV", False, "RF Failure Alarm"),
        ],

        programs=[
            ProgramDef(37, "RF-PRG", "PRG37-RF-CS.bas", "", True,
                       "Return fan constant speed — follows supply fan",
                       exec_order=37),
        ],

        soo_paragraph="""A return fan shall operate at constant speed, starting and stopping
with the supply fan. Fan failure shall be alarmed if commanded on
with no status after 30 seconds.""",

        requires=["core"],
        conflicts=["fan-rf-vfd", "fan-ef-vfd", "fan-ef-cs", "fan-rlf-vfd", "fan-rlf-cs"],
        mutually_exclusive_group="return-exhaust-fan",
    )


def build_ef_vfd():
    """Exhaust fan with VFD — tracks OA airflow"""
    return Module(
        id="fan-ef-vfd",
        name="Exhaust Fan VFD",
        category="fan",
        description="Exhaust fan VFD tracking OA airflow for building pressure",

        inputs=[
            InputPoint(2,  "EF-S",      "BI", "Off/On",         "Exhaust Fan Status"),
            InputPoint(22, "EA-CFM",    "AI", "Table5",   "Exhaust Airflow", "CFM", "EA-VEL-TBL"),
            InputPoint(23, "EA-DMP-ES", "BI", "Close/Open",     "Exhaust Damper End Switch"),
        ],

        outputs=[
            OutputPoint(3,  "EAD",        "AO", "0.0 ->100%", "Exhaust Air Damper",     2.0, 10.0),
            OutputPoint(11, "EF",         "BO", "Stop/Start", "Exhaust Fan Command"),
            OutputPoint(12, "EF-VFD-SPD", "AO", "0.0 ->100%",  "Exhaust Fan VFD Speed", 0.0, 10.0),
        ],

        values=[
            ValuePoint(160, "EA-FLOW-%OA",    "AV", 0.9,   "EA Flow % of OA",       "%"),
            ValuePoint(161, "EF-SPEED-RAMP",  "AV", 1.0,   "EF Speed Ramp Time",    "Min."),
            ValuePoint(163, "EA-FLOW-SP",     "AV", 0.0,   "EA Airflow Setpoint",   "CFM"),
            ValuePoint(166, "EF-FAIL",        "BV", False,  "EF Failure Alarm"),
            ValuePoint(167, "EA-MIN-SPEED",   "AV", 30.0,  "EF Minimum Speed",      "%"),
            ValuePoint(168, "EA-MAX-SPEED",   "AV", 100.0, "EF Maximum Speed",      "%"),
            ValuePoint(170, "EA-FLOW-RAMP",   "AV", 1.0,   "EA Flow Ramp Time",     "Min."),
        ],

        loops=[
            LoopDef(5, "EA-FLOW-LOOP", "EA-CFM", "EA-FLOW-SP", "EF-VFD-SPD",
                    p_band=1500.0, integral=30.0, action="reverse",
                    description="Exhaust Air Flow Tracking"),
        ],

        tables=[
            TableDef(5, "EA-VEL-TBL", "Volts", "CFM",
                     [[0.0, 0.0], [5.0, 1634.0], [10.0, 3269.0]],
                     "Exhaust airflow sensor scaling"),
        ],

        programs=[
            ProgramDef(37, "EF-PRG", "PRG37-EF.bas", "", True,
                       "Exhaust fan VFD with airflow tracking",
                       exec_order=37),
        ],

        soo_paragraph="""An exhaust fan shall track outside airflow to maintain building pressure
balance. Exhaust airflow setpoint shall equal OA actual flow multiplied by a
configurable percentage. Exhaust fan speed shall modulate via PID loop.
The exhaust air damper shall open when the supply fan is running.
The exhaust fan shall not start until the exhaust damper end switch confirms open.
Fan failure shall be alarmed if commanded on with no status after 30 seconds.
A high exhaust static pressure switch shall initiate a safety shutdown.""",

        requires=["core"],
        conflicts=["fan-rf-vfd", "fan-rf-cs", "fan-rlf-vfd", "fan-rlf-cs"],
        mutually_exclusive_group="return-exhaust-fan",
    )


def build_ef_cs():
    """Exhaust fan constant speed"""
    return Module(
        id="fan-ef-cs",
        name="Exhaust Fan Constant Speed",
        category="fan",
        description="Exhaust fan constant speed — runs with supply fan",

        inputs=[
            InputPoint(2,  "EF-S",      "BI", "Off/On",       "Exhaust Fan Status"),
            InputPoint(23, "EA-DMP-ES", "BI", "Close/Open",   "Exhaust Damper End Switch"),
        ],

        outputs=[
            OutputPoint(3,  "EAD", "AO", "0.0 ->100%",   "Exhaust Air Damper", 2.0, 10.0),
            OutputPoint(11, "EF",  "BO", "Stop/Start", "Exhaust Fan Command"),
        ],

        values=[
            ValuePoint(166, "EF-FAIL", "BV", False, "EF Failure Alarm"),
        ],

        programs=[
            ProgramDef(37, "EF-PRG", "PRG37-EF-CS.bas", "", True,
                       "Exhaust fan constant speed",
                       exec_order=37),
        ],

        soo_paragraph="""An exhaust fan shall operate at constant speed. The exhaust air damper
shall open when the supply fan runs. The exhaust fan shall start after the
exhaust damper end switch confirms open. Fan failure shall be alarmed if
commanded on with no status after 30 seconds.""",

        requires=["core"],
        conflicts=["fan-rf-vfd", "fan-rf-cs", "fan-ef-vfd", "fan-rlf-vfd", "fan-rlf-cs"],
        mutually_exclusive_group="return-exhaust-fan",
    )


def build_rlf_vfd():
    """Relief fan with VFD"""
    return Module(
        id="fan-rlf-vfd",
        name="Relief Fan VFD",
        category="fan",
        description="Relief fan VFD for building pressure control",

        inputs=[
            InputPoint(28, "RLF-S",      "BI", "Off/On",       "Relief Fan Status"),
            InputPoint(14, "BLDG-PRESS", "AI", "Table4", "Building Static Pressure", "WC", "BLDG-P-TBL"),
        ],

        outputs=[
            OutputPoint(14, "RLF",         "BO", "Stop/Start", "Relief Fan Command"),
            OutputPoint(15, "RLF-VFD-SPD", "AO", "0.0 ->100%",   "Relief Fan VFD Speed", 0.0, 10.0),
        ],

        values=[
            ValuePoint(7,   "AVG-BLDG-PRESS", "AV", 0.0,   "Avg Building Pressure", "WC"),
            ValuePoint(190, "RLF-MIN-SPEED",   "AV", 30.0,  "RLF Minimum Speed",     "%"),
            ValuePoint(191, "RLF-MAX-SPEED",   "AV", 100.0, "RLF Maximum Speed",     "%"),
            ValuePoint(192, "RLF-SPEED-RAMP",  "AV", 1.0,   "RLF Speed Ramp Time",   "Min."),
            ValuePoint(193, "RLF-FAIL",        "BV", False,  "RLF Failure Alarm"),
        ],

        tables=[
            TableDef(4, "BLDG-P-TBL", "Volts", "WC",
                     [[0.0, -0.25], [5.0, 0.0], [10.0, 0.25]],
                     "Building pressure sensor scaling"),
        ],

        programs=[
            ProgramDef(38, "RLF-PRG", "PRG38-RLF.bas", "", True,
                       "Relief fan VFD with building pressure control",
                       exec_order=38),
        ],

        soo_paragraph="""A relief fan shall modulate to maintain building static pressure
setpoint. Relief fan speed shall be controlled via PID loop. The relief fan
shall run when the supply fan is operating and the economizer is enabled.
Fan failure shall be alarmed if commanded on with no status after 30 seconds.""",

        requires=["core"],
        conflicts=["fan-rf-vfd", "fan-rf-cs", "fan-ef-vfd", "fan-ef-cs", "fan-rlf-cs"],
        mutually_exclusive_group="return-exhaust-fan",
    )


def build_rlf_cs():
    """Relief fan constant speed"""
    return Module(
        id="fan-rlf-cs",
        name="Relief Fan Constant Speed",
        category="fan",
        description="Relief fan constant speed",

        inputs=[
            InputPoint(28, "RLF-S", "BI", "Off/On", "Relief Fan Status"),
        ],

        outputs=[
            OutputPoint(14, "RLF", "BO", "Stop/Start", "Relief Fan Command"),
        ],

        values=[
            ValuePoint(193, "RLF-FAIL", "BV", False, "RLF Failure Alarm"),
        ],

        programs=[
            ProgramDef(38, "RLF-PRG", "PRG38-RLF-CS.bas", "", True,
                       "Relief fan constant speed",
                       exec_order=38),
        ],

        soo_paragraph="""A relief fan shall operate at constant speed when the supply fan
is running and the economizer is enabled.""",

        requires=["core"],
        conflicts=["fan-rf-vfd", "fan-rf-cs", "fan-ef-vfd", "fan-ef-cs", "fan-rlf-vfd"],
        mutually_exclusive_group="return-exhaust-fan",
    )
