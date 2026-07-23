"""
FCU (Fan Coil Unit) Modules — All variants

Families: 2-pipe switchover, 2-pipe CHW only, 4-pipe CHW+HW,
          4-pipe CHW+HW+Electric, 4-pipe CHW+Electric,
          DX+HW, DX+Electric, Heat pump, Heat pump+aux

Standard I/O:
  AI1 = DAT (discharge air temp, 10K type III, mandatory)
  AI3 = RMT (room temp, 10K type III)
  BI2 = SF-STS (fan status feedback)

Control Architecture — Cascaded PID:
  PRG01 MODE-CTRL: occupancy, setpoint selection
  PRG02 CLG-RESET: space temp loop resets CLG-DAT-SP
  PRG03 HTG-RESET: space temp loop resets HTG-DAT-SP
  PRG04 CLG-OUTPUT: DAT loop drives cooling valve/stage
  PRG05 HTG-OUTPUT: DAT loop drives heating valve/stage
  PRG06 FAN-CTRL: fan speed from max loop demand
  PRG07 ECON-CTRL: economizer damper from CLG-DAT-LOOP
  PRG08 SAFETY: freezestat, DAT limits, latch/reset

Controller: MACH-ProZone 88 standard, MACH-ProView LCD optional
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
#  Program Code — Explicit verifiable logic chains
# ═══════════════════════════════════════════════════════════════════════════

_PRG01_MODE = """\
REM --- MODE-CTRL ---
REM Occupancy mode and setpoint selection
REM {parent} = parent device for network variables
REM
IF NET-OCC-CMD = 1 THEN OCC-MODE = 1 ELSE OCC-MODE = 0
REM
REM --- Active Setpoints ---
REM Single operator zone setpoint (RMT-SP) with symmetric deadband.
REM Cooling setpoint = operator SP + deadband ; heating setpoint = operator SP - deadband.
REM Occupied: derive both actives from the one setpoint so they stay locked
REM around it and cannot drift or cross.
REM Unoccupied: use the unoccupied setback pair (unchanged this step).
ACT-RMT-SP-DB = DB-MTPLR * CFG-RMT-SP-DB
IF OCC-MODE = 1 THEN ACT-CLG-SP = RMT-SP + ACT-RMT-SP-DB
IF OCC-MODE = 1 THEN ACT-HTG-SP = RMT-SP - ACT-RMT-SP-DB
IF OCC-MODE = 0 THEN ACT-CLG-SP = CFG-UNOCC-CLG-SP
IF OCC-MODE = 0 THEN ACT-HTG-SP = CFG-UNOCC-HTG-SP
REM Display mirrors of the active setpoints
CLG-SP = ACT-CLG-SP
HTG-SP = ACT-HTG-SP
ACT-RMT = AI3
ACT-DAT = AI1
NET-OCC-CMD = {parent}BV21
HWS-OK = {parent}BV22
NET-OAT = {parent}AV20
"""

_PRG02_CLG_RESET = """\
REM --- CLG-RESET ---
REM Space temp loop resets cooling DAT setpoint
REM CLG-RESET-LOOP: input=ACT-RMT vs setpoint=ACT-CLG-SP, direct acting
REM High space temp = lower DAT-SP (more cooling)
REM
CLG-DAT-SP = SLIDE( CLG-RESET-LOOP, 0.0, 100.0, CFG-CLG-DAT-MIN, CFG-CLG-DAT-MAX )
"""

_PRG03_HTG_RESET = """\
REM --- HTG-RESET ---
REM Space temp loop resets heating DAT setpoint
REM HTG-RESET-LOOP: input=ACT-RMT vs setpoint=ACT-HTG-SP, reverse acting
REM Low space temp = higher DAT-SP (more heating)
REM
HTG-DAT-SP = SLIDE( HTG-RESET-LOOP, 0.0, 100.0, CFG-HTG-DAT-MIN, CFG-HTG-DAT-MAX )
"""

# --- Cooling output programs (one per cooling type) ---

_PRG04_CHW_MOD = """\
REM --- CLG-OUTPUT ---
REM CHW modulating valve driven by CLG-DAT-LOOP
REM CLG-DAT-LOOP: input=ACT-DAT vs setpoint=CLG-DAT-SP, direct acting
REM
CHW-VLV = CLG-DAT-LOOP
IF ACT-DAT < CFG-DAT-LL THEN CHW-VLV = 0
IF FREEZE-TRIP = 1 THEN CHW-VLV = 0
IF OCC-MODE = 0 AND ACT-RMT < CFG-UNOCC-CLG-SP THEN CHW-VLV = 0
"""

_PRG04_CHW_FLT = """\
REM --- CLG-OUTPUT ---
REM CHW floating valve using CBAS FLOAT() function
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
REM
REM Position command from cooling DAT loop
CHW-POS-CMD = CLG-DAT-LOOP
REM
REM Safety overrides force valve closed
IF ACT-DAT < CFG-DAT-LL THEN CHW-POS-CMD = 0
IF FREEZE-TRIP = 1 THEN CHW-POS-CMD = 0
IF OCC-MODE = 0 AND ACT-RMT < CFG-UNOCC-CLG-SP THEN CHW-POS-CMD = 0
REM
REM Floating sync on power cycle and unoccupied
IF+ POWER-LOSS THEN START CHW-FLOAT-SYNC
IF+ OCC-MODE = 0 THEN START CHW-FLOAT-SYNC
IF TIME-ON( CHW-FLOAT-SYNC ) > 0:00:05 THEN STOP CHW-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays
CHW-POS = FLOAT( CHW-OPEN , CHW-CLOSE , CHW-POS-CMD , CFG-CHW-DRV-TIME , CFG-CHW-POS-DB , CHW-FLOAT-SYNC )
"""

_PRG04_DX_1 = """\
REM --- CLG-OUTPUT ---
REM DX stage 1 driven by CLG-DAT-LOOP
REM Min off-timer 180s protects compressor
REM
IF CLG-DAT-LOOP > CFG-STG1-T AND DX1-OFF-TMR > 180 THEN DX-STG1 = 1
IF CLG-DAT-LOOP < ( CFG-STG1-T - 10 ) THEN DX-STG1 = 0
IF FREEZE-TRIP = 1 THEN DX-STG1 = 0
IF OCC-MODE = 0 AND ACT-RMT < CFG-UNOCC-CLG-SP THEN DX-STG1 = 0
IF DX-STG1 = 0 THEN DX1-OFF-TMR = 0
IF DX-STG1 = 1 THEN DX1-OFF-TMR = 999
"""

_PRG04_DX_2 = """\
REM --- CLG-OUTPUT ---
REM DX 2-stage driven by CLG-DAT-LOOP
REM Stage 1: min off 180s. Stage 2: requires stage 1 + min delay 300s
REM
IF CLG-DAT-LOOP > CFG-STG1-T AND DX1-OFF-TMR > 180 THEN DX-STG1 = 1
IF CLG-DAT-LOOP < ( CFG-STG1-T - 10 ) THEN DX-STG1 = 0
IF CLG-DAT-LOOP > CFG-STG2-T AND DX-STG1 = 1 AND DX2-OFF-TMR > 300 THEN DX-STG2 = 1
IF CLG-DAT-LOOP < ( CFG-STG2-T - 10 ) THEN DX-STG2 = 0
IF FREEZE-TRIP = 1 THEN DX-STG1 = 0 : DX-STG2 = 0
IF DX-STG1 = 0 THEN DX1-OFF-TMR = 0 : DX-STG2 = 0
IF DX-STG1 = 1 THEN DX1-OFF-TMR = 999
IF DX-STG2 = 0 THEN DX2-OFF-TMR = 0
IF DX-STG2 = 1 THEN DX2-OFF-TMR = 999
"""

_PRG04_2PIPE_MOD = """\
REM --- CLG-OUTPUT ---
REM 2-pipe switchover: single valve from active DAT loop
REM PIPE-MODE 1=heating (HW available), 0=cooling (CHW available)
REM
IF HWS-OK = 1 OR NET-OAT < CFG-SWITCHOVER-T THEN PIPE-MODE = 1 ELSE PIPE-MODE = 0
IF PIPE-MODE = 0 THEN VALVE = CLG-DAT-LOOP
IF PIPE-MODE = 1 THEN VALVE = HTG-DAT-LOOP
IF FREEZE-TRIP = 1 THEN VALVE = 0
IF OCC-MODE = 0 AND PIPE-MODE = 0 AND ACT-RMT < CFG-UNOCC-CLG-SP THEN VALVE = 0
IF OCC-MODE = 0 AND PIPE-MODE = 1 AND ACT-RMT > CFG-UNOCC-HTG-SP THEN VALVE = 0
"""

_PRG04_2PIPE_FLT = """\
REM --- CLG-OUTPUT ---
REM 2-pipe switchover floating valve using CBAS FLOAT() function
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
REM
REM Pipe mode: 1=heating loop active, 0=cooling loop active
IF HWS-OK = 1 OR NET-OAT < CFG-SWITCHOVER-T THEN PIPE-MODE = 1 ELSE PIPE-MODE = 0
REM
REM Position command from active mode's DAT loop
IF PIPE-MODE = 0 THEN ACTIVE-DMD = CLG-DAT-LOOP ELSE ACTIVE-DMD = HTG-DAT-LOOP
VLV-POS-CMD = ACTIVE-DMD
REM
REM Safety overrides
IF FREEZE-TRIP = 1 THEN VLV-POS-CMD = 0
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP AND ACT-RMT < CFG-UNOCC-CLG-SP THEN VLV-POS-CMD = 0
REM
REM Floating sync on power cycle, mode change, and unoccupied
IF+ POWER-LOSS THEN START VLV-FLOAT-SYNC
IF+ OCC-MODE = 0 THEN START VLV-FLOAT-SYNC
IF+ PIPE-MODE = 1 THEN START VLV-FLOAT-SYNC
IF+ PIPE-MODE = 0 THEN START VLV-FLOAT-SYNC
IF TIME-ON( VLV-FLOAT-SYNC ) > 0:00:05 THEN STOP VLV-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays
VLV-POS = FLOAT( VLV-OPEN , VLV-CLOSE , VLV-POS-CMD , CFG-VLV-DRV-TIME , CFG-VLV-POS-DB , VLV-FLOAT-SYNC )
"""

_PRG04_HP = """\
REM --- HP-CTRL ---
REM Heat pump: compressor + reversing valve from active DAT loop
REM CFG-RV-CLG: 1=energized in cooling, 0=energized in heating
REM
IF ACT-RMT < ACT-HTG-SP THEN HP-MODE = 1 ELSE HP-MODE = 0
IF ACT-RMT > ACT-CLG-SP THEN HP-MODE = 0
IF HP-MODE = 0 THEN HP-DMD = CLG-DAT-LOOP
IF HP-MODE = 1 THEN HP-DMD = HTG-DAT-LOOP
IF HP-DMD > CFG-HP-MIN THEN COMP-CMD = 1 ELSE COMP-CMD = 0
IF COMP-CMD = 0 AND COMP-ON-TMR < 180 THEN COMP-CMD = 1
IF CFG-RV-CLG = 1 AND HP-MODE = 0 THEN RV-CMD = 1
IF CFG-RV-CLG = 1 AND HP-MODE = 1 THEN RV-CMD = 0
IF CFG-RV-CLG = 0 AND HP-MODE = 0 THEN RV-CMD = 0
IF CFG-RV-CLG = 0 AND HP-MODE = 1 THEN RV-CMD = 1
IF FREEZE-TRIP = 1 THEN COMP-CMD = 0 : RV-CMD = 0
COMP-S/S = COMP-CMD
RV = RV-CMD
"""

# --- Heating output programs ---

_PRG05_HW_MOD = """\
REM --- HTG-OUTPUT ---
REM HW modulating valve driven by HTG-DAT-LOOP
REM HTG-DAT-LOOP: input=ACT-DAT vs setpoint=HTG-DAT-SP, reverse acting
REM
HW-VLV = HTG-DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN HW-VLV = 0
IF FREEZE-TRIP = 1 THEN HW-VLV = 0
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP THEN HW-VLV = 0
"""

_PRG05_HW_FLT = """\
REM --- HTG-OUTPUT ---
REM HW floating valve using CBAS FLOAT() function
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
REM
REM Position command from heating DAT loop
RH-POS-CMD = HTG-DAT-LOOP
REM
REM Safety overrides
IF ACT-DAT > CFG-DAT-HL THEN RH-POS-CMD = 0
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP THEN RH-POS-CMD = 0
REM
REM Freeze: drive valve open to keep coil warm
IF FREEZE-TRIP = 1 THEN RH-POS-CMD = 100
REM
REM Floating sync on power cycle and unoccupied
IF+ POWER-LOSS THEN START RH-FLOAT-SYNC
IF+ OCC-MODE = 0 THEN START RH-FLOAT-SYNC
IF TIME-ON( RH-FLOAT-SYNC ) > 0:00:05 THEN STOP RH-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays
RH-POS = FLOAT( RH-OPEN , RH-CLOSE , RH-POS-CMD , CFG-RH-DRV-TIME , CFG-RH-POS-DB , RH-FLOAT-SYNC )
"""

_PRG05_ELEC_1 = """\
REM --- HTG-OUTPUT ---
REM Electric stage 1 driven by HTG-DAT-LOOP
REM
IF HTG-DAT-LOOP > CFG-STG1-T AND ACT-DAT < 87 THEN RH-STG1 = 1
IF HTG-DAT-LOOP < ( CFG-STG1-T - 10 ) THEN RH-STG1 = 0
IF ACT-DAT > 87 THEN RH-STG1 = 0
IF FREEZE-TRIP = 1 THEN RH-STG1 = 0
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP THEN RH-STG1 = 0
ELEC-HTR-S/S = RH-STG1
"""

_PRG05_ELEC_2 = """\
REM --- HTG-OUTPUT ---
REM Electric 2-stage driven by HTG-DAT-LOOP
REM Stage 2 requires stage 1 on
REM
IF HTG-DAT-LOOP > CFG-STG1-T AND ACT-DAT < 87 THEN RH-STG1 = 1
IF HTG-DAT-LOOP < ( CFG-STG1-T - 10 ) THEN RH-STG1 = 0
IF ACT-DAT > 87 THEN RH-STG1 = 0
IF HTG-DAT-LOOP > CFG-STG2-T AND RH-STG1 = 1 AND ACT-DAT < 87 THEN RH-STG2 = 1
IF HTG-DAT-LOOP < ( CFG-STG2-T - 10 ) THEN RH-STG2 = 0
IF ACT-DAT > 87 THEN RH-STG2 = 0
IF FREEZE-TRIP = 1 THEN RH-STG1 = 0 : RH-STG2 = 0
ELEC-HTR1-S/S = RH-STG1
ELEC-HTR2-S/S = RH-STG2
"""

_PRG05_HP_AUX = """\
REM --- HTG-OUTPUT ---
REM HP aux electric: enables when HP running and demand high after delay
REM
IF COMP-CMD = 1 AND HTG-DAT-LOOP > CFG-STG2-T AND AUX-ON-TMR > CFG-AUX-DELAY THEN AUX-HTR-S/S = 1
IF HTG-DAT-LOOP < ( CFG-STG2-T - 10 ) THEN AUX-HTR-S/S = 0
IF COMP-CMD = 0 THEN AUX-HTR-S/S = 0
IF ACT-DAT > 87 THEN AUX-HTR-S/S = 0
IF FREEZE-TRIP = 1 THEN AUX-HTR-S/S = 0
IF AUX-HTR-S/S = 0 THEN AUX-ON-TMR = 0
IF AUX-HTR-S/S = 1 THEN AUX-ON-TMR = 999
"""

# --- Fan programs ---

_PRG06_FAN_CV = """\
REM --- FAN-CTRL ---
REM Constant volume: on when occupied or unoccupied deviation
REM
IF OCC-MODE = 1 THEN FAN-CMD = 1
IF OCC-MODE = 0 AND ( ACT-RMT < CFG-UNOCC-HTG-SP OR ACT-RMT > CFG-UNOCC-CLG-SP ) THEN FAN-CMD = 1
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP AND ACT-RMT < CFG-UNOCC-CLG-SP THEN FAN-CMD = 0
IF FREEZE-TRIP = 1 THEN FAN-CMD = 0
FAN-S/S = FAN-CMD
"""

_PRG06_FAN_MS = """\
REM --- FAN-CTRL ---
REM Multi-speed: speed from max loop demand
REM
FAN-DMD = MAX( CLG-DAT-LOOP, HTG-DAT-LOOP )
IF FAN-DMD < 33 THEN FAN-SPD = 1
IF FAN-DMD >= 33 AND FAN-DMD < 66 THEN FAN-SPD = 2
IF FAN-DMD >= 66 THEN FAN-SPD = 3
FAN-LO = 0
FAN-MED = 0
FAN-HI = 0
IF FAN-SPD = 1 THEN FAN-LO = 1
IF FAN-SPD = 2 THEN FAN-MED = 1
IF FAN-SPD = 3 THEN FAN-HI = 1
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP AND ACT-RMT < CFG-UNOCC-CLG-SP THEN FAN-LO = 0 : FAN-MED = 0 : FAN-HI = 0
IF FREEZE-TRIP = 1 THEN FAN-LO = 0 : FAN-MED = 0 : FAN-HI = 0
"""

_PRG06_FAN_VFD = """\
REM --- FAN-CTRL ---
REM VFD: speed from max loop demand
REM
FAN-DMD = MAX( CLG-DAT-LOOP, HTG-DAT-LOOP )
FAN-SPD = SLIDE( FAN-DMD, 0.0, 100.0, CFG-FAN-MIN-SPD, 100.0 )
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP AND ACT-RMT < CFG-UNOCC-CLG-SP THEN FAN-SPD = 0
IF FREEZE-TRIP = 1 THEN FAN-SPD = 0
"""

# --- Economizer ---

_PRG07_ECON_MOD = """\
REM --- ECON-CTRL ---
REM Economizer modulating damper from CLG-DAT-LOOP
REM
ECON-ENABLE = 0
IF NET-OAT < ACT-RMT AND NET-OAT < CFG-ECON-ENABLE-T THEN ECON-ENABLE = 1
IF ECON-ENABLE = 0 THEN OAD = 0
IF ECON-ENABLE = 1 THEN OAD = CLG-DAT-LOOP
IF FREEZE-TRIP = 1 THEN OAD = 0
"""

_PRG07_ECON_FLT = """\
REM --- ECON-CTRL ---
REM Economizer floating damper using CBAS FLOAT() function
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
REM
REM Economizer enable: OAT < RAT AND OAT < enable temp
ECON-ENABLE = 0
IF NET-OAT < ACT-RMT AND NET-OAT < CFG-ECON-ENABLE-T THEN ECON-ENABLE = 1
REM
REM Position command from cooling loop when enabled
IF ECON-ENABLE = 1 THEN DMP-POS-CMD = CLG-DAT-LOOP ELSE DMP-POS-CMD = 0
REM
REM Safety overrides force damper closed
IF FREEZE-TRIP = 1 THEN DMP-POS-CMD = 0
REM
REM Floating sync on power cycle and economizer disable
IF+ POWER-LOSS THEN START DMP-FLOAT-SYNC
IF+ ECON-ENABLE = 0 THEN START DMP-FLOAT-SYNC
IF TIME-ON( DMP-FLOAT-SYNC ) > 0:00:05 THEN STOP DMP-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays
DMP-POS = FLOAT( DMP-OPEN , DMP-CLOSE , DMP-POS-CMD , CFG-DMP-DRV-TIME , CFG-DMP-POS-DB , DMP-FLOAT-SYNC )
"""

# --- Safety ---

_PRG08_SAFETY = """\
REM --- SAFETY ---
REM Freezestat and DAT limits — latching shutdown
REM
FREEZE-TRIP = 0
IF ACT-DAT < CFG-DAT-FREEZE THEN FREEZE-TRIP = 1
IF FREEZE-STAT = 0 THEN FREEZE-TRIP = 1
IF FREEZE-TRIP = 1 AND FREEZE-LATCH = 0 THEN FREEZE-LATCH = 1
IF FREEZE-LATCH = 1 AND FREEZE-RST = 1 AND ACT-DAT > ( CFG-DAT-FREEZE + 5 ) THEN FREEZE-LATCH = 0
IF FREEZE-LATCH = 1 THEN FREEZE-TRIP = 1
FREEZE-ALARM = FREEZE-LATCH
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Core Module — Always present in every FCU build
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_core():
    """FCU core — sensors, cascade loops, mode, safety"""
    return Module(
        id="fcu-core",
        name="FCU Core",
        category="core",
        description="Base FCU: sensors, cascade loops, mode control, DAT limits, safety",
        is_core=True,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250", "Discharge Air Temperature", "°F"),
            InputPoint(2, "SF-STS", "BI", "Off/On", "Fan Status Feedback"),
            InputPoint(3, "RMT", "AI", "10K -40 ->250", "Room Temperature", "°F"),
        ],

        values=[
            # Sensor reads
            ValuePoint(1, "ACT-RMT",          "AV", 72.0,  "Actual Room Temperature",     "°F"),
            ValuePoint(2, "ACT-DAT",          "AV", 55.0,  "Actual Discharge Air Temp",   "°F"),
            # Single operator zone setpoint + deadband (VAV single-setpoint pattern).
            # AV3/AV4 instances reused from the former CFG-OCC-CLG-SP/CFG-OCC-HTG-SP
            # pair. DB-MTPLR + ACT-RMT-SP-DB mirror VAV core (AV15/AV44) for exact
            # parity: ACT-RMT-SP-DB = DB-MTPLR * CFG-RMT-SP-DB, actives = RMT-SP +/-
            # ACT-RMT-SP-DB (see MODE-CTRL). AV11/AV12 are the next free instances
            # in fcu-core — add all four to the FCU point-location standard.
            ValuePoint(3, "RMT-SP",           "AV", 72.0,  "Operator Room Temp Setpoint", "°F"),
            ValuePoint(4, "CFG-RMT-SP-DB",    "AV", 1.0,   "Room Temp SP Deadband",       "°F"),
            ValuePoint(11, "DB-MTPLR",        "AV", 1.5,   "Deadband Multiplier",         ""),
            ValuePoint(12, "ACT-RMT-SP-DB",   "AV", 1.5,   "Active Setpoint Deadband",    "°F"),
            # Setpoints — unoccupied (unchanged this step)
            ValuePoint(5, "CFG-UNOCC-CLG-SP", "AV", 85.0,  "Unoccupied Cooling Setpoint", "°F"),
            ValuePoint(6, "CFG-UNOCC-HTG-SP", "AV", 60.0,  "Unoccupied Heating Setpoint", "°F"),
            # Active setpoints (computed from RMT-SP +/- ACT-RMT-SP-DB)
            ValuePoint(7, "ACT-CLG-SP",       "AV", 73.5,  "Active Cooling Setpoint",     "°F"),
            ValuePoint(8, "ACT-HTG-SP",       "AV", 70.5,  "Active Heating Setpoint",     "°F"),
            ValuePoint(9, "CLG-SP",           "AV", 73.5,  "Current Cooling SP",          "°F"),
            ValuePoint(10, "HTG-SP",          "AV", 70.5,  "Current Heating SP",          "°F"),
            # DAT setpoint reset (loop outputs)
            ValuePoint(31, "CLG-DAT-SP",      "AV", 55.0,  "Cooling DAT Setpoint",        "°F"),
            ValuePoint(32, "HTG-DAT-SP",      "AV", 95.0,  "Heating DAT Setpoint",        "°F"),
            ValuePoint(33, "CFG-CLG-DAT-MIN", "AV", 52.0,  "Min Cooling DAT SP",          "°F"),
            ValuePoint(34, "CFG-CLG-DAT-MAX", "AV", 65.0,  "Max Cooling DAT SP",          "°F"),
            ValuePoint(35, "CFG-HTG-DAT-MIN", "AV", 85.0,  "Min Heating DAT SP",          "°F"),
            ValuePoint(36, "CFG-HTG-DAT-MAX", "AV", 110.0, "Max Heating DAT SP",          "°F"),
            # DAT safety limits
            ValuePoint(37, "CFG-DAT-LL",      "AV", 45.0,  "DAT Low Limit (safety)",      "°F"),
            ValuePoint(38, "CFG-DAT-HL",      "AV", 110.0, "DAT High Limit (safety)",     "°F"),
            ValuePoint(39, "CFG-DAT-FREEZE",  "AV", 38.0,  "DAT Freeze Protection",       "°F"),
            # Stage thresholds
            ValuePoint(40, "CFG-STG1-T",      "AV", 50.0,  "Stage 1 Threshold",           "%"),
            ValuePoint(41, "CFG-STG2-T",      "AV", 80.0,  "Stage 2 Threshold",           "%"),
            # Network
            ValuePoint(11, "NET-OCC-CMD",     "BV", True,  "Network Occupied Command"),
            ValuePoint(12, "OCC-MODE",        "BV", True,  "Occupancy Mode"),
            ValuePoint(13, "HWS-OK",          "BV", True,  "Hot Water Available"),
            ValuePoint(14, "NET-OAT",         "AV", 65.0,  "Network OAT",                 "°F"),
            # Safety
            ValuePoint(70, "FREEZE-TRIP",     "BV", False, "Freeze Trip Active"),
            ValuePoint(71, "FREEZE-LATCH",    "BV", False, "Freeze Latch"),
            ValuePoint(72, "FREEZE-RST",      "BV", False, "Freeze Reset Command"),
            ValuePoint(73, "FREEZE-ALARM",    "BV", False, "Freeze Alarm"),
            # Fan
            ValuePoint(15, "FAN-CMD",         "BV", False, "Fan Command"),
        ],

        loops=[
            # Primary: space temp resets DAT setpoint
            LoopDef(1, "CLG-RESET-LOOP", "ACT-RMT", "ACT-CLG-SP", "CLG-DAT-SP",
                    p_band=4.0, integral=10.0, action="direct",
                    description="Cooling: space temp resets CLG-DAT-SP"),
            LoopDef(2, "HTG-RESET-LOOP", "ACT-RMT", "ACT-HTG-SP", "HTG-DAT-SP",
                    p_band=4.0, integral=10.0, action="reverse",
                    description="Heating: space temp resets HTG-DAT-SP"),
            # Secondary: DAT drives valve/stage output (output_ref is informational)
            LoopDef(3, "CLG-DAT-LOOP", "ACT-DAT", "CLG-DAT-SP", "CLG-DAT-SP",
                    p_band=8.0, integral=20.0, action="direct",
                    description="Cooling DAT loop drives valve/stage"),
            LoopDef(4, "HTG-DAT-LOOP", "ACT-DAT", "HTG-DAT-SP", "HTG-DAT-SP",
                    p_band=8.0, integral=20.0, action="reverse",
                    description="Heating DAT loop drives valve/stage"),
        ],

        programs=[
            ProgramDef(1, "MODE-CTRL", "PRG01-MODE-CTRL.bas", _PRG01_MODE, True,
                       "Occupancy mode and setpoint selection", exec_order=1),
            ProgramDef(2, "CLG-RESET", "PRG02-CLG-RESET.bas", _PRG02_CLG_RESET, True,
                       "Space temp loop resets CLG-DAT-SP", exec_order=2),
            ProgramDef(3, "HTG-RESET", "PRG03-HTG-RESET.bas", _PRG03_HTG_RESET, True,
                       "Space temp loop resets HTG-DAT-SP", exec_order=3),
        ],

        schedules=[
            ScheduleDef(1, "LOCAL-SCHEDULE", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10,
                        "Local occupancy schedule"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM", "FCU system overview"),
            SystemGroupDef("{device-name}-SET-POINTS", "Setpoints and configuration"),
        ],

        soo_paragraph="""The fan coil unit shall be equipped with a direct digital controller
providing fully automatic cascaded PID control. Primary loops reset
discharge air temperature setpoints based on space temperature. Secondary
DAT loops drive valve position or staging to maintain discharge setpoint.
Freeze protection with latching shutdown and manual reset is standard.""",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Fan Modules (select one)
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_fan_cv():
    """FCU fan — constant volume on/off"""
    return Module(
        id="fcu-fan-cv",
        name="FCU Fan CV",
        category="fan",
        description="Constant volume fan — on/off from occupancy and demand",
        outputs=[
            OutputPoint(1, "FAN-S/S", "BO", "Stop/Start", "Fan Start/Stop"),
        ],
        programs=[
            ProgramDef(6, "FAN-CTRL", "PRG06-FAN-CTRL.bas", _PRG06_FAN_CV, True,
                       "Fan CV — on when occupied or deviation", exec_order=6),
        ],
        requires=["fcu-core"],
        conflicts=["fcu-fan-ms", "fcu-fan-vfd"],
        mutually_exclusive_group="fcu-fan",
    )


def build_fcu_fan_ms():
    """FCU fan — multi-speed"""
    return Module(
        id="fcu-fan-ms",
        name="FCU Fan Multi-Speed",
        category="fan",
        description="Multi-speed fan — low/med/high from max loop demand",
        outputs=[
            OutputPoint(1, "FAN-LO", "BO", "Stop/Start", "Fan Low Speed"),
            OutputPoint(2, "FAN-MED", "BO", "Stop/Start", "Fan Medium Speed"),
            OutputPoint(3, "FAN-HI", "BO", "Stop/Start", "Fan High Speed"),
        ],
        values=[
            ValuePoint(48, "FAN-DMD", "AV", 0.0, "Fan Demand", "%"),
            ValuePoint(49, "FAN-SPD", "AV", 1.0, "Fan Speed Level", ""),
        ],
        programs=[
            ProgramDef(6, "FAN-CTRL", "PRG06-FAN-CTRL.bas", _PRG06_FAN_MS, True,
                       "Fan MS — speed from max loop demand", exec_order=6),
        ],
        requires=["fcu-core"],
        conflicts=["fcu-fan-cv", "fcu-fan-vfd"],
        mutually_exclusive_group="fcu-fan",
    )


def build_fcu_fan_vfd():
    """FCU fan — VFD"""
    return Module(
        id="fcu-fan-vfd",
        name="FCU Fan VFD",
        category="fan",
        description="VFD fan — speed from max loop demand via SLIDE",
        outputs=[
            OutputPoint(1, "FAN-SPD", "AO", "0.0 ->100%", "Fan Speed", 0.0, 10.0),
        ],
        values=[
            ValuePoint(30, "CFG-FAN-MIN-SPD", "AV", 30.0, "Fan Minimum Speed", "%"),
            ValuePoint(48, "FAN-DMD",         "AV", 0.0,  "Fan Demand",        "%"),
        ],
        programs=[
            ProgramDef(6, "FAN-CTRL", "PRG06-FAN-CTRL.bas", _PRG06_FAN_VFD, True,
                       "Fan VFD — speed from max loop demand", exec_order=6),
        ],
        requires=["fcu-core"],
        conflicts=["fcu-fan-cv", "fcu-fan-ms"],
        mutually_exclusive_group="fcu-fan",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Cooling Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_chw_mod():
    """CHW modulating valve"""
    return Module(
        id="fcu-chw-mod", name="FCU CHW Modulating", category="cooling",
        description="CHW modulating valve — AO driven by CLG-DAT-LOOP",
        outputs=[OutputPoint(4, "CHW-VLV", "AO", "0.0 ->100%", "CHW Valve", 2.0, 10.0)],
        programs=[ProgramDef(4, "CLG-OUTPUT", "PRG04-CLG-OUTPUT.bas", _PRG04_CHW_MOD, True,
                             "CHW mod valve = CLG-DAT-LOOP", exec_order=4)],
        requires=["fcu-core"],
        conflicts=["fcu-chw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt", "fcu-dx-1", "fcu-dx-2", "fcu-hp-core"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_chw_flt():
    """CHW floating point valve"""
    return Module(
        id="fcu-chw-flt", name="FCU CHW Floating", category="cooling",
        description="CHW floating valve — CBAS FLOAT() function drives open/close relays",
        outputs=[
            OutputPoint(4, "CHW-OPEN",  "BO", "Stop/Start", "CHW Valve Open"),
            OutputPoint(5, "CHW-CLOSE", "BO", "Stop/Start", "CHW Valve Close"),
        ],
        values=[
            ValuePoint(45, "CHW-POS",          "AV", 0.0,   "CHW Valve Actual Position",      "%"),
            ValuePoint(46, "CHW-POS-CMD",      "AV", 0.0,   "CHW Valve Commanded Position",   "%"),
            ValuePoint(90, "CFG-CHW-POS-DB",   "AV", 2.0,   "CHW Float Position Deadband",    "%"),
            ValuePoint(91, "CFG-CHW-DRV-TIME", "AV", 150.0, "CHW Valve Full Stroke Time",     "Sec"),
            ValuePoint(92, "CHW-FLOAT-SYNC",   "BV", False, "CHW Float Sync Trigger"),
        ],
        programs=[ProgramDef(4, "CLG-OUTPUT", "PRG04-CLG-OUTPUT.bas", _PRG04_CHW_FLT, True,
                             "CHW float = CLG-DAT-LOOP vs position", exec_order=4)],
        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-2pipe-mod", "fcu-2pipe-flt", "fcu-dx-1", "fcu-dx-2", "fcu-hp-core"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_2pipe_mod():
    """2-pipe switchover modulating"""
    return Module(
        id="fcu-2pipe-mod", name="FCU 2-Pipe Modulating", category="cooling",
        description="2-pipe switchover — single AO valve from active DAT loop",
        outputs=[OutputPoint(4, "VALVE", "AO", "0.0 ->100%", "2-Pipe Valve", 2.0, 10.0)],
        values=[
            ValuePoint(42, "PIPE-MODE",        "BV", False, "Pipe Mode (1=heat 0=cool)"),
            ValuePoint(43, "CFG-SWITCHOVER-T", "AV", 55.0,  "Switchover Temperature", "°F"),
        ],
        programs=[ProgramDef(4, "CLG-OUTPUT", "PRG04-CLG-OUTPUT.bas", _PRG04_2PIPE_MOD, True,
                             "2-pipe mod = active DAT loop by mode", exec_order=4)],
        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-flt", "fcu-dx-1", "fcu-dx-2", "fcu-hp-core",
                   "fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_2pipe_flt():
    """2-pipe switchover floating"""
    return Module(
        id="fcu-2pipe-flt", name="FCU 2-Pipe Floating", category="cooling",
        description="2-pipe switchover floating valve — CBAS FLOAT() function",
        outputs=[
            OutputPoint(4, "VLV-OPEN",  "BO", "Stop/Start", "2-Pipe Valve Open"),
            OutputPoint(5, "VLV-CLOSE", "BO", "Stop/Start", "2-Pipe Valve Close"),
        ],
        values=[
            ValuePoint(42, "PIPE-MODE",        "BV", False, "Pipe Mode (1=heat 0=cool)"),
            ValuePoint(43, "CFG-SWITCHOVER-T", "AV", 55.0,  "Switchover Temperature",        "°F"),
            ValuePoint(44, "VLV-POS",          "AV", 0.0,   "Valve Actual Position",         "%"),
            ValuePoint(47, "ACTIVE-DMD",       "AV", 0.0,   "Active Demand",                 "%"),
            ValuePoint(48, "VLV-POS-CMD",      "AV", 0.0,   "Valve Commanded Position",      "%"),
            ValuePoint(90, "CFG-VLV-POS-DB",   "AV", 2.0,   "Valve Float Position Deadband", "%"),
            ValuePoint(91, "CFG-VLV-DRV-TIME", "AV", 150.0, "Valve Full Stroke Time",        "Sec"),
            ValuePoint(92, "VLV-FLOAT-SYNC",   "BV", False, "Valve Float Sync Trigger"),
        ],
        programs=[ProgramDef(4, "CLG-OUTPUT", "PRG04-CLG-OUTPUT.bas", _PRG04_2PIPE_FLT, True,
                             "2-pipe float = active DAT loop vs position", exec_order=4)],
        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-mod", "fcu-dx-1", "fcu-dx-2", "fcu-hp-core",
                   "fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_dx_1():
    """DX single stage"""
    return Module(
        id="fcu-dx-1", name="FCU DX 1-Stage", category="cooling",
        description="DX single stage — CLG-DAT-LOOP > threshold, 3min off-timer",
        outputs=[OutputPoint(4, "DX-STG1", "BO", "Stop/Start", "DX Compressor Stage 1")],
        values=[ValuePoint(50, "DX1-OFF-TMR", "AV", 999.0, "DX1 Off Timer", "Sec")],
        programs=[ProgramDef(4, "CLG-OUTPUT", "PRG04-CLG-OUTPUT.bas", _PRG04_DX_1, True,
                             "DX stg1 = CLG-DAT-LOOP > threshold", exec_order=4)],
        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt", "fcu-dx-2", "fcu-hp-core"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_dx_2():
    """DX two stage"""
    return Module(
        id="fcu-dx-2", name="FCU DX 2-Stage", category="cooling",
        description="DX 2-stage — stg1 3min off-timer, stg2 requires stg1 + 5min delay",
        outputs=[
            OutputPoint(4, "DX-STG1", "BO", "Stop/Start", "DX Compressor Stage 1"),
            OutputPoint(5, "DX-STG2", "BO", "Stop/Start", "DX Compressor Stage 2"),
        ],
        values=[
            ValuePoint(50, "DX1-OFF-TMR", "AV", 999.0, "DX1 Off Timer", "Sec"),
            ValuePoint(51, "DX2-OFF-TMR", "AV", 999.0, "DX2 Off Timer", "Sec"),
        ],
        programs=[ProgramDef(4, "CLG-OUTPUT", "PRG04-CLG-OUTPUT.bas", _PRG04_DX_2, True,
                             "DX 2-stage = CLG-DAT-LOOP > thresholds", exec_order=4)],
        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt", "fcu-dx-1", "fcu-hp-core"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_hp_core():
    """Heat pump — compressor + reversing valve"""
    return Module(
        id="fcu-hp-core", name="FCU Heat Pump", category="cooling",
        description="Heat pump — compressor + RV from active DAT loop, CFG-RV-CLG config",
        outputs=[
            OutputPoint(4, "COMP-S/S", "BO", "Stop/Start", "Compressor"),
            OutputPoint(5, "RV", "BO", "Stop/Start", "Reversing Valve"),
        ],
        values=[
            ValuePoint(50, "COMP-CMD",     "BV", False, "Compressor Command"),
            ValuePoint(51, "RV-CMD",       "BV", False, "Reversing Valve Command"),
            ValuePoint(52, "HP-MODE",      "BV", False, "HP Mode (1=heat 0=cool)"),
            ValuePoint(53, "HP-DMD",       "AV", 0.0,   "HP Demand",           "%"),
            ValuePoint(54, "COMP-ON-TMR",  "AV", 999.0, "Compressor On Timer", "Sec"),
            ValuePoint(55, "CFG-RV-CLG",   "BV", True,  "RV Energized in Cooling"),
            ValuePoint(56, "CFG-HP-MIN",   "AV", 10.0,  "HP Min Demand",       "%"),
        ],
        programs=[ProgramDef(4, "HP-CTRL", "PRG04-HP-CTRL.bas", _PRG04_HP, True,
                             "HP compressor+RV from active DAT loop", exec_order=4)],
        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-dx-1", "fcu-dx-2", "fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-cooling",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Heating Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_hw_mod():
    """HW modulating valve"""
    return Module(
        id="fcu-hw-mod", name="FCU HW Modulating", category="heating",
        description="HW modulating valve — AO driven by HTG-DAT-LOOP",
        outputs=[OutputPoint(6, "HW-VLV", "AO", "0.0 ->100%", "HW Valve (reverse)", 10.0, 2.0, True)],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HW_MOD, True,
                             "HW mod valve = HTG-DAT-LOOP", exec_order=5)],
        requires=["fcu-core"],
        conflicts=["fcu-hw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt", "fcu-hp-core", "fcu-hp-aux"],
        mutually_exclusive_group="fcu-heating",
    )


def build_fcu_hw_flt():
    """HW floating point valve"""
    return Module(
        id="fcu-hw-flt", name="FCU HW Floating", category="heating",
        description="HW floating valve — CBAS FLOAT() function drives open/close relays",
        outputs=[
            OutputPoint(6, "RH-OPEN",  "BO", "Stop/Start", "HW Valve Open"),
            OutputPoint(7, "RH-CLOSE", "BO", "Stop/Start", "HW Valve Close"),
        ],
        values=[
            ValuePoint(50, "RH-POS",          "AV", 0.0,   "HW Valve Actual Position",     "%"),
            ValuePoint(51, "RH-POS-CMD",      "AV", 0.0,   "HW Valve Commanded Position",  "%"),
            ValuePoint(93, "CFG-RH-POS-DB",   "AV", 2.0,   "HW Float Position Deadband",   "%"),
            ValuePoint(94, "CFG-RH-DRV-TIME", "AV", 150.0, "HW Valve Full Stroke Time",    "Sec"),
            ValuePoint(95, "RH-FLOAT-SYNC",   "BV", False, "HW Float Sync Trigger"),
        ],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HW_FLT, True,
                             "HW float = HTG-DAT-LOOP vs position", exec_order=5)],
        requires=["fcu-core"],
        conflicts=["fcu-hw-mod", "fcu-2pipe-mod", "fcu-2pipe-flt", "fcu-hp-core", "fcu-hp-aux"],
        mutually_exclusive_group="fcu-heating",
    )


def build_fcu_elec_1():
    """Electric 1-stage"""
    return Module(
        id="fcu-elec-1", name="FCU Electric 1-Stage", category="heating",
        description="Electric 1-stage — BO from HTG-DAT-LOOP > threshold",
        outputs=[OutputPoint(8, "ELEC-HTR-S/S", "BO", "Stop/Start", "Electric Heater")],
        values=[ValuePoint(60, "RH-STG1", "BV", False, "Reheat Stage 1 Command")],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_ELEC_1, True,
                             "Electric stg1 = HTG-DAT-LOOP > threshold", exec_order=5)],
        requires=["fcu-core"],
        conflicts=["fcu-elec-2", "fcu-2pipe-mod", "fcu-2pipe-flt", "fcu-hp-core", "fcu-hp-aux"],
    )


def build_fcu_elec_2():
    """Electric 2-stage"""
    return Module(
        id="fcu-elec-2", name="FCU Electric 2-Stage", category="heating",
        description="Electric 2-stage — stg2 requires stg1 on, DAT < 87F",
        outputs=[
            OutputPoint(8, "ELEC-HTR1-S/S", "BO", "Stop/Start", "Electric Heater Stage 1"),
            OutputPoint(9, "ELEC-HTR2-S/S", "BO", "Stop/Start", "Electric Heater Stage 2"),
        ],
        values=[
            ValuePoint(60, "RH-STG1", "BV", False, "Reheat Stage 1"),
            ValuePoint(61, "RH-STG2", "BV", False, "Reheat Stage 2"),
        ],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_ELEC_2, True,
                             "Electric 2-stg = HTG-DAT-LOOP > thresholds", exec_order=5)],
        requires=["fcu-core"],
        conflicts=["fcu-elec-1", "fcu-2pipe-mod", "fcu-2pipe-flt", "fcu-hp-core", "fcu-hp-aux"],
    )


def build_fcu_hp_aux():
    """HP aux electric heat"""
    return Module(
        id="fcu-hp-aux", name="FCU HP Aux Electric", category="heating",
        description="HP aux heat — enables after delay when HP demand high",
        outputs=[OutputPoint(6, "AUX-HTR-S/S", "BO", "Stop/Start", "Aux Electric Heater")],
        values=[
            ValuePoint(57, "CFG-AUX-DELAY", "AV", 600.0, "Aux Heat Delay", "Sec"),
            ValuePoint(58, "AUX-ON-TMR",    "AV", 0.0,   "Aux On Timer",   "Sec"),
        ],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HP_AUX, True,
                             "HP aux = HTG-DAT-LOOP > threshold after delay", exec_order=5)],
        requires=["fcu-hp-core"],
        conflicts=["fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-heating",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Economizer Modules (optional)
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_econ_mod():
    """Economizer modulating"""
    return Module(
        id="fcu-econ-mod", name="FCU Economizer Modulating", category="economizer",
        description="Economizer AO damper = CLG-DAT-LOOP when OAT < RAT",
        outputs=[OutputPoint(10, "OAD", "AO", "0.0 ->100%", "OA Damper", 2.0, 10.0)],
        values=[
            ValuePoint(80, "CFG-ECON-ENABLE-T", "AV", 65.0, "Economizer Enable Temp", "°F"),
            ValuePoint(81, "ECON-ENABLE",       "BV", False, "Economizer Enabled"),
        ],
        programs=[ProgramDef(7, "ECON-CTRL", "PRG07-ECON-CTRL.bas", _PRG07_ECON_MOD, True,
                             "Economizer mod = CLG-DAT-LOOP when enabled", exec_order=7)],
        requires=["fcu-core"],
        conflicts=["fcu-econ-flt"],
        mutually_exclusive_group="fcu-econ",
    )


def build_fcu_econ_flt():
    """Economizer floating"""
    return Module(
        id="fcu-econ-flt", name="FCU Economizer Floating", category="economizer",
        description="Economizer floating damper — CBAS FLOAT() function",
        outputs=[
            OutputPoint(10, "DMP-OPEN",  "BO", "Stop/Start", "OA Damper Open"),
            OutputPoint(11, "DMP-CLOSE", "BO", "Stop/Start", "OA Damper Close"),
        ],
        values=[
            ValuePoint(80, "CFG-ECON-ENABLE-T", "AV", 65.0,  "Economizer Enable Temp",         "°F"),
            ValuePoint(81, "ECON-ENABLE",       "BV", False, "Economizer Enabled"),
            ValuePoint(82, "DMP-POS",           "AV", 0.0,   "OA Damper Actual Position",     "%"),
            ValuePoint(83, "DMP-POS-CMD",       "AV", 0.0,   "OA Damper Commanded Position",  "%"),
            ValuePoint(96, "CFG-DMP-POS-DB",    "AV", 2.0,   "Damper Float Position Deadband","%"),
            ValuePoint(97, "CFG-DMP-DRV-TIME",  "AV", 150.0, "Damper Full Stroke Time",       "Sec"),
            ValuePoint(98, "DMP-FLOAT-SYNC",    "BV", False, "Damper Float Sync Trigger"),
        ],
        programs=[ProgramDef(7, "ECON-CTRL", "PRG07-ECON-CTRL.bas", _PRG07_ECON_FLT, True,
                             "Economizer float = CLG-DAT-LOOP vs position", exec_order=7)],
        requires=["fcu-core"],
        conflicts=["fcu-econ-mod"],
        mutually_exclusive_group="fcu-econ",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Freezestat Module (optional — adds BI input)
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_freezestat():
    """Freezestat BI input — adds hardware contact to safety program"""
    return Module(
        id="fcu-freezestat", name="FCU Freezestat", category="safety",
        description="Freezestat BI contact — hardware trip input for safety program",
        inputs=[
            InputPoint(4, "FREEZE-STAT", "BI", "Normal/Alarm", "Freezestat Contact"),
        ],
        programs=[ProgramDef(8, "SAFETY", "PRG08-SAFETY.bas", _PRG08_SAFETY, True,
                             "Freezestat + DAT freeze protection, latch/reset", exec_order=8)],
        requires=["fcu-core"],
    )
