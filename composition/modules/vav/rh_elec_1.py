"""
VAV 1-Stage Electric Reheat Module — vav-rh-elec-1

Adds single-stage electric reheat to any VAV family.
AI1 = DAT (discharge air temp), BO1 = RH-STG01.
No PID loop — simple on/off with DAT limit and deadband.
PRG4 = RH-PRG stages heater based on HVAC mode and DAT.

Used by: VAV-SD-ELEC-1
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG04_RH = """\
REM --- RH-PRG ---
REM 1-stage electric reheat: on/off with DAT setpoint and safety limit
REM No HW dependency — electric heat is self-contained
REM
REM --- Reheat Mode Check ---
IF HVAC-MODE = 3 THEN GOTO 100
IF HVAC-MODE = 4 THEN GOTO 100
REM
REM --- No Reheat ---
RH-STG01 = 0
GOTO 999
REM
REM --- Reheat Active ---
100 REM Calculate DAT setpoint from room temp deviation
DAT-SP = SLIDE( RMT-SP-HTG - ACT-RMT, 0.0, 4.0, DAT-MIN-SP, DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP, DAT-MIN-SP, DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Safety Cutoff ---
IF DAT > RH-MAX-DAT THEN RH-STG01 = 0
IF DAT > RH-MAX-DAT THEN GOTO 999
REM
REM --- Stage Control with Deadband ---
REM On when DAT below setpoint, off when DAT above setpoint + 2F
IF DAT < DAT-SP THEN RH-STG01 = 1
IF DAT > ( DAT-SP + 2.0 ) THEN RH-STG01 = 0
REM
999 REM End
"""


def build():
    return Module(
        id="vav-rh-elec-1",
        name="1-Stage Electric Reheat",
        category="reheat",
        description="Single stage electric reheat (BO on/off) with DAT safety limit",
        is_core=False,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250",
                       "Discharge Air Temperature", "deg.F"),
        ],

        outputs=[
            OutputPoint(1, "RH-STG01", "BO", "Off/On",
                        "Reheat Stage 1", units=""),
        ],

        values=[
            ValuePoint(36, "DAT-MAX-SP",   "AV", 102.5, "Max DAT Setpoint",                "deg.F"),
            ValuePoint(37, "DAT-SP",       "AV", 90.0,  "Active DAT Setpoint (calculated)","deg.F"),
            ValuePoint(39, "DAT-MIN-SP",   "AV", 70.0,  "Min DAT Setpoint",                "deg.F"),
        ],

        loops=[],

        programs=[
            ProgramDef(4, "RH-PRG", "PRG04-RH.bas", _PRG04_RH, True,
                       "1-stage electric reheat: on/off with DAT limit",
                       exec_order=4),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "Reheat stage control: DAT, setpoints, stage status"),
        ],

        soo_paragraph="""The VAV terminal unit shall include a single stage electric reheat coil
controlled by a binary output. Discharge air temperature shall be measured
by a 10K thermistor sensor. The heater shall energize when the HVAC mode
is Reheat or Heat and discharge air temperature is below the calculated
setpoint. A 2 degree deadband shall prevent short cycling. The heater
shall de-energize immediately if discharge air temperature exceeds the
maximum safety limit. The heater shall be off in ventilation, cooling,
and unoccupied modes.""",

        mutually_exclusive_group="reheat",
    )
