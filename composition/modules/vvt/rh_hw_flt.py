"""
VVT Floating HW Reheat Module — vvt-rh-hw-flt

Adds floating hot water reheat valve to VVT zone controller.
AI1 = DAT (discharge air temp), BO1 = RH-OPEN, BO2 = RH-CLOSE.
No PID loop — uses FLOAT() function for open/close/position tracking.
PRG7 = RH-PRG calculates demand and calls FLOAT().

VVT-specific interlocks:
  1. NET-WU-MODE (warmup) → reheat OFF (RTU handles warmup)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG07_RH = """\
REM --- RH-PRG ---
REM VVT floating HW reheat: calculate demand, drive valve via FLOAT()
REM FLOAT( open-BO, close-BO, LOOP, drive-time, deadband, reset )
REM
REM --- VVT Warmup Lockout ---
IF NET-HVAC-MODE = 5 THEN GOTO 800
REM
REM --- Reheat Mode Check ---
IF HVAC-MODE-LOCAL = 3 THEN GOTO 100
IF HVAC-MODE-LOCAL = 4 THEN GOTO 100
REM
REM --- No Reheat ---
800 REM Vent, Cool, or Unoccupied — sync valve closed
IF RH-POS > 0.0 THEN RH-FLOAT-SYNC = 1
RH-POS = FLOAT( RH-OPEN, RH-CLOSE, 0.0, CFG-RH-DRV-TIME, CFG-RH-POS-DB, RH-FLOAT-SYNC )
GOTO 999
REM
REM --- Reheat Active ---
100 REM Calculate DAT setpoint from room temp deviation
DAT-SP = SLIDE( RMT-HTG-SP - ACT-RMT, 0.0, 4.0, DAT-MIN-SP, DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP, DAT-MIN-SP, DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Calculate Demand 0-100% ---
RH-DMD = SLIDE( DAT-SP - DAT, 0.0, DAT-MAX-SP - DAT-MIN-SP, 0.0, 100.0 )
RH-DMD = LIMIT( RH-DMD, 0.0, 100.0 )
REM
REM --- Drive Valve ---
RH-POS = FLOAT( RH-OPEN, RH-CLOSE, RH-DMD, CFG-RH-DRV-TIME, CFG-RH-POS-DB, RH-FLOAT-SYNC )
REM
REM --- Auto-clear sync ---
IF TIME-ON( RH-FLOAT-SYNC ) > 0:00:05 THEN STOP RH-FLOAT-SYNC
REM
999 REM End
"""


def build():
    return Module(
        id="vvt-rh-hw-flt",
        name="VVT Floating HW Reheat",
        category="reheat",
        description="Floating hot water reheat valve (BO open/close) with VVT interlocks",
        is_core=False,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250",
                       "Discharge Air Temperature", "deg.F"),
        ],

        outputs=[
            OutputPoint(1, "RH-OPEN",  "BO", "Off/On",
                        "Reheat Valve Open",  units=""),
            OutputPoint(2, "RH-CLOSE", "BO", "Off/On",
                        "Reheat Valve Close", units=""),
        ],

        values=[
            ValuePoint(36, "DAT-MAX-SP",      "AV", 102.5, "Max DAT Setpoint",                "deg.F"),
            ValuePoint(37, "DAT-SP",          "AV", 90.0,  "Active DAT Setpoint (calculated)","deg.F"),
            ValuePoint(39, "DAT-MIN-SP",      "AV", 70.0,  "Min DAT Setpoint",                "deg.F"),
            ValuePoint(67, "RH-POS",          "AV", 0.0,   "Tracked Valve Position (0-100%)", "%"),
            ValuePoint(68, "CFG-RH-DRV-TIME", "AV", 135.0, "Valve Full Stroke Drive Time",    "Sec."),
            ValuePoint(69, "CFG-RH-POS-DB",   "AV", 5.0,   "Reheat Position Deadband",        "%"),
            ValuePoint(83, "RH-DMD",          "AV", 0.0,   "Reheat Demand (0-100%)",          "%"),
            ValuePoint(100,"RH-MAX-DAT",      "AV", 90.0,  "Reheat Max Discharge Air Temp",   "deg.F"),
            ValuePoint(70, "RH-FLOAT-SYNC",   "BV", False, "Float Sync Trigger"),
        ],

        loops=[],

        programs=[
            ProgramDef(7, "RH-PRG", "PRG07-RH.bas", _PRG07_RH, True,
                       "VVT floating HW reheat: FLOAT() with warmup lockout",
                       exec_order=7),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "Reheat valve control: DAT, setpoints, valve position, float sync"),
        ],

        soo_paragraph="""The VVT zone controller shall include a floating hot water reheat valve
controlled by open and close binary outputs. The FLOAT function shall track
valve position based on output active time and configured drive time.
The reheat valve shall close when the RTU is in warmup mode (Initialize).
The reheat demand shall be calculated from discharge air temperature
deviation below the active setpoint.""",

        mutually_exclusive_group="reheat",
    )
