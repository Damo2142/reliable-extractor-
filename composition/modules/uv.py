"""
UV (Unit Ventilator) Modules — All variants

Families: HW+OAD, HW+FBP, Steam+OAD, Steam+FBP,
          CHW+HW+OAD, CHW+HW+FBP, DX+HW+OAD, DX+HW+FBP

Standard I/O:
  AI1 = DAT (discharge air temp, 10K type III, mandatory)
  AI2 = OAT (outdoor air temp, 10K type III)
  RMT (room temp) — from thermostat module (vav-stat-hardwired AI3 wired,
       or stat-remote network read); no longer hardwired in uv-core
  BI = SF-STS (fan status feedback)

Control Architecture — single-setpoint cascade with a latching mode arbiter:

  One effective zone setpoint (EFF-RMT-SP) with one deadband
  -> latching HVAC-MODE arbiter (1=Vent 2=Cool 3=Reheat 4=Heat 5=Init)
  -> one DAT setpoint (DAT-SP) reset by one RESET-LOOP
  -> one DAT-LOOP whose ACTION FLIPS BY MODE (LOOP:2, 0=direct 1=reverse)
  -> the idle coil is forced closed three independent ways.

  There is exactly ONE live DAT loop. Heating and cooling can never modulate
  at the same time: the modes are mutually exclusive, each coil is gated on
  its own mode, and each coil re-checks the loop action before it drives.
  Reheat (3) exists only to keep the enum aligned with VAV — UV never sets it.

  PRG01 MODE-CTRL: network reads, occupancy mode, EFF-RMT-SP, mode arbiter
  PRG02 DAT-RESET: RESET-LOOP slides the single DAT-SP
  PRG04 FBP-CTRL: face/bypass cold/mild mode (FBP families)
  PRG05 HTG-OUTPUT: heating valve from DAT-LOOP, MAX'd with DAT-LL-LOOP
  PRG06 CLG-OUTPUT: cooling valve/stage from DAT-LOOP
  PRG07 OAD-CTRL: OA damper ASHRAE Cycle 1+2 (OAD families)
  PRG08 FAN-CTRL: fan on/off or VFD speed
  PRG09 DCV-CTRL: CO2 demand-controlled ventilation (optional)
  PRG10 FREEZESTAT: hardware freezestat + DAT latch (optional)
  PRG12 MECH-CLG-ENAB-PRG: mech cooling enable, latched on damper position
  PRG13 RAD-HTG-PRG: radiant heat OAT reset (optional add-on)

Controller: MACH-ProZone 88 standard, MACH-ProView LCD optional
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
#  Program Code
# ═══════════════════════════════════════════════════════════════════════════

_PRG01_MODE = """\
REM --- MODE-CTRL ---
REM *** VERIFY PARENT BV20=OCC-CMD BV22=HW-AVAIL AV1=OUTSIDE-AIR ***
NET-OCC-CMD = {parent}BV20
HWS-OK = {parent}BV22
NET-OAT = {parent}AV1
REM --- Outside air source ---
IF NET-OAT > -60 AND NET-OAT < 140 THEN NET-OAT-OK = 1 ELSE NET-OAT-OK = 0
IF CFG-OAT-LOCAL OR NOT NET-OAT-OK THEN ACT-OAT = OAT
IF NOT CFG-OAT-LOCAL AND NET-OAT-OK THEN ACT-OAT = NET-OAT
ACT-DAT = DAT
REM --- Occupancy mode ---
REM 1=Occupied 2=Bypass 3=Standby 4=Unoccupied 5=NSB 6=NSF
IF NET-OCC-CMD THEN OCC-MODE = 1
IF NOT NET-OCC-CMD THEN OCC-MODE = 4
ACT-RMT-SP-DB = DB-MTPLR * CFG-RMT-SP-DB
F = SWITCH( F , ACT-RMT , NSB-SP + ACT-RMT-SP-DB , NSB-SP )
G = SWITCH( G , ACT-RMT , NSF-SP - ACT-RMT-SP-DB , NSF-SP )
IF OCC-MODE = 4 AND F THEN OCC-MODE = 5
IF OCC-MODE = 4 AND G THEN OCC-MODE = 6
REM --- Effective setpoint ---
IF OCC-MODE <= 3 THEN EFF-RMT-SP = RMT-SP
IF OCC-MODE = 4 THEN EFF-RMT-SP = NSB-SP
IF OCC-MODE = 5 THEN EFF-RMT-SP = NSB-SP
IF OCC-MODE = 6 THEN EFF-RMT-SP = NSF-SP
CLG-SP = EFF-RMT-SP + ACT-RMT-SP-DB
HTG-SP = EFF-RMT-SP - ACT-RMT-SP-DB
REM --- Mode arbiter ---
REM 1=Ventilation 2=Cool 3=Reheat 4=Heat 5=Initialize
D = SWITCH( D , ACT-RMT , EFF-RMT-SP , EFF-RMT-SP - ACT-RMT-SP-DB )
IF D THEN HVAC-MODE = 4 , GOTO 340
E = SWITCH( E , ACT-RMT , EFF-RMT-SP , EFF-RMT-SP + ACT-RMT-SP-DB )
IF E THEN HVAC-MODE = 2 ELSE HVAC-MODE = 1
REM LOOP:2 action 0=direct 1=reverse
IF HVAC-MODE = 4 THEN DAT-LOOP:2 = 1
IF HVAC-MODE = 2 THEN DAT-LOOP:2 = 0
IF OCC-MODE = 4 THEN HVAC-MODE = 1
IF POWER-LOSS THEN START INIT-MODE
IF TIME-ON( INIT-MODE ) > 0:05:00 THEN STOP INIT-MODE
IF INIT-MODE THEN HVAC-MODE = 5
"""

_PRG02_DAT_RESET = """\
REM --- DAT-RESET ---
DAT-SP = SLIDE( RESET-LOOP , 0 , 100 , CFG-DAT-MIN-SP , CFG-DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP , CFG-DAT-MIN-SP , CFG-DAT-MAX-SP )
"""

_PRG02B_CAB_PROT = """\
REM --- CAB-PROT-RESET ---
IF ACT-OAT >= CFG-CAB-OAT-HI THEN CAB-PROT-VLV = CFG-CAB-VLV-MIN
IF ACT-OAT <= CFG-CAB-OAT-LO THEN CAB-PROT-VLV = CFG-CAB-VLV-MAX
IF ACT-OAT > CFG-CAB-OAT-LO AND ACT-OAT < CFG-CAB-OAT-HI THEN CAB-PROT-VLV = CFG-CAB-VLV-MAX - ( ( ACT-OAT - CFG-CAB-OAT-LO ) / ( CFG-CAB-OAT-HI - CFG-CAB-OAT-LO ) ) * ( CFG-CAB-VLV-MAX - CFG-CAB-VLV-MIN )
"""

_PRG04_FBP = """\
REM --- FBP-CTRL ---
REM FBP-MODE 1=cold (valve open, damper modulates) 0=mild (full face)
IF FRZ-SD THEN FBP = 100 , HW-DEMAND = 100 , END
IF OCC-MODE = 6 THEN FBP = 100 , HW-DEMAND = 0 , END
IF OCC-MODE = 5 THEN FBP = 100 , HW-DEMAND = CFG-NSB-HTG-POS , END
IF ACT-OAT < CFG-FBP-SWITCHOVER-T THEN FBP-MODE = 1 ELSE FBP-MODE = 0
A = DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN A = 0
IF HVAC-MODE < 3 THEN A = 0
IF DAT-LOOP:2 = 0 THEN A = 0
A = MAX( A , DAT-LL-LOOP )
IF HVAC-MODE = 5 THEN A = 100
IF FBP-MODE = 1 THEN HW-DEMAND = 100
IF FBP-MODE = 1 THEN FBP = A
IF FBP-MODE = 0 THEN FBP = 100
IF FBP-MODE = 0 THEN HW-DEMAND = A
"""

_PRG04_FBP_FLT = """\
REM --- FBP-CTRL ---
REM FBP-MODE 1=cold (valve open, damper modulates) 0=mild (full face)
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
IF FRZ-SD THEN FBP-POS-CMD = 100 , HW-DEMAND = 100 , GOTO 220
IF OCC-MODE = 6 THEN FBP-POS-CMD = 100 , HW-DEMAND = 0 , GOTO 220
IF OCC-MODE = 5 THEN FBP-POS-CMD = 100 , HW-DEMAND = CFG-NSB-HTG-POS , GOTO 220
IF ACT-OAT < CFG-FBP-SWITCHOVER-T THEN FBP-MODE = 1 ELSE FBP-MODE = 0
A = DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN A = 0
IF HVAC-MODE < 3 THEN A = 0
IF DAT-LOOP:2 = 0 THEN A = 0
A = MAX( A , DAT-LL-LOOP )
IF HVAC-MODE = 5 THEN A = 100
IF FBP-MODE = 1 THEN FBP-POS-CMD = A
IF FBP-MODE = 1 THEN HW-DEMAND = 100
IF FBP-MODE = 0 THEN FBP-POS-CMD = 100
IF FBP-MODE = 0 THEN HW-DEMAND = A
IF+ POWER-LOSS THEN START FBP-FLOAT-SYNC
IF+ FBP-MODE = 1 THEN START FBP-FLOAT-SYNC
IF+ FBP-MODE = 0 THEN START FBP-FLOAT-SYNC
IF TIME-ON( FBP-FLOAT-SYNC ) > 0:00:05 THEN STOP FBP-FLOAT-SYNC
FBP-POS = FLOAT( FBP-OPEN , FBP-CLOSE , FBP-POS-CMD , CFG-FBP-DRV-TIME , CFG-FBP-POS-DB , FBP-FLOAT-SYNC )
"""

_PRG05_STEAM_ONOFF_FBP = """\
REM --- HTG-OUTPUT ---
REM FBP-MODE is set by FBP-CTRL
IF FRZ-SD THEN STM-VLV = 1 , END
IF OCC-MODE = 6 THEN STM-VLV = 0 , END
IF OCC-MODE = 5 THEN STM-VLV = ( CFG-NSB-HTG-POS > 0 ) , GOTO 170
A = DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN A = 0
IF HVAC-MODE < 3 THEN A = 0
IF DAT-LOOP:2 = 0 THEN A = 0
A = MAX( A , DAT-LL-LOOP )
IF FBP-MODE = 1 AND A > 0 THEN STM-VLV = 1
IF FBP-MODE = 0 AND A > 50 THEN STM-VLV = 1
IF FBP-MODE = 0 AND A < 40 THEN STM-VLV = 0
IF A = 0 THEN STM-VLV = 0
IF HVAC-MODE = 5 THEN STM-VLV = 1
IF OCC-MODE >= 4 AND ACT-OAT < CFG-CAB-OAT-HI THEN STM-VLV = 1
IF ACT-DAT > CFG-DAT-HL THEN STM-VLV = 0
"""

_PRG05_HW_MOD = """\
REM --- HTG-OUTPUT ---
IF FRZ-SD THEN HW-VLV = 100 , END
IF OCC-MODE = 6 THEN HW-VLV = 0 , END
IF OCC-MODE = 5 THEN HW-VLV = CFG-NSB-HTG-POS , GOTO 120
A = DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN A = 0
IF HVAC-MODE < 3 THEN A = 0
IF DAT-LOOP:2 = 0 THEN A = 0
HW-VLV = MAX( A , DAT-LL-LOOP )
IF HVAC-MODE = 5 THEN HW-VLV = 100
IF OCC-MODE >= 4 AND ACT-OAT < CFG-CAB-OAT-HI THEN HW-VLV = MAX( CAB-PROT-VLV , DAT-LL-LOOP )
IF ACT-DAT > CFG-DAT-HL THEN HW-VLV = 0
"""

_PRG05_HW_FLT = """\
REM --- HTG-OUTPUT ---
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
IF FRZ-SD THEN RH-POS-CMD = 100 , GOTO 170
IF OCC-MODE = 6 THEN RH-POS-CMD = 0 , GOTO 170
IF OCC-MODE = 5 THEN RH-POS-CMD = CFG-NSB-HTG-POS , GOTO 130
A = DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN A = 0
IF HVAC-MODE < 3 THEN A = 0
IF DAT-LOOP:2 = 0 THEN A = 0
RH-POS-CMD = MAX( A , DAT-LL-LOOP )
IF HVAC-MODE = 5 THEN RH-POS-CMD = 100
IF OCC-MODE >= 4 AND ACT-OAT < CFG-CAB-OAT-HI THEN RH-POS-CMD = MAX( CAB-PROT-VLV , DAT-LL-LOOP )
IF ACT-DAT > CFG-DAT-HL THEN RH-POS-CMD = 0
IF+ POWER-LOSS THEN START RH-FLOAT-SYNC
IF+ OCC-MODE >= 4 THEN START RH-FLOAT-SYNC
IF TIME-ON( RH-FLOAT-SYNC ) > 0:00:05 THEN STOP RH-FLOAT-SYNC
RH-POS = FLOAT( RH-OPEN , RH-CLOSE , RH-POS-CMD , CFG-RH-DRV-TIME , CFG-RH-POS-DB , RH-FLOAT-SYNC )
"""

_PRG05_STEAM_MOD = """\
REM --- HTG-OUTPUT ---
IF FRZ-SD THEN STM-VLV = 100 , END
IF OCC-MODE = 6 THEN STM-VLV = 0 , END
IF OCC-MODE = 5 THEN STM-VLV = CFG-NSB-HTG-POS , GOTO 110
A = DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN A = 0
IF HVAC-MODE < 3 THEN A = 0
IF DAT-LOOP:2 = 0 THEN A = 0
STM-VLV = MAX( A , DAT-LL-LOOP )
IF HVAC-MODE = 5 THEN STM-VLV = 100
IF ACT-DAT > CFG-DAT-HL THEN STM-VLV = 0
"""

_PRG05_STEAM_ONOFF = """\
REM --- HTG-OUTPUT ---
IF FRZ-SD THEN STM-VLV = 1 , END
IF OCC-MODE = 6 THEN STM-VLV = 0 , END
IF OCC-MODE = 5 THEN STM-VLV = ( CFG-NSB-HTG-POS > 0 ) , GOTO 140
A = DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN A = 0
IF HVAC-MODE < 3 THEN A = 0
IF DAT-LOOP:2 = 0 THEN A = 0
A = MAX( A , DAT-LL-LOOP )
IF A > 50 THEN STM-VLV = 1
IF A < 40 THEN STM-VLV = 0
IF HVAC-MODE = 5 THEN STM-VLV = 1
IF OCC-MODE >= 4 AND ACT-OAT < CFG-CAB-OAT-HI THEN STM-VLV = 1
IF ACT-DAT > CFG-DAT-HL THEN STM-VLV = 0
"""

_PRG05_HW_MOD_FBP = """\
REM --- HTG-OUTPUT ---
REM HW-DEMAND is set by FBP-CTRL, already mode and action guarded
IF FRZ-SD THEN HW-VLV = 100 , END
IF OCC-MODE = 6 THEN HW-VLV = 0 , END
IF OCC-MODE = 5 THEN HW-VLV = CFG-NSB-HTG-POS , GOTO 80
HW-VLV = HW-DEMAND
IF HVAC-MODE = 5 THEN HW-VLV = 100
IF ACT-DAT > CFG-DAT-HL THEN HW-VLV = 0
"""

_PRG06_CHW_MOD = """\
REM --- CLG-OUTPUT ---
IF FRZ-SD THEN CHW-VLV = 0 , END
IF OCC-MODE = 5 THEN CHW-VLV = 0 , END
IF OCC-MODE = 6 THEN CHW-VLV = CFG-NSF-CLG-POS , GOTO 120
A = DAT-LOOP
IF ACT-DAT < CFG-DAT-LL THEN A = 0
IF OCC-MODE >= 4 THEN A = 0
IF HVAC-MODE <> 2 THEN A = 0
IF DAT-LOOP:2 = 1 THEN A = 0
IF NOT MECH-CLG-ENAB THEN A = 0
CHW-VLV = A
IF ACT-DAT < CFG-DAT-LL THEN CHW-VLV = 0
"""

_PRG06_CHW_FLT = """\
REM --- CLG-OUTPUT ---
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
IF FRZ-SD THEN CHW-POS-CMD = 0 , GOTO 170
IF OCC-MODE = 5 THEN CHW-POS-CMD = 0 , GOTO 170
IF OCC-MODE = 6 THEN CHW-POS-CMD = CFG-NSF-CLG-POS , GOTO 130
A = DAT-LOOP
IF ACT-DAT < CFG-DAT-LL THEN A = 0
IF OCC-MODE >= 4 THEN A = 0
IF HVAC-MODE <> 2 THEN A = 0
IF DAT-LOOP:2 = 1 THEN A = 0
IF NOT MECH-CLG-ENAB THEN A = 0
CHW-POS-CMD = A
IF ACT-DAT < CFG-DAT-LL THEN CHW-POS-CMD = 0
IF+ POWER-LOSS THEN START CHW-FLOAT-SYNC
IF+ OCC-MODE >= 4 THEN START CHW-FLOAT-SYNC
IF TIME-ON( CHW-FLOAT-SYNC ) > 0:00:05 THEN STOP CHW-FLOAT-SYNC
CHW-POS = FLOAT( CHW-OPEN , CHW-CLOSE , CHW-POS-CMD , CFG-CHW-DRV-TIME , CFG-CHW-POS-DB , CHW-FLOAT-SYNC )
"""

_PRG06_DX_1 = """\
REM --- CLG-OUTPUT ---
IF FRZ-SD THEN DX-STG1 = 0 , END
IF OCC-MODE = 5 THEN DX-STG1 = 0 , END
IF OCC-MODE = 6 AND DX1-OFF-TMR > 180 THEN DX-STG1 = 1
IF OCC-MODE = 6 THEN GOTO 140
A = DAT-LOOP
IF ACT-DAT < CFG-DAT-LL THEN A = 0
IF OCC-MODE >= 4 THEN A = 0
IF HVAC-MODE <> 2 THEN A = 0
IF DAT-LOOP:2 = 1 THEN A = 0
IF NOT MECH-CLG-ENAB THEN A = 0
IF A > CFG-STG1-T AND DX1-OFF-TMR > 180 THEN DX-STG1 = 1
IF A < ( CFG-STG1-T - 10 ) THEN DX-STG1 = 0
IF ACT-DAT < CFG-DAT-LL THEN DX-STG1 = 0
IF DX-STG1 = 0 THEN DX1-OFF-TMR = 0
IF DX-STG1 = 1 THEN DX1-OFF-TMR = 999
"""

_PRG06_DX_2 = """\
REM --- CLG-OUTPUT ---
IF FRZ-SD THEN DX-STG1 = 0 , DX-STG2 = 0 , END
IF OCC-MODE = 5 THEN DX-STG1 = 0 , DX-STG2 = 0 , END
IF OCC-MODE = 6 AND DX1-OFF-TMR > 180 THEN DX-STG1 = 1
IF OCC-MODE = 6 AND CFG-NSF-CLG-POS > 50 AND DX2-OFF-TMR > 300 THEN DX-STG2 = 1
IF OCC-MODE = 6 AND CFG-NSF-CLG-POS <= 50 THEN DX-STG2 = 0
IF OCC-MODE = 6 THEN GOTO 180
A = DAT-LOOP
IF ACT-DAT < CFG-DAT-LL THEN A = 0
IF OCC-MODE >= 4 THEN A = 0
IF HVAC-MODE <> 2 THEN A = 0
IF DAT-LOOP:2 = 1 THEN A = 0
IF NOT MECH-CLG-ENAB THEN A = 0
IF A > CFG-STG1-T AND DX1-OFF-TMR > 180 THEN DX-STG1 = 1
IF A < ( CFG-STG1-T - 10 ) THEN DX-STG1 = 0
IF A > CFG-STG2-T AND DX-STG1 = 1 AND DX2-OFF-TMR > 300 THEN DX-STG2 = 1
IF A < ( CFG-STG2-T - 10 ) THEN DX-STG2 = 0
IF ACT-DAT < CFG-DAT-LL THEN DX-STG1 = 0 , DX-STG2 = 0
IF DX-STG1 = 0 THEN DX1-OFF-TMR = 0 : DX-STG2 = 0
IF DX-STG1 = 1 THEN DX1-OFF-TMR = 999
IF DX-STG2 = 0 THEN DX2-OFF-TMR = 0
IF DX-STG2 = 1 THEN DX2-OFF-TMR = 999
"""

_PRG07_OAD = """\
REM --- OAD-CTRL ---
REM ASHRAE Cycle 1 (min OA) + Cycle 2 (free cooling)
IF FRZ-SD THEN OAD = 0 , END
A = CFG-OAD-MIN
IF ACT-OAT < ACT-RMT AND ACT-OAT < CFG-ECON-ENABLE-T THEN CYCLE2-ENABLE = 1 ELSE CYCLE2-ENABLE = 0
IF CYCLE2-ENABLE = 1 AND OCC-MODE <= 3 AND HVAC-MODE = 2 THEN A = SLIDE( DAT-LOOP , 0.0 , 100.0 , CFG-OAD-MIN , 100.0 )
IF OCC-MODE >= 4 THEN A = 0
A = MAX( A , OAD-DCV )
REM Discharge low limit closes the damper as the heating coil opens
C = SLIDE( DAT-LL-LOOP , 0 , 100 , 100 , 0 )
OAD = MIN( A , C )
"""

_PRG07_OAD_FLT = """\
REM --- OAD-CTRL ---
REM ASHRAE Cycle 1 (min OA) + Cycle 2 (free cooling)
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
IF FRZ-SD THEN DMP-POS-CMD = 0 , GOTO 160
IF ACT-OAT < ACT-RMT AND ACT-OAT < CFG-ECON-ENABLE-T THEN CYCLE2-ENABLE = 1 ELSE CYCLE2-ENABLE = 0
A = CFG-OAD-MIN
IF CYCLE2-ENABLE = 1 AND OCC-MODE <= 3 AND HVAC-MODE = 2 THEN A = SLIDE( DAT-LOOP , 0.0 , 100.0 , CFG-OAD-MIN , 100.0 )
IF OCC-MODE >= 4 THEN A = 0
A = MAX( A , OAD-DCV )
REM Discharge low limit closes the damper as the heating coil opens
C = SLIDE( DAT-LL-LOOP , 0 , 100 , 100 , 0 )
DMP-POS-CMD = MIN( A , C )
IF+ POWER-LOSS THEN START DMP-FLOAT-SYNC
IF+ OCC-MODE >= 4 THEN START DMP-FLOAT-SYNC
IF TIME-ON( DMP-FLOAT-SYNC ) > 0:00:05 THEN STOP DMP-FLOAT-SYNC
DMP-POS = FLOAT( DMP-OPEN , DMP-CLOSE , DMP-POS-CMD , CFG-DMP-DRV-TIME , CFG-DMP-POS-DB , DMP-FLOAT-SYNC )
"""

_PRG08_FAN_CV = """\
REM --- FAN-CTRL ---
IF FRZ-SD THEN FAN-CMD = 0 , STOP FAN-S/S , END
IF OCC-MODE <= 3 THEN FAN-CMD = 1
IF OCC-MODE >= 4 AND HVAC-MODE <> 1 THEN FAN-CMD = 1
IF OCC-MODE >= 4 AND HVAC-MODE = 1 THEN FAN-CMD = 0
FAN-S/S = FAN-CMD
"""

_PRG08_FAN_VFD = """\
REM --- FAN-CTRL ---
IF FRZ-SD THEN FAN-CMD = 0 , FAN-SPD = 0 , END
FAN-DMD = DAT-LOOP
IF HVAC-MODE = 1 THEN FAN-DMD = 0
FAN-SPD = SLIDE( FAN-DMD , 0.0 , 100.0 , CFG-FAN-MIN-SPD , 100.0 )
IF OCC-MODE >= 4 AND HVAC-MODE = 1 THEN FAN-SPD = 0
"""

_PRG09_FREEZESTAT = """\
REM --- FREEZESTAT ---
REM CFG-FRZ-STAT-NC On = normally closed contact, opens on trip
FREEZE-TRIP = 0
IF CFG-FRZ-STAT-NC AND NOT FREEZE-STAT THEN FREEZE-TRIP = 1
IF NOT CFG-FRZ-STAT-NC AND FREEZE-STAT THEN FREEZE-TRIP = 1
IF ACT-DAT < CFG-DAT-FREEZE THEN FREEZE-TRIP = 1
REM CFG-FRZ-TRIP-CNT trips inside CFG-FRZ-TRIP-WIN minutes latch the lockout
IF+ FREEZE-TRIP THEN FRZ-TRIP-CNT = FRZ-TRIP-CNT + 1
IF TIME-OFF( FREEZE-TRIP ) > CFG-FRZ-TRIP-WIN * 1.667 THEN FRZ-TRIP-CNT = 0
IF FRZ-TRIP-CNT >= CFG-FRZ-TRIP-CNT THEN FREEZE-LATCH = 1
REM Lockout clears only on manual reset with the discharge recovered
IF FREEZE-LATCH AND FREEZE-RST AND ACT-DAT > ( CFG-DAT-FREEZE + 5 ) THEN FREEZE-LATCH = 0 , FRZ-TRIP-CNT = 0 , STOP FREEZE-RST
FREEZE-ALARM = FREEZE-LATCH
FRZ-SD = FREEZE-TRIP OR FREEZE-LATCH
"""

_PRG12_MECH_CLG = """\
REM --- MECH-CLG-ENAB-PRG ---
REM Mechanical cooling waits for the economizer to run out of capacity
A = OAD > CFG-MECH-CLG-ENAB-POS
B = OAD < CFG-MECH-CLG-DISB-POS
IF TIME-ON( A ) > CFG-MECH-CLG-ENAB-TM * 1.667 THEN MECH-CLG-ENAB = 1
IF TIME-ON( B ) > CFG-MECH-CLG-DISB-TM * 1.667 THEN MECH-CLG-ENAB = 0
"""

_PRG12_MECH_CLG_FLT = """\
REM --- MECH-CLG-ENAB-PRG ---
REM Mechanical cooling waits for the economizer to run out of capacity
A = DMP-POS-CMD > CFG-MECH-CLG-ENAB-POS
B = DMP-POS-CMD < CFG-MECH-CLG-DISB-POS
IF TIME-ON( A ) > CFG-MECH-CLG-ENAB-TM * 1.667 THEN MECH-CLG-ENAB = 1
IF TIME-ON( B ) > CFG-MECH-CLG-DISB-TM * 1.667 THEN MECH-CLG-ENAB = 0
"""

_PRG_DCV = """\
REM --- DCV-CTRL ---
REM OAD-DCV is a demand only — the damper programs MAX it in, then clamp
REM it with the discharge low limit, so DCV cannot defeat that protection.
ACT-CO2 = CO2
OAD-DCV = 0
IF OCC-MODE <= 3 THEN OAD-DCV = SLIDE( ACT-CO2 , CFG-CO2-SP , CFG-CO2-MAX , 0 , 100.0 )
IF ACT-CO2 <= CFG-CO2-SP THEN OAD-DCV = 0
IF OCC-MODE >= 4 THEN OAD-DCV = 0
IF ACT-CO2 > CFG-CO2-ALARM THEN CO2-ALARM = 1 ELSE CO2-ALARM = 0
"""

_PRG_RAD_HTG = """\
REM --- RAD-HTG-PRG ---
REM Runs in parallel with the primary heating coil, independent of HVAC-MODE
IF ACT-OAT <= CFG-RAD-OA-MIN THEN RAD-HTG-ENAB = 1
IF ACT-OAT <= CFG-RAD-OA-MIN THEN RAD-HTG-VLV = CFG-RAD-VLV-MAX
IF ACT-OAT >= CFG-RAD-OA-MAX THEN RAD-HTG-ENAB = 0
IF ACT-OAT >= CFG-RAD-OA-MAX THEN RAD-HTG-VLV = CFG-RAD-VLV-MIN
IF ACT-OAT > CFG-RAD-OA-MIN AND ACT-OAT < CFG-RAD-OA-MAX THEN RAD-HTG-ENAB = 1
IF ACT-OAT > CFG-RAD-OA-MIN AND ACT-OAT < CFG-RAD-OA-MAX THEN ACT-RAD-HTG-POS = SLIDE( ACT-OAT, CFG-RAD-OA-MIN, CFG-RAD-OA-MAX, CFG-RAD-VLV-MAX, CFG-RAD-VLV-MIN )
IF ACT-OAT > CFG-RAD-OA-MIN AND ACT-OAT < CFG-RAD-OA-MAX THEN RAD-HTG-VLV = ACT-RAD-HTG-POS
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Core Module
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_core():
    """UV core — sensors, cascade loops, mode, freeze protection"""
    return Module(
        id="uv-core",
        name="UV Core",
        category="core",
        description="Base UV: DAT/OAT/RMT sensors, cascade loops, mode, freeze protection",
        is_core=True,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250", "Discharge Air Temperature", "°F"),
            InputPoint(2, "OAT", "AI", "10K -40 ->250", "Outdoor Air Temperature", "°F"),
            # RMT (room temp) now comes from the selected thermostat module:
            #   vav-stat-hardwired (AI3 wired) / vav-stat-hardwired-ud / stat-remote (network)
            InputPoint(4, "SF-STS", "BI", "Off/On", "Fan Status Feedback"),
        ],

        values=[
            ValuePoint(1, "ACT-RMT",           "AV", 72.0,  "Actual Room Temp",            "°F"),
            ValuePoint(2, "ACT-DAT",           "AV", 55.0,  "Actual DAT",                  "°F"),
            ValuePoint(3, "ACT-OAT",           "AV", 65.0,  "Actual OAT",                  "°F"),
            ValuePoint(14, "NET-OAT",          "AV", 65.0,  "Network OAT from parent (AV1)", "°F"),
            # Single operator zone setpoint + deadband (VAV single-setpoint pattern).
            # AV4/AV5 instances reused from the former CFG-OCC-CLG-SP/CFG-OCC-HTG-SP
            # pair so the UV point-location standard only needs those two entries
            # re-issued. Occupied actives = RMT-SP +/- CFG-RMT-SP-DB (see MODE-CTRL).
            ValuePoint(4, "RMT-SP",            "AV", 72.0,  "Operator Room Temp Setpoint", "°F"),
            ValuePoint(5, "CFG-RMT-SP-DB",     "AV", 1.0,   "Room Temp SP Deadband",       "°F"),
            # DB-MTPLR + ACT-RMT-SP-DB mirror VAV core (AV15/AV44) for exact parity:
            # ACT-RMT-SP-DB = DB-MTPLR * CFG-RMT-SP-DB, actives = RMT-SP +/- ACT-RMT-SP-DB.
            # New AV instances 12/13 (next free in uv-core) — add to point-location std.
            ValuePoint(12, "DB-MTPLR",         "AV", 1.5,   "Deadband Multiplier",         ""),
            ValuePoint(13, "ACT-RMT-SP-DB",    "AV", 1.5,   "Active Setpoint Deadband",    "°F"),
            # NSB/NSF setbacks — AV6/AV7 renamed in place from the old unoccupied
            # cooling/heating pair. Same instances, same defaults, same meaning:
            # the single setpoint the arbiter works against while unoccupied.
            ValuePoint(6, "NSF-SP",            "AV", 85.0,  "Night Setforward Setpoint",   "°F"),
            ValuePoint(7, "NSB-SP",            "AV", 60.0,  "Night Setback Setpoint",      "°F"),
            # THE zone setpoint the arbiter works against — one value, one
            # deadband, selected by occupancy mode in MODE-CTRL.
            # AV8 reused from the deleted ACT-CLG-SP.
            ValuePoint(8, "EFF-RMT-SP",        "AV", 72.0,  "Effective Room Setpoint",     "°F"),
            # AV9 free (was ACT-HTG-SP — deleted with the dual-setpoint scheme)
            # Display mirrors of the deadband edges. NOTHING in the control path
            # reads these — they exist so an operator can see the effective
            # heat/cool edges around EFF-RMT-SP.
            ValuePoint(10, "CLG-SP",           "AV", 73.5,  "Cooling Edge (display only)", "°F"),
            ValuePoint(11, "HTG-SP",           "AV", 70.5,  "Heating Edge (display only)", "°F"),
            # ONE discharge setpoint, reset by RESET-LOOP across the full range.
            # AV31/33/34 reused from the deleted cooling DAT trio.
            # AV32/35/36 free (was HTG-DAT-SP / CFG-HTG-DAT-MIN / CFG-HTG-DAT-MAX)
            ValuePoint(31, "DAT-SP",           "AV", 55.0,  "Discharge Air Setpoint",      "°F"),
            ValuePoint(33, "CFG-DAT-MIN-SP",   "AV", 55.0,  "Min DAT Setpoint (full cooling)", "°F"),
            ValuePoint(34, "CFG-DAT-MAX-SP",   "AV", 105.0, "Max DAT Setpoint (full heating)", "°F"),
            # Night setback / setforward are bang-bang, not modulated.
            ValuePoint(35, "CFG-NSB-HTG-POS",  "AV", 100.0, "Heating Coil Position During NSB", "%"),
            ValuePoint(36, "CFG-NSF-CLG-POS",  "AV", 100.0, "Cooling Coil Position During NSF", "%"),
            # Owned by core, not uv-dcv, so the damper programs can read it
            # whether or not the CO2 module is selected. Stays 0 without DCV.
            ValuePoint(74, "OAD-DCV",          "AV", 0.0,   "DCV Damper Demand",               "%"),
            # Safety/config
            ValuePoint(37, "CFG-DAT-LL",  "AV", 45.0,  "DAT Low Limit (safety)",      "°F"),
            ValuePoint(38, "CFG-DAT-HL",  "AV", 110.0, "DAT High Limit (safety)",     "°F"),
            ValuePoint(39, "CFG-DAT-FREEZE",   "AV", 38.0,  "DAT Freeze Protection",       "°F"),
            # Cabinet protection reset (Part 2)
            ValuePoint(41, "CFG-CAB-OAT-HI",   "AV", 35.0,  "Cabinet Protection: OAT High (no trickle)", "°F"),
            ValuePoint(44, "CFG-CAB-OAT-LO",   "AV", 0.0,   "Cabinet Protection: OAT Low (max trickle)",  "°F"),
            ValuePoint(40, "CFG-CAB-VLV-MIN",  "AV", 20.0,  "Cabinet Protection: Valve % at OAT-HI",     "%"),
            ValuePoint(46, "CFG-CAB-VLV-MAX",  "AV", 60.0,  "Cabinet Protection: Valve % at OAT-LO",     "%"),
            ValuePoint(52, "CAB-PROT-VLV",     "AV", 0.0,   "Cabinet Protection: Computed Valve Output",  "%"),
            ValuePoint(42, "CFG-STG1-T",       "AV", 50.0,  "Stage 1 Threshold",           "%"),
            ValuePoint(43, "CFG-STG2-T",       "AV", 80.0,  "Stage 2 Threshold",           "%"),
            # Network/status
            ValuePoint(12, "NET-OCC-CMD",      "BV", True,  "Network Occupied Command"),
            # BV13 reused from the old binary OCC-MODE, which is now MV19.
            ValuePoint(13, "INIT-MODE",        "BV", False, "Initialize Window Active"),
            ValuePoint(14, "HWS-OK",           "BV", True,  "Hot Water Available"),
            ValuePoint(16, "FAN-CMD",          "BV", False, "Fan Command"),
            ValuePoint(17, "CFG-OAT-LOCAL",    "BV", False, "Use Local OAT Sensor (default FALSE = network)"),
            ValuePoint(18, "NET-OAT-OK",       "BV", True,  "Network OAT Comms OK (plausible-range)"),
            # Stub defaults for optional modules — the owning module drives them
            # when selected, and the safe default applies when it is not.
            # FRZ-SD is written by uv-freezestat; without that module it stays
            # Off and every freeze guard is inert.
            ValuePoint(19, "FRZ-SD",           "BV", False, "Freeze Shutdown Active"),
            # MECH-CLG-ENAB is written by the OA damper modules. Face/bypass
            # units have no economizer, so it defaults On and cooling is free
            # to run.
            ValuePoint(31, "MECH-CLG-ENAB",    "BV", True,  "Mechanical Cooling Enabled"),

            # ── Multi-state values ──
            # MV19/MV20 match the A201 convention and the VAV core enums.
            ValuePoint(19, "OCC-MODE",  "MV", 4, "Occupancy Mode",
                       states={1: "Occupied", 2: "Bypass", 3: "Standby",
                               4: "Unoccupied", 5: "NSB", 6: "NSF"}),
            # Reheat (3) is never set on a UV — the enum stays aligned with VAV
            # so mode numbers mean the same thing on every SBS controller.
            ValuePoint(20, "HVAC-MODE", "MV", 1, "HVAC Mode",
                       states={1: "Ventilation", 2: "Cool", 3: "Reheat",
                               4: "Heat", 5: "Initialize"}),
        ],

        loops=[
            # Three loops, none self-referential. LOOP2's stored action is a
            # starting value only — MODE-CTRL overwrites DAT-LOOP:2 every scan.
            LoopDef(1, "RESET-LOOP", "ACT-RMT", "EFF-RMT-SP", "DAT-SP-LOOP1",
                    p_band=18.0, integral=20.0, action="reverse",
                    description="Zone resets DAT-SP (deadband 2.0)"),
            LoopDef(2, "DAT-LOOP", "ACT-DAT", "DAT-SP", "DAT-PID",
                    p_band=20.0, integral=40.0, action="reverse",
                    description="Single DAT loop, action flips by mode (deadband 0.5, bias 50.0)"),
            LoopDef(3, "DAT-LL-LOOP", "ACT-DAT", "CFG-DAT-LL", "LL-PID",
                    p_band=4.0, integral=20.0, action="reverse",
                    description="Discharge low limit floors the heating output"),
        ],

        programs=[
            ProgramDef(1, "MODE-CTRL", "PRG01-MODE-CTRL.bas", _PRG01_MODE, True,
                       "Occupancy mode and setpoint selection", exec_order=1),
            ProgramDef(2, "DAT-RESET", "PRG02-DAT-RESET.bas", _PRG02_DAT_RESET, True,
                       "Space temp loops reset DAT setpoints", exec_order=2),
            ProgramDef(11, "CAB-PROT-RESET", "PRG02B-CAB-PROT-RESET.bas", _PRG02B_CAB_PROT, True,
                       "Cabinet protection OAT-based reset", exec_order=2),
        ],

        schedules=[
            ScheduleDef(1, "LOCAL-SCHEDULE", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10, "Local occupancy schedule"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM", "UV system overview"),
            SystemGroupDef("{device-name}-SET-POINTS", "Setpoints and configuration"),
        ],

        soo_paragraph="""The unit ventilator shall be equipped with a direct digital controller
providing cascaded PID control from a single effective zone setpoint with an
adjustable deadband. A latching mode arbiter shall determine the unit mode —
Ventilation, Cool, Heat or Initialize — and only one mode shall be active at a
time. The zone reset loop shall reset a single discharge air temperature
setpoint across its full range, and one discharge air loop, whose action
reverses with the mode, shall drive the coil selected by that mode. The idle
coil shall be driven closed. A discharge low limit loop shall hold the heating
output above the minimum discharge temperature in any mode. Freeze protection
activates when unoccupied and outdoor temperature drops below the freeze enable
setpoint.""",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Fan Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_fan_cv():
    return Module(
        id="uv-fan-cv", name="UV Fan CV", category="fan",
        description="Constant volume fan on/off",
        outputs=[OutputPoint(1, "FAN-S/S", "BO", "Stop/Start", "Fan Start/Stop")],
        programs=[ProgramDef(8, "FAN-CTRL", "PRG08-FAN-CTRL.bas", _PRG08_FAN_CV, True,
                             "Fan CV on/off", exec_order=8)],
        requires=["uv-core"],
        conflicts=["uv-fan-vfd"],
        mutually_exclusive_group="uv-fan",
    )


def build_uv_fan_vfd():
    return Module(
        id="uv-fan-vfd", name="UV Fan VFD", category="fan",
        description="VFD fan speed from max loop demand",
        outputs=[OutputPoint(1, "FAN-SPD", "AO", "0.0 ->100%", "Fan Speed", 0.0, 10.0)],
        values=[
            ValuePoint(9, "CFG-FAN-MIN-SPD", "AV", 30.0, "Fan Min Speed", "%"),
            ValuePoint(49, "FAN-DMD",         "AV", 0.0,  "Fan Demand",    "%"),
        ],
        programs=[ProgramDef(8, "FAN-CTRL", "PRG08-FAN-CTRL.bas", _PRG08_FAN_VFD, True,
                             "Fan VFD from max demand", exec_order=8)],
        requires=["uv-core"],
        conflicts=["uv-fan-cv"],
        mutually_exclusive_group="uv-fan",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  OA Damper Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_oad_mod():
    return Module(
        id="uv-oad-mod", name="UV OA Damper Modulating", category="economizer",
        description="OA damper AO — ASHRAE Cycle 1+2",
        outputs=[OutputPoint(10, "OAD", "AO", "0.0 ->100%", "OA Damper", 2.0, 10.0)],
        values=[
            ValuePoint(80, "CFG-OAD-MIN",       "AV", 10.0, "Min OA Damper Position",  "%"),
            ValuePoint(81, "CFG-ECON-ENABLE-T",  "AV", 65.0, "Economizer Enable Temp",  "°F"),
            ValuePoint(82, "CYCLE2-ENABLE",      "BV", False, "Cycle 2 Free Cooling"),
            ValuePoint(105, "CFG-MECH-CLG-ENAB-POS", "AV", 99.0, "Damper Pos To Enable Mech Cooling",  "%"),
            ValuePoint(106, "CFG-MECH-CLG-DISB-POS", "AV", 90.0, "Damper Pos To Disable Mech Cooling", "%"),
            ValuePoint(107, "CFG-MECH-CLG-ENAB-TM",  "AV", 10.0, "Time Above Enable Pos",              "Min"),
            ValuePoint(108, "CFG-MECH-CLG-DISB-TM",  "AV", 10.0, "Time Below Disable Pos",             "Min"),
        ],
        programs=[
            ProgramDef(7, "OAD-CTRL", "PRG07-OAD-CTRL.bas", _PRG07_OAD, True,
                       "OA damper ASHRAE Cycle 1+2", exec_order=7),
            ProgramDef(12, "MECH-CLG-ENAB-PRG", "PRG12-MECH-CLG-ENAB-PRG.bas", _PRG12_MECH_CLG, True,
                       "Mechanical cooling enable, latched on damper position", exec_order=4),
        ],
        requires=["uv-core"],
        conflicts=["uv-oad-flt"],
        mutually_exclusive_group="uv-oad",
    )


def build_uv_oad_flt():
    return Module(
        id="uv-oad-flt", name="UV OA Damper Floating", category="economizer",
        description="OA damper floating — CBAS FLOAT() ASHRAE Cycle 1+2",
        outputs=[
            OutputPoint(10, "DMP-OPEN",  "BO", "Stop/Start", "OA Damper Open"),
            OutputPoint(11, "DMP-CLOSE", "BO", "Stop/Start", "OA Damper Close"),
        ],
        values=[
            ValuePoint(80, "CFG-OAD-MIN",       "AV", 10.0,  "Min OA Damper Position",        "%"),
            ValuePoint(81, "CFG-ECON-ENABLE-T", "AV", 65.0,  "Economizer Enable Temp",        "°F"),
            ValuePoint(82, "CYCLE2-ENABLE",     "BV", False, "Cycle 2 Free Cooling"),
            ValuePoint(83, "DMP-POS",           "AV", 0.0,   "OA Damper Actual Position",    "%"),
            ValuePoint(84, "DMP-POS-CMD",       "AV", 0.0,   "OA Damper Commanded Position", "%"),
            ValuePoint(96, "CFG-DMP-POS-DB",    "AV", 2.0,   "Damper Float Position Deadband","%"),
            ValuePoint(97, "CFG-DMP-DRV-TIME",  "AV", 150.0, "Damper Full Stroke Time",      "Sec"),
            ValuePoint(98, "DMP-FLOAT-SYNC",    "BV", False, "Damper Float Sync Trigger"),
            ValuePoint(105, "CFG-MECH-CLG-ENAB-POS", "AV", 99.0, "Damper Pos To Enable Mech Cooling",  "%"),
            ValuePoint(106, "CFG-MECH-CLG-DISB-POS", "AV", 90.0, "Damper Pos To Disable Mech Cooling", "%"),
            ValuePoint(107, "CFG-MECH-CLG-ENAB-TM",  "AV", 10.0, "Time Above Enable Pos",              "Min"),
            ValuePoint(108, "CFG-MECH-CLG-DISB-TM",  "AV", 10.0, "Time Below Disable Pos",             "Min"),
        ],
        programs=[
            ProgramDef(7, "OAD-CTRL", "PRG07-OAD-CTRL.bas", _PRG07_OAD_FLT, True,
                       "OA damper floating Cycle 1+2", exec_order=7),
            ProgramDef(12, "MECH-CLG-ENAB-PRG", "PRG12-MECH-CLG-ENAB-PRG.bas", _PRG12_MECH_CLG_FLT, True,
                       "Mechanical cooling enable, latched on damper position", exec_order=4),
        ],
        requires=["uv-core"],
        conflicts=["uv-oad-mod"],
        mutually_exclusive_group="uv-oad",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Face/Bypass Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_fbp_mod():
    return Module(
        id="uv-fbp-mod", name="UV Face/Bypass Modulating", category="economizer",
        description="Face/bypass modulating AO — cold/mild mode switching",
        outputs=[OutputPoint(12, "FBP", "AO", "0.0 ->100%", "Face/Bypass Damper", 2.0, 10.0)],
        values=[
            ValuePoint(85, "CFG-FBP-SWITCHOVER-T", "AV", 40.0, "FBP Switchover Temp", "°F"),
            ValuePoint(86, "FBP-MODE",             "BV", False, "FBP Cold Mode"),
            ValuePoint(87, "HW-DEMAND",            "AV", 0.0,   "HW Demand from FBP",  "%"),
        ],
        programs=[ProgramDef(4, "FBP-CTRL", "PRG04-FBP-CTRL.bas", _PRG04_FBP, True,
                             "Face/bypass cold/mild mode", exec_order=4)],
        requires=["uv-core"],
        conflicts=["uv-fbp-flt"],
        mutually_exclusive_group="uv-fbp",
    )


def build_uv_fbp_flt():
    return Module(
        id="uv-fbp-flt", name="UV Face/Bypass Floating", category="economizer",
        description="Face/bypass floating damper — CBAS FLOAT() cold/mild mode switching",
        outputs=[
            OutputPoint(12, "FBP-OPEN",  "BO", "Stop/Start", "Face/Bypass Open"),
            OutputPoint(13, "FBP-CLOSE", "BO", "Stop/Start", "Face/Bypass Close"),
        ],
        values=[
            ValuePoint(85, "CFG-FBP-SWITCHOVER-T", "AV", 40.0,  "FBP Switchover Temp",          "°F"),
            ValuePoint(86, "FBP-MODE",             "BV", False, "FBP Cold Mode"),
            ValuePoint(87, "HW-DEMAND",            "AV", 0.0,   "HW Demand from FBP",          "%"),
            ValuePoint(88, "FBP-POS",              "AV", 0.0,   "FBP Actual Position",         "%"),
            ValuePoint(89, "FBP-POS-CMD",          "AV", 0.0,   "FBP Commanded Position",      "%"),
            ValuePoint(102, "CFG-FBP-POS-DB",      "AV", 2.0,   "FBP Float Position Deadband", "%"),
            ValuePoint(103, "CFG-FBP-DRV-TIME",    "AV", 150.0, "FBP Full Stroke Time",        "Sec"),
            ValuePoint(104, "FBP-FLOAT-SYNC",      "BV", False, "FBP Float Sync Trigger"),
        ],
        programs=[ProgramDef(4, "FBP-CTRL", "PRG04-FBP-CTRL.bas", _PRG04_FBP_FLT, True,
                             "Face/bypass floating: FLOAT() with cold/mild logic", exec_order=4)],
        requires=["uv-core"],
        conflicts=["uv-fbp-mod"],
        mutually_exclusive_group="uv-fbp",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Heating Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_hw_mod():
    return Module(
        id="uv-hw-mod", name="UV HW Modulating", category="heating",
        description="HW modulating valve — guarded DAT-LOOP, heating modes only",
        outputs=[OutputPoint(6, "HW-VLV", "AO", "0.0 ->100%", "HW Valve (reverse)", 10.0, 2.0, True)],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HW_MOD, True,
                             "HW mod = guarded DAT-LOOP", exec_order=5)],
        requires=["uv-core"],
        conflicts=["uv-hw-flt", "uv-steam-mod", "uv-steam-onoff"],
        mutually_exclusive_group="uv-heating",
    )


def build_uv_hw_flt():
    return Module(
        id="uv-hw-flt", name="UV HW Floating", category="heating",
        description="HW floating valve — CBAS FLOAT() function drives open/close relays",
        outputs=[
            OutputPoint(6, "RH-OPEN",  "BO", "Stop/Start", "HW Valve Open"),
            OutputPoint(7, "RH-CLOSE", "BO", "Stop/Start", "HW Valve Close"),
        ],
        values=[
            ValuePoint(32, "RH-POS",          "AV", 0.0,   "HW Valve Actual Position",    "%"),
            ValuePoint(47, "RH-POS-CMD",      "AV", 0.0,   "HW Valve Commanded Position", "%"),
            ValuePoint(93, "CFG-RH-POS-DB",   "AV", 2.0,   "HW Float Position Deadband",  "%"),
            ValuePoint(94, "CFG-RH-DRV-TIME", "AV", 150.0, "HW Valve Full Stroke Time",   "Sec"),
            ValuePoint(95, "RH-FLOAT-SYNC",   "BV", False, "HW Float Sync Trigger"),
        ],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HW_FLT, True,
                             "HW float = guarded DAT-LOOP vs position", exec_order=5)],
        requires=["uv-core"],
        conflicts=["uv-hw-mod", "uv-steam-mod", "uv-steam-onoff"],
        mutually_exclusive_group="uv-heating",
    )


