"""
VAV Floating HW Reheat Module — vav-rh-hw-flt

Adds floating hot water reheat valve to any VAV family.
AI1 = DAT (discharge air temp), BO1 = RH-OPEN, BO2 = RH-CLOSE.
No PID loop — uses FLOAT() function for open/close/position tracking.
PRG4 = RH-PRG calculates demand and calls FLOAT().

FLOAT syntax (Control-BASIC Manual p.281):
  feedback = FLOAT( open-BO, close-BO, LOOP, drive-time, deadband, reset )
  - LOOP = desired position 0-100% (demand value)
  - drive-time = full stroke seconds
  - deadband = full deadband % (divided by 2 internally)
  - reset = BV sync trigger (1=sync, auto-clears)
  - feedback = tracked position 0-100%

Used by: VAV-SD-HW-FLT, VAV-PF-HW-FLT, VAV-SF-HW-FLT, VAV-DD-HW-FLT
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG04_RH = """\
REM --- RH-PRG ---
REM Floating HW reheat: calculate demand, drive valve via FLOAT()
REM FLOAT( open-BO, close-BO, LOOP, drive-time, deadband, reset )
REM
REM --- Reheat Mode Check ---
IF HVAC-MODE = 3 THEN GOTO 100
IF HVAC-MODE = 4 THEN GOTO 100
REM
REM --- No Reheat ---
REM Vent, Cool, or Unoccupied — sync valve closed
REM Trigger sync on transition out of reheat mode
IF RH-POS > 0.0 THEN RH-FLOAT-SYNC = 1
RH-POS = FLOAT( RH-OPEN, RH-CLOSE, 0.0, CFG-RH-DRV-TIME, CFG-RH-POS-DB, RH-FLOAT-SYNC )
GOTO 999
REM
REM --- Reheat Active ---
100 REM Calculate DAT setpoint from room temp deviation
DAT-SP = SLIDE( RMT-SP-HTG - ACT-RMT, 0.0, 4.0, DAT-MIN-SP, DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP, DAT-MIN-SP, DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- HW Available Check ---
IF NOT HWS-OK THEN RH-FLOAT-SYNC = 1
IF NOT HWS-OK THEN RH-POS = FLOAT( RH-OPEN, RH-CLOSE, 0.0, CFG-RH-DRV-TIME, CFG-RH-POS-DB, RH-FLOAT-SYNC )
IF NOT HWS-OK THEN GOTO 999
REM
REM --- Calculate Demand 0-100% ---
REM Demand based on DAT error: how far DAT is below setpoint
REM At DAT-SP demand=0 (satisfied), at DAT-SP minus range demand=100 (full open)
REM Range = DAT-MAX-SP - DAT-MIN-SP
RH-DMD = SLIDE( DAT-SP - DAT, 0.0, DAT-MAX-SP - DAT-MIN-SP, 0.0, 100.0 )
RH-DMD = LIMIT( RH-DMD, 0.0, 100.0 )
REM
REM --- Power Loss Sync ---
IF+ POWER-LOSS THEN START RH-FLOAT-SYNC
REM
REM --- Unoccupied Transition Sync ---
IF+ OCC-MODE >= 4 THEN START RH-FLOAT-SYNC
REM
REM --- Drive Valve ---
RH-POS = FLOAT( RH-OPEN, RH-CLOSE, RH-DMD, CFG-RH-DRV-TIME, CFG-RH-POS-DB, RH-FLOAT-SYNC )
REM
REM --- Auto-clear sync after FLOAT processes it ---
IF TIME-ON( RH-FLOAT-SYNC ) > 0:00:05 THEN STOP RH-FLOAT-SYNC
REM
999 REM End
"""


def build():
    return Module(
        id="vav-rh-hw-flt",
        name="Floating HW Reheat",
        category="reheat",
        description="Floating hot water reheat valve (BO open/close) with FLOAT() position tracking",
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
            # BV for float sync
            ValuePoint(70, "RH-FLOAT-SYNC",   "BV", False, "Float Sync Trigger"),
        ],

        loops=[],  # No PID loop — FLOAT() handles control

        programs=[
            ProgramDef(4, "RH-PRG", "PRG04-RH.bas", _PRG04_RH, True,
                       "Floating HW reheat: FLOAT() valve control with position tracking",
                       exec_order=4),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "Reheat valve control: DAT, setpoints, valve position, float sync"),
        ],

        soo_paragraph="""The VAV terminal unit shall include a floating hot water reheat valve
controlled by open and close binary outputs. Discharge air temperature shall be
measured by a 10K thermistor sensor. The FLOAT function shall track valve position
based on output active time and configured drive time. A floating synchronization
routine shall execute on power loss, transition to unoccupied mode, and transition
out of reheat mode. The reheat demand shall be calculated from discharge air
temperature deviation below the active setpoint. The valve shall close in
ventilation and cooling modes, and when the HW system status indicates unavailable.""",

        mutually_exclusive_group="reheat",
    )
