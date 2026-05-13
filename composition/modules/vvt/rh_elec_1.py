"""
VVT 1-Stage Electric Reheat Module — vvt-rh-elec-1

Adds single-stage electric reheat to VVT zone controller.
AI1 = DAT (discharge air temp), BO1 = RH-STG01.
No PID loop — simple on/off with DAT limit and deadband.

VVT-specific interlocks:
  1. NET-WU-MODE (warmup) → reheat OFF (RTU handles warmup)
  2. NET-SAT > 75F → lockout (SAT too warm for electric)
  3. DAT > 87F → lockout (DAT high limit)
  4. Damper at CFG-HTG-DMP-MIN before stage fires
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG07_RH = """\
REM --- RH-PRG ---
REM VVT 1-stage electric reheat with VVT safety interlocks.
REM Locks out during RTU warmup, with hot SAT, with high DAT, with damper
REM above its minimum-heating position, or out of local heating mode.
REM
REM --- DAT Setpoint from room temp deviation (always computed) ---
DAT-SP = SLIDE( RMT-HTG-SP - ACT-RMT , 0.0 , 4.0 , DAT-MIN-SP , DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP , DAT-MIN-SP , DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Default off; turn on only when ALL gating conditions pass and DAT cold ---
RH-STG01 = 0
IF NET-HVAC-MODE <> 5 AND NET-SAT <= 75.0 AND DAT <= 87.0 AND HVAC-MODE-LOCAL >= 3 AND HVAC-MODE-LOCAL <= 4 AND DMP-POS <= CFG-HTG-DMP-MIN AND DAT < DAT-SP THEN RH-STG01 = 1
REM
REM --- Deadband: shut off once DAT rises above setpoint + 2°F ---
IF DAT > ( DAT-SP + 2.0 ) THEN RH-STG01 = 0
"""


def build():
    return Module(
        id="vvt-rh-elec-1",
        name="VVT 1-Stage Electric Reheat",
        category="reheat",
        description="Single stage electric reheat (BO) with VVT interlocks: SAT lockout, DAT limit, min airflow",
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
            ValuePoint(57, "DAT-MAX-SP",      "AV", 87.0,  "Max DAT Setpoint",                "deg.F"),
            ValuePoint(37, "DAT-SP",          "AV", 80.0,  "Active DAT Setpoint (calculated)","deg.F"),
            ValuePoint(58, "DAT-MIN-SP",      "AV", 70.0,  "Min DAT Setpoint",                "deg.F"),
            ValuePoint(100,"RH-MAX-DAT",      "AV", 87.0,  "Reheat Max Discharge Air Temp",   "deg.F"),
            ValuePoint(101,"CFG-HTG-DMP-MIN", "AV", 20.0,  "Min Damper Position for Reheat",  "%"),
        ],

        loops=[],

        programs=[
            ProgramDef(7, "RH-PRG", "PRG07-RH.bas", _PRG07_RH, True,
                       "VVT 1-stage electric: SAT lockout, DAT limit, min airflow",
                       exec_order=7),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "Reheat stage control: DAT, setpoints, stage status, safety interlocks"),
        ],

        soo_paragraph="""The VVT zone controller shall include a single stage electric reheat coil.
The heater shall energize when the local HVAC mode is Reheat or Heat and
discharge air temperature is below the calculated setpoint. VVT-specific
safety interlocks shall include: warmup lockout (RTU Initialize mode),
supply air temperature lockout above 75F, discharge air temperature high
limit at 87F, and minimum damper position requirement before the stage fires.
A 2 degree deadband shall prevent short cycling.""",

        mutually_exclusive_group="reheat",
    )