def build_uv_hw_mod_fbp():
    """HW modulating for face/bypass families (valve controlled by FBP-CTRL)"""
    return Module(
        id="uv-hw-mod-fbp", name="UV HW Mod (FBP)", category="heating",
        description="HW modulating valve — driven by FBP HW-DEMAND",
        outputs=[OutputPoint(6, "HW-VLV", "AO", "0.0 ->100%", "HW Valve (reverse)", 10.0, 2.0, True)],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HW_MOD_FBP, True,
                             "HW valve = HW-DEMAND from FBP", exec_order=5)],
        requires=["uv-core"],
        conflicts=["uv-hw-mod", "uv-hw-flt", "uv-steam-mod", "uv-steam-onoff"],
        mutually_exclusive_group="uv-heating",
    )


def build_uv_steam_mod():
    return Module(
        id="uv-steam-mod", name="UV Steam Modulating", category="heating",
        description="Steam modulating valve — guarded DAT-LOOP, heating modes only",
        outputs=[OutputPoint(6, "STM-VLV", "AO", "0.0 ->100%", "Steam Valve", 2.0, 10.0)],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_STEAM_MOD, True,
                             "Steam mod = guarded DAT-LOOP", exec_order=5)],
        requires=["uv-core"],
        conflicts=["uv-hw-mod", "uv-hw-flt", "uv-hw-mod-fbp", "uv-steam-onoff"],
        mutually_exclusive_group="uv-heating",
    )


