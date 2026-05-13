"""
VAV 2-Stage Electric Reheat Module — vav-rh-elec-2

AI1 = DAT, BO1 = RH-STG01, BO2 = RH-STG02.
Stage 1 on at DAT < DAT-SP, Stage 2 on at DAT < DAT-SP - 4F.
Both off above DAT-SP + 2F. Safety cutoff at RH-MAX-DAT.
No PID loop. PRG4 = RH-PRG.

Used by: VAV-SD-ELEC-2, VAV-PF-ELEC-2, VAV-SF-ELEC-2
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG04_RH = """\
REM --- RH-PRG ---
REM 2-stage electric reheat: staged on/off with DAT setpoint.
REM Stage 1 on at DAT < DAT-SP. Stage 2 on at DAT < DAT-SP - 4°F.
REM Both off above DAT-SP + 2°F. Safety cutoff at RH-MAX-DAT.
REM
REM --- DAT Setpoint from room temp deviation (always computed) ---
DAT-SP = SLIDE( RMT-SP-HTG - ACT-RMT , 0.0 , 4.0 , DAT-MIN-SP , DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP , DAT-MIN-SP , DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Default both stages off; turn on only in heating mode + cold DAT ---
RH-STG01 = 0
RH-STG02 = 0
IF HVAC-MODE = 3 AND DAT < DAT-SP THEN RH-STG01 = 1
IF HVAC-MODE = 4 AND DAT < DAT-SP THEN RH-STG01 = 1
IF HVAC-MODE = 3 AND DAT < ( DAT-SP - 4.0 ) THEN RH-STG02 = 1
IF HVAC-MODE = 4 AND DAT < ( DAT-SP - 4.0 ) THEN RH-STG02 = 1
REM
REM --- Deadband: drop stage 2 once DAT recovers to within 2°F of SP ---
IF DAT >= ( DAT-SP - 2.0 ) THEN RH-STG02 = 0
REM
REM --- Deadband: both stages off once DAT rises above SP + 2°F ---
IF DAT > ( DAT-SP + 2.0 ) THEN RH-STG01 = 0
IF DAT > ( DAT-SP + 2.0 ) THEN RH-STG02 = 0
REM
REM --- Safety cutoff: forced off if DAT exceeds RH-MAX-DAT ---
IF DAT > RH-MAX-DAT THEN RH-STG01 = 0
IF DAT > RH-MAX-DAT THEN RH-STG02 = 0
"""


def build():
    return Module(
        id="vav-rh-elec-2",
        name="2-Stage Electric Reheat",
        category="reheat",
        description="Two stage electric reheat (BO x2) with DAT safety limit",
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
            ValuePoint(36, "DAT-MAX-SP",   "AV", 102.5, "Max DAT Setpoint",                "deg.F"),
            ValuePoint(37, "DAT-SP",       "AV", 90.0,  "Active DAT Setpoint (calculated)","deg.F"),
            ValuePoint(39, "DAT-MIN-SP",   "AV", 70.0,  "Min DAT Setpoint",                "deg.F"),
        ],

        loops=[],

        programs=[
            ProgramDef(4, "RH-PRG", "PRG04-RH.bas", _PRG04_RH, True,
                       "2-stage electric reheat: staged on/off with DAT limit",
                       exec_order=4),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "Reheat stage control: DAT, setpoints, stage status"),
        ],

        soo_paragraph="""The VAV terminal unit shall include a two stage electric reheat coil.
Stage 1 shall energize when discharge air temperature falls below the
calculated DAT setpoint. Stage 2 shall energize when discharge air
temperature falls 4 degrees below the setpoint. Both stages shall
de-energize when discharge air temperature rises 2 degrees above the
setpoint. Both stages shall de-energize immediately if discharge air
temperature exceeds the maximum safety limit.""",

        mutually_exclusive_group="reheat",
    )
