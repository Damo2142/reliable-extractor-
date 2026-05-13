"""
VVT 2-Stage Electric Reheat Module — vvt-rh-elec-2

AI1 = DAT, BO1 = RH-STG01, BO2 = RH-STG02.
Same VVT interlocks as elec-1 apply to both stages.
Staging: SWITCH at 5/50 for stage 1, SWITCH at 50/90 for stage 2.
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG07_RH = """\
REM --- RH-PRG ---
REM VVT 2-stage electric reheat with VVT safety interlocks.
REM Locks out during RTU warmup, with hot SAT, with high DAT, with damper
REM above its minimum-heating position, or out of local heating mode.
REM
REM --- DAT Setpoint from room temp deviation (always computed) ---
DAT-SP = SLIDE( RMT-HTG-SP - ACT-RMT , 0.0 , 4.0 , DAT-MIN-SP , DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP , DAT-MIN-SP , DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Default both stages off; turn on only when ALL gates pass AND cold DAT ---
RH-STG01 = 0
RH-STG02 = 0
IF NET-HVAC-MODE <> 5 AND NET-SAT <= 75.0 AND DAT <= 87.0 AND HVAC-MODE-LOCAL >= 3 AND HVAC-MODE-LOCAL <= 4 AND DMP-POS <= CFG-HTG-DMP-MIN AND DAT < DAT-SP THEN RH-STG01 = 1
IF NET-HVAC-MODE <> 5 AND NET-SAT <= 75.0 AND DAT <= 87.0 AND HVAC-MODE-LOCAL >= 3 AND HVAC-MODE-LOCAL <= 4 AND DMP-POS <= CFG-HTG-DMP-MIN AND DAT < ( DAT-SP - 4.0 ) THEN RH-STG02 = 1
REM
REM --- Deadband: drop stage 2 once DAT recovers to within 2°F of SP ---
IF DAT >= ( DAT-SP - 2.0 ) THEN RH-STG02 = 0
REM
REM --- Deadband: both stages off once DAT rises above SP + 2°F ---
IF DAT > ( DAT-SP + 2.0 ) THEN RH-STG01 = 0
IF DAT > ( DAT-SP + 2.0 ) THEN RH-STG02 = 0
"""


def build():
    return Module(
        id="vvt-rh-elec-2",
        name="VVT 2-Stage Electric Reheat",
        category="reheat",
        description="Two stage electric reheat (BO x2) with VVT interlocks: SAT lockout, DAT limit, min airflow",
        is_core=False,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250",
                       "Discharge Air Temperature", "deg.F"),
        ],

        outputs=[
            OutputPoint(1, "RH-STG01", "BO", "Off/On",
                        "Reheat Stage 1", units=""),
            OutputPoint(2, "RH-STG02", "BO", "Off/On",
                        "Reheat Stage 2", units=""),
        ],

        values=[
            ValuePoint(57, "DAT-MAX-SP",      "AV", 87.0,  "Max DAT Setpoint",                "deg.F"),
            ValuePoint(37, "DAT-SP",          "AV", 80.0,  "Active DAT Setpoint (calculated)","deg.F"),
            ValuePoint(58, "DAT-MIN-SP",      "AV", 70.0,  "Min DAT Setpoint",                "deg.F"),
            ValuePoint(100,"RH-MAX-DAT",      "AV", 87.0,  "Reheat Max Discharge Air Temp",   "deg.F"),
            ValuePoint(101,"CFG-HTG-DMP-MIN", "AV", 20.0,  "Min Damper Position for Reheat",  "%"),
        ],

        loops=[],

        programs=[
            ProgramDef(7, "RH-PRG", "PRG07-RH.bas", _PRG07_RH, True,
                       "VVT 2-stage electric: SAT lockout, DAT limit, min airflow",
                       exec_order=7),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "Reheat stage control: DAT, setpoints, stages, safety interlocks"),
        ],

        soo_paragraph="""The VVT zone controller shall include a two stage electric reheat coil.
Stage 1 shall energize when discharge air temperature falls below the
calculated DAT setpoint. Stage 2 shall energize when discharge air
temperature falls 4 degrees below the setpoint. VVT-specific safety
interlocks shall include: warmup lockout, SAT lockout above 75F,
DAT high limit at 87F, and minimum damper position requirement.""",

        mutually_exclusive_group="reheat",
    )