def build_uv_steam_onoff():
    return Module(
        id="uv-steam-onoff", name="UV Steam On/Off", category="heating",
        description="Steam on/off valve — cycles on guarded DAT-LOOP threshold",
        outputs=[OutputPoint(6, "STM-VLV", "BO", "Stop/Start", "Steam Valve")],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_STEAM_ONOFF, True,
                             "Steam on/off from loop threshold", exec_order=5)],
        requires=["uv-core"],
        conflicts=["uv-hw-mod", "uv-hw-flt", "uv-hw-mod-fbp", "uv-steam-mod"],
        mutually_exclusive_group="uv-heating",
    )


def build_uv_steam_onoff_fbp():
    """Steam on/off for face/bypass.

    Drives only the steam valve, at HTG-OUTPUT (program instance 5) — the same
    slot every other heating module uses. The face/bypass damper and FBP-MODE
    are owned by the selected face/bypass module's FBP-CTRL (instance 4), so
    this no longer collides with it. Mirrors uv-hw-mod-fbp.
    """
    return Module(
        id="uv-steam-onoff-fbp", name="UV Steam On/Off (FBP)", category="heating",
        description="Steam on/off — coupled to face/bypass cold/mild mode (FBP-MODE)",
        outputs=[OutputPoint(6, "STM-VLV", "BO", "Stop/Start", "Steam Valve")],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_STEAM_ONOFF_FBP, True,
                             "Steam on/off coupled to FBP mode", exec_order=5)],
        requires=["uv-core"],
        conflicts=["uv-hw-mod", "uv-hw-flt", "uv-hw-mod-fbp", "uv-steam-mod", "uv-steam-onoff"],
        mutually_exclusive_group="uv-heating",
    )


def build_uv_radiant_heat():
    """Radiant heat with reverse-acting OAT reset.

    Independent add-on — NO mutual-exclusion group, so it can be selected
    alongside any primary heating option (HW, steam, etc.). Runs in parallel
    on its own valve output.
    """
    return Module(
        id="uv-radiant-heat", name="Radiant Heat (OAT Reset)", category="heating",
        description="Radiant heating valve with reverse-acting OAT reset — runs in parallel with any primary heating",
        outputs=[OutputPoint(8, "RAD-HTG-VLV", "AO", "0.0 ->100%", "Radiant Heat Valve", 2.0, 10.0)],
        values=[
            ValuePoint(60, "CFG-RAD-OA-MIN",  "AV", 0.0,   "OAT at full open",              "°F"),
            ValuePoint(61, "CFG-RAD-OA-MAX",  "AV", 55.0,  "OAT at full closed",            "°F"),
            ValuePoint(62, "CFG-RAD-VLV-MIN", "AV", 0.0,   "Valve minimum position",        "%"),
            ValuePoint(63, "CFG-RAD-VLV-MAX", "AV", 100.0, "Valve maximum position",        "%"),
            ValuePoint(64, "ACT-RAD-HTG-POS", "AV", 0.0,   "Actual radiant valve position", "%"),
            ValuePoint(60, "RAD-HTG-ENAB",    "BV", False, "Radiant Heat Enabled"),
        ],
        programs=[ProgramDef(13, "RAD-HTG-PRG", "PRG13-RAD-HTG.bas", _PRG_RAD_HTG, True,
                             "Radiant heat reverse-acting OAT reset", exec_order=13)],
        requires=["uv-core"],
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Cooling Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_chw_mod():
    return Module(
        id="uv-chw-mod", name="UV CHW Modulating", category="cooling",
        description="CHW modulating valve — guarded DAT-LOOP, Cool mode only",
        outputs=[OutputPoint(4, "CHW-VLV", "AO", "0.0 ->100%", "CHW Valve", 2.0, 10.0)],
        programs=[ProgramDef(6, "CLG-OUTPUT", "PRG06-CLG-OUTPUT.bas", _PRG06_CHW_MOD, True,
                             "CHW mod = guarded DAT-LOOP", exec_order=6)],
        requires=["uv-core"],
        conflicts=["uv-chw-flt", "uv-dx-1", "uv-dx-2"],
        mutually_exclusive_group="uv-cooling",
    )


def build_uv_chw_flt():
    return Module(
        id="uv-chw-flt", name="UV CHW Floating", category="cooling",
        description="CHW floating valve — CBAS FLOAT() function drives open/close relays",
        outputs=[
            OutputPoint(4, "CHW-OPEN",  "BO", "Stop/Start", "CHW Valve Open"),
            OutputPoint(5, "CHW-CLOSE", "BO", "Stop/Start", "CHW Valve Close"),
        ],
        values=[
            ValuePoint(45, "CHW-POS",          "AV", 0.0,   "CHW Valve Actual Position",    "%"),
            ValuePoint(48, "CHW-POS-CMD",      "AV", 0.0,   "CHW Valve Commanded Position", "%"),
            ValuePoint(90, "CFG-CHW-POS-DB",   "AV", 2.0,   "CHW Float Position Deadband",  "%"),
            ValuePoint(91, "CFG-CHW-DRV-TIME", "AV", 150.0, "CHW Valve Full Stroke Time",   "Sec"),
            ValuePoint(92, "CHW-FLOAT-SYNC",   "BV", False, "CHW Float Sync Trigger"),
        ],
        programs=[ProgramDef(6, "CLG-OUTPUT", "PRG06-CLG-OUTPUT.bas", _PRG06_CHW_FLT, True,
                             "CHW float = guarded DAT-LOOP vs position", exec_order=6)],
        requires=["uv-core"],
        conflicts=["uv-chw-mod", "uv-dx-1", "uv-dx-2"],
        mutually_exclusive_group="uv-cooling",
    )


def build_uv_dx_1():
    return Module(
        id="uv-dx-1", name="UV DX 1-Stage", category="cooling",
        description="DX single stage — guarded DAT-LOOP > threshold, 3min timer",
        outputs=[OutputPoint(4, "DX-STG1", "BO", "Stop/Start", "DX Stage 1")],
        values=[ValuePoint(50, "DX1-OFF-TMR", "AV", 999.0, "DX1 Off Timer", "Sec")],
        programs=[ProgramDef(6, "CLG-OUTPUT", "PRG06-CLG-OUTPUT.bas", _PRG06_DX_1, True,
                             "DX stg1 from guarded DAT-LOOP", exec_order=6)],
        requires=["uv-core"],
        conflicts=["uv-chw-mod", "uv-chw-flt", "uv-dx-2"],
        mutually_exclusive_group="uv-cooling",
    )


def build_uv_dx_2():
    return Module(
        id="uv-dx-2", name="UV DX 2-Stage", category="cooling",
        description="DX 2-stage — stg1 3min, stg2 5min delay",
        outputs=[
            OutputPoint(4, "DX-STG1", "BO", "Stop/Start", "DX Stage 1"),
            OutputPoint(5, "DX-STG2", "BO", "Stop/Start", "DX Stage 2"),
        ],
        values=[
            ValuePoint(50, "DX1-OFF-TMR", "AV", 999.0, "DX1 Off Timer", "Sec"),
            ValuePoint(51, "DX2-OFF-TMR", "AV", 999.0, "DX2 Off Timer", "Sec"),
        ],
        programs=[ProgramDef(6, "CLG-OUTPUT", "PRG06-CLG-OUTPUT.bas", _PRG06_DX_2, True,
                             "DX 2-stage from guarded DAT-LOOP", exec_order=6)],
        requires=["uv-core"],
        conflicts=["uv-chw-mod", "uv-chw-flt", "uv-dx-1"],
        mutually_exclusive_group="uv-cooling",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  DCV Module (optional)
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_dcv():
    return Module(
        id="uv-dcv", name="UV DCV (CO2)", category="safety",
        description="Demand Controlled Ventilation — CO2 overrides OA damper minimum",
        inputs=[InputPoint(5, "CO2", "AI", "0 ->100% (0-5V)", "CO2 Sensor", "ppm")],
        values=[
            ValuePoint(70, "ACT-CO2",        "AV", 400.0,  "Actual CO2 Level",       "ppm"),
            ValuePoint(71, "CFG-CO2-SP",     "AV", 1000.0, "CO2 Setpoint",           "ppm"),
            ValuePoint(72, "CFG-CO2-MAX",    "AV", 1200.0, "CO2 Max (full OA)",      "ppm"),
            ValuePoint(73, "CFG-CO2-ALARM",  "AV", 1200.0, "CO2 Alarm Level",        "ppm"),
            ValuePoint(75, "CO2-ALARM",      "BV", False,   "CO2 High Alarm"),
        ],
        programs=[ProgramDef(9, "DCV-CTRL", "PRG09-DCV-CTRL.bas", _PRG_DCV, True,
                             "DCV CO2 override of OA damper", exec_order=9)],
        requires=["uv-core"],
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Freezestat Module (optional)
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_freezestat():
    return Module(
        id="uv-freezestat", name="UV Freezestat", category="safety",
        description="Freezestat BI + DAT low limit, latching shutdown",
        inputs=[InputPoint(6, "FREEZE-STAT", "BI", "Normal/Alarm", "Freezestat Contact")],
        values=[
            ValuePoint(76, "FREEZE-TRIP",  "BV", False, "Freeze Trip"),
            ValuePoint(77, "FREEZE-LATCH", "BV", False, "Freeze Latch"),
            ValuePoint(78, "FREEZE-RST",   "BV", False, "Freeze Reset"),
            ValuePoint(79, "FREEZE-ALARM", "BV", False, "Freeze Alarm"),
            # Contact polarity varies by unit. On = normally closed (SBS
            # standard): the contact opens on trip, so the input reads 0.
            ValuePoint(80, "CFG-FRZ-STAT-NC", "BV", True, "Freezestat Contact Normally Closed"),
            # Two-stage trip: the contact stops the fan every time it opens,
            # and CFG-FRZ-TRIP-CNT trips inside the window latch the lockout.
            ValuePoint(53, "CFG-FRZ-TRIP-CNT", "AV", 3.0,  "Trips Before Lockout",       ""),
            ValuePoint(54, "CFG-FRZ-TRIP-WIN", "AV", 30.0, "Trip Count Window",          "Min"),
            ValuePoint(55, "FRZ-TRIP-CNT",     "AV", 0.0,  "Trips In Current Window",    ""),
        ],
        # exec_order 0 — a safety runs before everything that consumes it.
        programs=[ProgramDef(10, "FREEZESTAT", "PRG10-FREEZESTAT.bas", _PRG09_FREEZESTAT, True,
                             "Freezestat trip, count-to-lockout, manual reset", exec_order=0)],
        requires=["uv-core"],
    )
