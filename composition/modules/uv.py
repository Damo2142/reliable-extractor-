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

Control Architecture — Cascaded PID:
  PRG01 MODE-CTRL: occupancy, setpoint selection
  PRG02 DAT-RESET: space temp loops reset DAT setpoints
  PRG03 FREEZE-PROTECT: unoccupied freeze logic
  PRG04 FBP-CTRL: face/bypass cold/mild mode (FBP families)
  PRG05 HTG-OUTPUT: heating valve from HTG-DAT-LOOP
  PRG06 CLG-OUTPUT: cooling valve/stage from CLG-DAT-LOOP
  PRG07 OAD-CTRL: OA damper ASHRAE Cycle 1+2 (OAD families)
  PRG08 FAN-CTRL: fan on/off or VFD speed
  PRG09 FREEZESTAT: hardware freezestat + DAT latch (optional)

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
REM Occupancy mode and setpoint selection
REM {parent} = parent device for network variables
REM
IF NET-OCC-CMD = 1 THEN OCC-MODE = 1 ELSE OCC-MODE = 0
IF OCC-MODE = 0 THEN CLG-SP = CFG-UNOCC-CLG-SP ELSE CLG-SP = CFG-OCC-CLG-SP
IF OCC-MODE = 0 THEN HTG-SP = CFG-UNOCC-HTG-SP ELSE HTG-SP = CFG-OCC-HTG-SP
ACT-CLG-SP = CLG-SP
ACT-HTG-SP = HTG-SP
REM ACT-RMT is set by the selected thermostat module (wired or network)
ACT-DAT = AI1
ACT-OAT = AI2
NET-OCC-CMD = {parent}BV21
HWS-OK = {parent}BV22
"""

_PRG02_DAT_RESET = """\
REM --- DAT-RESET ---
REM Space temp loops reset DAT setpoints via SLIDE
REM CLG-RESET-LOOP: ACT-RMT vs ACT-CLG-SP direct acting
REM HTG-RESET-LOOP: ACT-RMT vs ACT-HTG-SP reverse acting
REM
HTG-DAT-SP = SLIDE( HTG-RESET-LOOP, 0.0, 100.0, CFG-HTG-DAT-MIN, CFG-HTG-DAT-MAX )
CLG-DAT-SP = SLIDE( CLG-RESET-LOOP, 0.0, 100.0, CFG-CLG-DAT-MIN, CFG-CLG-DAT-MAX )
"""

_PRG03_FREEZE = """\
REM --- FREEZE-PROTECT ---
REM Unoccupied freeze protection based on OAT
REM
FREEZE-PROT = 0
IF OCC-MODE = 0 AND ACT-OAT < CFG-UV-FREEZE-OAT THEN FREEZE-PROT = 1
IF FREEZE-PROT = 1 THEN OAD = 0
"""

_PRG04_FBP = """\
REM --- FBP-CTRL ---
REM Face/bypass cold/mild mode control
REM Cold mode (OAT < switchover): valve full open, FBP modulates DAT
REM Mild mode (OAT >= switchover): full face, valve modulates DAT
REM
IF ACT-OAT < CFG-FBP-SWITCHOVER-T THEN FBP-MODE = 1 ELSE FBP-MODE = 0
IF FBP-MODE = 1 THEN HW-DEMAND = 100
IF FBP-MODE = 1 THEN FBP = HTG-DAT-LOOP
IF FBP-MODE = 0 THEN FBP = 100
IF FBP-MODE = 0 THEN HW-DEMAND = HTG-DAT-LOOP
IF FREEZE-PROT = 1 THEN FBP = 100
IF FREEZE-PROT = 1 THEN HW-DEMAND = CFG-UV-FREEZE-VLV
"""

_PRG04_FBP_FLT = """\
REM --- FBP-CTRL ---
REM Face/bypass floating damper using CBAS FLOAT() function
REM Cold mode (OAT < switchover): valve full open, FBP modulates DAT
REM Mild mode (OAT >= switchover): full face position, valve modulates DAT
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
REM
IF ACT-OAT < CFG-FBP-SWITCHOVER-T THEN FBP-MODE = 1 ELSE FBP-MODE = 0
REM
REM Position command and HW demand based on mode
IF FBP-MODE = 1 THEN FBP-POS-CMD = HTG-DAT-LOOP
IF FBP-MODE = 1 THEN HW-DEMAND = 100
IF FBP-MODE = 0 THEN FBP-POS-CMD = 100
IF FBP-MODE = 0 THEN HW-DEMAND = HTG-DAT-LOOP
REM
REM Freeze: drive damper to full face
IF FREEZE-PROT = 1 THEN FBP-POS-CMD = 100
IF FREEZE-PROT = 1 THEN HW-DEMAND = CFG-UV-FREEZE-VLV
REM
REM Floating sync on power cycle and mode change
IF+ POWER-LOSS THEN START FBP-FLOAT-SYNC
IF+ FBP-MODE = 1 THEN START FBP-FLOAT-SYNC
IF+ FBP-MODE = 0 THEN START FBP-FLOAT-SYNC
IF TIME-ON( FBP-FLOAT-SYNC ) > 0:00:05 THEN STOP FBP-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays
FBP-POS = FLOAT( FBP-OPEN , FBP-CLOSE , FBP-POS-CMD , CFG-FBP-DRV-TIME , CFG-FBP-POS-DB , FBP-FLOAT-SYNC )
"""

_PRG04_FBP_STEAM_ONOFF = """\
REM --- FBP-CTRL ---
REM Face/bypass with steam on/off valve
REM Cold mode: steam on, FBP modulates
REM Mild mode: full face, steam cycles on demand
REM
IF ACT-OAT < CFG-FBP-SWITCHOVER-T THEN FBP-MODE = 1 ELSE FBP-MODE = 0
IF FBP-MODE = 1 AND HTG-DAT-LOOP > 0 THEN STM-VLV = 1
IF FBP-MODE = 1 THEN FBP = HTG-DAT-LOOP
IF FBP-MODE = 0 THEN FBP = 100
IF FBP-MODE = 0 AND HTG-DAT-LOOP > 50 THEN STM-VLV = 1
IF FBP-MODE = 0 AND HTG-DAT-LOOP < 40 THEN STM-VLV = 0
IF HTG-DAT-LOOP = 0 THEN STM-VLV = 0
IF FREEZE-PROT = 1 THEN FBP = 100
IF FREEZE-PROT = 1 THEN STM-VLV = 1
"""

_PRG05_HW_MOD = """\
REM --- HTG-OUTPUT ---
REM HW modulating valve from HTG-DAT-LOOP
REM
IF FREEZE-PROT = 0 THEN HW-VLV = HTG-DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN HW-VLV = 0
IF FREEZE-PROT = 1 THEN HW-VLV = CFG-UV-FREEZE-VLV
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
REM
REM Freeze: drive valve to configured freeze position
IF FREEZE-PROT = 1 THEN RH-POS-CMD = CFG-UV-FREEZE-VLV
REM
REM Floating sync on power cycle and unoccupied
IF+ POWER-LOSS THEN START RH-FLOAT-SYNC
IF+ OCC-MODE = 0 THEN START RH-FLOAT-SYNC
IF TIME-ON( RH-FLOAT-SYNC ) > 0:00:05 THEN STOP RH-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays
RH-POS = FLOAT( RH-OPEN , RH-CLOSE , RH-POS-CMD , CFG-RH-DRV-TIME , CFG-RH-POS-DB , RH-FLOAT-SYNC )
"""

_PRG05_STEAM_MOD = """\
REM --- HTG-OUTPUT ---
REM Steam modulating valve from HTG-DAT-LOOP
REM
IF FREEZE-PROT = 0 THEN STM-VLV = HTG-DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN STM-VLV = 0
IF FREEZE-PROT = 1 THEN STM-VLV = CFG-UV-FREEZE-VLV
"""

_PRG05_STEAM_ONOFF = """\
REM --- HTG-OUTPUT ---
REM Steam on/off valve from HTG-DAT-LOOP threshold
REM
IF HTG-DAT-LOOP > 50 THEN STM-VLV = 1
IF HTG-DAT-LOOP < 40 THEN STM-VLV = 0
IF ACT-DAT > CFG-DAT-HL THEN STM-VLV = 0
IF FREEZE-PROT = 1 THEN STM-VLV = 1
"""

_PRG05_HW_MOD_FBP = """\
REM --- HTG-OUTPUT ---
REM HW modulating valve (face/bypass mode)
REM In cold mode: valve = HW-DEMAND (100%)
REM In mild mode: valve = HW-DEMAND (from loop)
REM
HW-VLV = HW-DEMAND
IF ACT-DAT > CFG-DAT-HL THEN HW-VLV = 0
"""

_PRG06_CHW_MOD = """\
REM --- CLG-OUTPUT ---
REM CHW modulating valve from CLG-DAT-LOOP
REM
CHW-VLV = CLG-DAT-LOOP
IF ACT-DAT < CFG-DAT-LL THEN CHW-VLV = 0
IF FREEZE-PROT = 1 THEN CHW-VLV = 0
"""

_PRG06_CHW_FLT = """\
REM --- CLG-OUTPUT ---
REM CHW floating valve using CBAS FLOAT() function
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
REM
REM Position command from cooling DAT loop
CHW-POS-CMD = CLG-DAT-LOOP
REM
REM Safety overrides force valve closed
IF ACT-DAT < CFG-DAT-LL THEN CHW-POS-CMD = 0
IF FREEZE-PROT = 1 THEN CHW-POS-CMD = 0
REM
REM Floating sync on power cycle and unoccupied
IF+ POWER-LOSS THEN START CHW-FLOAT-SYNC
IF+ OCC-MODE = 0 THEN START CHW-FLOAT-SYNC
IF TIME-ON( CHW-FLOAT-SYNC ) > 0:00:05 THEN STOP CHW-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays
CHW-POS = FLOAT( CHW-OPEN , CHW-CLOSE , CHW-POS-CMD , CFG-CHW-DRV-TIME , CFG-CHW-POS-DB , CHW-FLOAT-SYNC )
"""

_PRG06_DX_1 = """\
REM --- CLG-OUTPUT ---
REM DX single stage from CLG-DAT-LOOP
REM
IF CLG-DAT-LOOP > CFG-STG1-T AND DX1-OFF-TMR > 180 THEN DX-STG1 = 1
IF CLG-DAT-LOOP < ( CFG-STG1-T - 10 ) THEN DX-STG1 = 0
IF FREEZE-PROT = 1 THEN DX-STG1 = 0
IF DX-STG1 = 0 THEN DX1-OFF-TMR = 0
IF DX-STG1 = 1 THEN DX1-OFF-TMR = 999
"""

_PRG06_DX_2 = """\
REM --- CLG-OUTPUT ---
REM DX two stage from CLG-DAT-LOOP
REM
IF CLG-DAT-LOOP > CFG-STG1-T AND DX1-OFF-TMR > 180 THEN DX-STG1 = 1
IF CLG-DAT-LOOP < ( CFG-STG1-T - 10 ) THEN DX-STG1 = 0
IF CLG-DAT-LOOP > CFG-STG2-T AND DX-STG1 = 1 AND DX2-OFF-TMR > 300 THEN DX-STG2 = 1
IF CLG-DAT-LOOP < ( CFG-STG2-T - 10 ) THEN DX-STG2 = 0
IF FREEZE-PROT = 1 THEN DX-STG1 = 0 : DX-STG2 = 0
IF DX-STG1 = 0 THEN DX1-OFF-TMR = 0 : DX-STG2 = 0
IF DX-STG1 = 1 THEN DX1-OFF-TMR = 999
IF DX-STG2 = 0 THEN DX2-OFF-TMR = 0
IF DX-STG2 = 1 THEN DX2-OFF-TMR = 999
"""

_PRG07_OAD = """\
REM --- OAD-CTRL ---
REM ASHRAE Cycle 1 (min OA) + Cycle 2 (free cooling)
REM
OAD = CFG-OAD-MIN
IF OCC-MODE = 0 THEN OAD = 0
IF FREEZE-PROT = 1 THEN OAD = 0
IF ACT-OAT < ACT-RMT AND ACT-OAT < CFG-ECON-ENABLE-T THEN CYCLE2-ENABLE = 1 ELSE CYCLE2-ENABLE = 0
IF CYCLE2-ENABLE = 1 AND OCC-MODE = 1 THEN OAD = SLIDE( CLG-DAT-LOOP, 0.0, 100.0, CFG-OAD-MIN, 100.0 )
IF OCC-MODE = 0 THEN OAD = 0
IF FREEZE-PROT = 1 THEN OAD = 0
"""

_PRG07_OAD_FLT = """\
REM --- OAD-CTRL ---
REM ASHRAE Cycle 1+2 floating OA damper using CBAS FLOAT() function
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
REM
REM Cycle 2 enable: OAT < RAT AND OAT < enable temp
IF ACT-OAT < ACT-RMT AND ACT-OAT < CFG-ECON-ENABLE-T THEN CYCLE2-ENABLE = 1 ELSE CYCLE2-ENABLE = 0
REM
REM Position command: min position when occupied, free cooling when Cycle 2 enabled
DMP-POS-CMD = CFG-OAD-MIN
IF CYCLE2-ENABLE = 1 AND OCC-MODE = 1 THEN DMP-POS-CMD = SLIDE( CLG-DAT-LOOP , 0.0 , 100.0 , CFG-OAD-MIN , 100.0 )
REM
REM Safety overrides force damper closed
IF OCC-MODE = 0 THEN DMP-POS-CMD = 0
IF FREEZE-PROT = 1 THEN DMP-POS-CMD = 0
REM
REM Floating sync on power cycle and unoccupied
IF+ POWER-LOSS THEN START DMP-FLOAT-SYNC
IF+ OCC-MODE = 0 THEN START DMP-FLOAT-SYNC
IF TIME-ON( DMP-FLOAT-SYNC ) > 0:00:05 THEN STOP DMP-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays
DMP-POS = FLOAT( DMP-OPEN , DMP-CLOSE , DMP-POS-CMD , CFG-DMP-DRV-TIME , CFG-DMP-POS-DB , DMP-FLOAT-SYNC )
"""

_PRG08_FAN_CV = """\
REM --- FAN-CTRL ---
REM Constant volume on/off
REM
IF OCC-MODE = 1 THEN FAN-CMD = 1
IF OCC-MODE = 0 AND ( ACT-RMT < ACT-HTG-SP OR ACT-RMT > ACT-CLG-SP ) THEN FAN-CMD = 1
IF OCC-MODE = 0 AND ACT-RMT >= ACT-HTG-SP AND ACT-RMT <= ACT-CLG-SP THEN FAN-CMD = 0
IF FREEZE-PROT = 1 THEN FAN-CMD = 0
FAN-S/S = FAN-CMD
"""

_PRG08_FAN_VFD = """\
REM --- FAN-CTRL ---
REM VFD speed from max loop demand
REM
FAN-DMD = MAX( CLG-DAT-LOOP, HTG-DAT-LOOP )
FAN-SPD = SLIDE( FAN-DMD, 0.0, 100.0, CFG-FAN-MIN-SPD, 100.0 )
IF OCC-MODE = 0 AND ACT-RMT >= ACT-HTG-SP AND ACT-RMT <= ACT-CLG-SP THEN FAN-SPD = 0
IF FREEZE-PROT = 1 THEN FAN-SPD = 0
"""

_PRG09_FREEZESTAT = """\
REM --- FREEZESTAT ---
REM Hardware freezestat + DAT low limit, latching
REM
FREEZE-TRIP = 0
IF ACT-DAT < CFG-DAT-FREEZE THEN FREEZE-TRIP = 1
IF FREEZE-STAT = 0 THEN FREEZE-TRIP = 1
IF FREEZE-TRIP = 1 AND FREEZE-LATCH = 0 THEN FREEZE-LATCH = 1
IF FREEZE-LATCH = 1 AND FREEZE-RST = 1 AND ACT-DAT > ( CFG-DAT-FREEZE + 5 ) THEN FREEZE-LATCH = 0
IF FREEZE-LATCH = 1 THEN FREEZE-TRIP = 1
FREEZE-ALARM = FREEZE-LATCH
"""

_PRG_DCV = """\
REM --- DCV-CTRL ---
REM Demand Controlled Ventilation from CO2 sensor
REM Overrides OA damper minimum when CO2 > setpoint
REM
ACT-CO2 = AI4
OAD-DCV = 0
IF OCC-MODE = 1 AND FREEZE-PROT = 0 THEN OAD-DCV = SLIDE( ACT-CO2, CFG-CO2-SP, CFG-CO2-MAX, CFG-OAD-MIN, 100.0 )
IF OCC-MODE = 0 THEN OAD-DCV = 0
IF FREEZE-PROT = 1 THEN OAD-DCV = 0
IF ACT-CO2 > CFG-CO2-SP THEN OAD = MAX( OAD, OAD-DCV )
IF ACT-CO2 > CFG-CO2-ALARM THEN CO2-ALARM = 1 ELSE CO2-ALARM = 0
"""

_PRG_RAD_HTG = """\
REM --- RAD-HTG-PRG ---
REM Radiant heat — reverse-acting OAT reset. Independent of the primary
REM heating coil; runs in parallel. Colder OAT opens the valve, warmer
REM OAT closes it.
REM   OAT <= CFG-RAD-OA-MIN : enabled, valve = CFG-RAD-VLV-MAX (full open)
REM   OAT >= CFG-RAD-OA-MAX : disabled, valve = CFG-RAD-VLV-MIN (closed)
REM   between               : SLIDE reset from VLV-MAX down to VLV-MIN
REM
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
            ValuePoint(4, "CFG-OCC-CLG-SP",    "AV", 75.0,  "Occupied Cooling SP",         "°F"),
            ValuePoint(5, "CFG-OCC-HTG-SP",    "AV", 70.0,  "Occupied Heating SP",         "°F"),
            ValuePoint(6, "CFG-UNOCC-CLG-SP",  "AV", 85.0,  "Unoccupied Cooling SP",       "°F"),
            ValuePoint(7, "CFG-UNOCC-HTG-SP",  "AV", 60.0,  "Unoccupied Heating SP",       "°F"),
            ValuePoint(8, "ACT-CLG-SP",        "AV", 75.0,  "Active Cooling SP",           "°F"),
            ValuePoint(9, "ACT-HTG-SP",        "AV", 70.0,  "Active Heating SP",           "°F"),
            ValuePoint(10, "CLG-SP",           "AV", 75.0,  "Current Cooling SP",          "°F"),
            ValuePoint(11, "HTG-SP",           "AV", 70.0,  "Current Heating SP",          "°F"),
            # DAT setpoints
            ValuePoint(31, "CLG-DAT-SP",       "AV", 55.0,  "Cooling DAT Setpoint",        "°F"),
            ValuePoint(32, "HTG-DAT-SP",       "AV", 95.0,  "Heating DAT Setpoint",        "°F"),
            ValuePoint(33, "CFG-CLG-DAT-MIN",  "AV", 52.0,  "Min Cooling DAT SP",          "°F"),
            ValuePoint(34, "CFG-CLG-DAT-MAX",  "AV", 65.0,  "Max Cooling DAT SP",          "°F"),
            ValuePoint(35, "CFG-HTG-DAT-MIN",  "AV", 85.0,  "Min Heating DAT SP",          "°F"),
            ValuePoint(36, "CFG-HTG-DAT-MAX",  "AV", 110.0, "Max Heating DAT SP",          "°F"),
            # Safety/config
            ValuePoint(37, "CFG-DAT-LL",  "AV", 45.0,  "DAT Low Limit (safety)",      "°F"),
            ValuePoint(38, "CFG-DAT-HL",  "AV", 110.0, "DAT High Limit (safety)",     "°F"),
            ValuePoint(39, "CFG-DAT-FREEZE",   "AV", 38.0,  "DAT Freeze Protection",       "°F"),
            ValuePoint(40, "CFG-UV-FREEZE-OAT","AV", 35.0,  "Freeze Enable OAT",           "°F"),
            ValuePoint(41, "CFG-UV-FREEZE-VLV","AV", 20.0,  "Freeze Valve Position",       "%"),
            ValuePoint(42, "CFG-STG1-T",       "AV", 50.0,  "Stage 1 Threshold",           "%"),
            ValuePoint(43, "CFG-STG2-T",       "AV", 80.0,  "Stage 2 Threshold",           "%"),
            # Network/status
            ValuePoint(12, "NET-OCC-CMD",      "BV", True,  "Network Occupied Command"),
            ValuePoint(13, "OCC-MODE",         "BV", True,  "Occupancy Mode"),
            ValuePoint(14, "HWS-OK",           "BV", True,  "Hot Water Available"),
            ValuePoint(15, "FREEZE-PROT",      "BV", False, "Freeze Protection Active"),
            ValuePoint(16, "FAN-CMD",          "BV", False, "Fan Command"),
        ],

        loops=[
            LoopDef(1, "CLG-RESET-LOOP", "ACT-RMT", "ACT-CLG-SP", "CLG-DAT-SP",
                    p_band=4.0, integral=10.0, action="direct",
                    description="Cooling: space temp resets CLG-DAT-SP"),
            LoopDef(2, "HTG-RESET-LOOP", "ACT-RMT", "ACT-HTG-SP", "HTG-DAT-SP",
                    p_band=4.0, integral=10.0, action="reverse",
                    description="Heating: space temp resets HTG-DAT-SP"),
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
            ProgramDef(2, "DAT-RESET", "PRG02-DAT-RESET.bas", _PRG02_DAT_RESET, True,
                       "Space temp loops reset DAT setpoints", exec_order=2),
            ProgramDef(3, "FREEZE-PROTECT", "PRG03-FREEZE-PROTECT.bas", _PRG03_FREEZE, True,
                       "Unoccupied freeze protection", exec_order=3),
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
providing cascaded PID control. Primary loops reset discharge air temperature
setpoints from space temperature. Secondary DAT loops drive valve or stage
outputs. Freeze protection activates when unoccupied and outdoor temperature
drops below the freeze enable setpoint.""",
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
            ValuePoint(48, "CFG-FAN-MIN-SPD", "AV", 30.0, "Fan Min Speed", "%"),
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
        ],
        programs=[ProgramDef(7, "OAD-CTRL", "PRG07-OAD-CTRL.bas", _PRG07_OAD, True,
                             "OA damper ASHRAE Cycle 1+2", exec_order=7)],
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
        ],
        programs=[ProgramDef(7, "OAD-CTRL", "PRG07-OAD-CTRL.bas", _PRG07_OAD_FLT, True,
                             "OA damper floating Cycle 1+2", exec_order=7)],
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
        description="HW modulating valve from HTG-DAT-LOOP",
        outputs=[OutputPoint(6, "HW-VLV", "AO", "0.0 ->100%", "HW Valve (reverse)", 10.0, 2.0, True)],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HW_MOD, True,
                             "HW mod = HTG-DAT-LOOP", exec_order=5)],
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
            ValuePoint(46, "RH-POS",          "AV", 0.0,   "HW Valve Actual Position",    "%"),
            ValuePoint(47, "RH-POS-CMD",      "AV", 0.0,   "HW Valve Commanded Position", "%"),
            ValuePoint(93, "CFG-RH-POS-DB",   "AV", 2.0,   "HW Float Position Deadband",  "%"),
            ValuePoint(94, "CFG-RH-DRV-TIME", "AV", 150.0, "HW Valve Full Stroke Time",   "Sec"),
            ValuePoint(95, "RH-FLOAT-SYNC",   "BV", False, "HW Float Sync Trigger"),
        ],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HW_FLT, True,
                             "HW float = HTG-DAT-LOOP vs position", exec_order=5)],
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
        description="Steam modulating valve from HTG-DAT-LOOP",
        outputs=[OutputPoint(6, "STM-VLV", "AO", "0.0 ->100%", "Steam Valve", 2.0, 10.0)],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_STEAM_MOD, True,
                             "Steam mod = HTG-DAT-LOOP", exec_order=5)],
        requires=["uv-core"],
        conflicts=["uv-hw-mod", "uv-hw-flt", "uv-hw-mod-fbp", "uv-steam-onoff"],
        mutually_exclusive_group="uv-heating",
    )


def build_uv_steam_onoff():
    return Module(
        id="uv-steam-onoff", name="UV Steam On/Off", category="heating",
        description="Steam on/off valve — cycles on HTG-DAT-LOOP threshold",
        outputs=[OutputPoint(6, "STM-VLV", "BO", "Stop/Start", "Steam Valve")],
        programs=[ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_STEAM_ONOFF, True,
                             "Steam on/off from loop threshold", exec_order=5)],
        requires=["uv-core"],
        conflicts=["uv-hw-mod", "uv-hw-flt", "uv-hw-mod-fbp", "uv-steam-mod"],
        mutually_exclusive_group="uv-heating",
    )


def build_uv_steam_onoff_fbp():
    """Steam on/off for face/bypass — controlled by FBP program"""
    return Module(
        id="uv-steam-onoff-fbp", name="UV Steam On/Off (FBP)", category="heating",
        description="Steam on/off — controlled by FBP cold/mild logic",
        outputs=[OutputPoint(6, "STM-VLV", "BO", "Stop/Start", "Steam Valve")],
        programs=[ProgramDef(4, "FBP-CTRL", "PRG04-FBP-CTRL.bas", _PRG04_FBP_STEAM_ONOFF, True,
                             "FBP + steam on/off", exec_order=4)],
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
        description="CHW modulating valve from CLG-DAT-LOOP",
        outputs=[OutputPoint(4, "CHW-VLV", "AO", "0.0 ->100%", "CHW Valve", 2.0, 10.0)],
        programs=[ProgramDef(6, "CLG-OUTPUT", "PRG06-CLG-OUTPUT.bas", _PRG06_CHW_MOD, True,
                             "CHW mod = CLG-DAT-LOOP", exec_order=6)],
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
                             "CHW float = CLG-DAT-LOOP vs position", exec_order=6)],
        requires=["uv-core"],
        conflicts=["uv-chw-mod", "uv-dx-1", "uv-dx-2"],
        mutually_exclusive_group="uv-cooling",
    )


def build_uv_dx_1():
    return Module(
        id="uv-dx-1", name="UV DX 1-Stage", category="cooling",
        description="DX single stage — CLG-DAT-LOOP > threshold, 3min timer",
        outputs=[OutputPoint(4, "DX-STG1", "BO", "Stop/Start", "DX Stage 1")],
        values=[ValuePoint(50, "DX1-OFF-TMR", "AV", 999.0, "DX1 Off Timer", "Sec")],
        programs=[ProgramDef(6, "CLG-OUTPUT", "PRG06-CLG-OUTPUT.bas", _PRG06_DX_1, True,
                             "DX stg1 from CLG-DAT-LOOP", exec_order=6)],
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
                             "DX 2-stage from CLG-DAT-LOOP", exec_order=6)],
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
            ValuePoint(74, "OAD-DCV",        "AV", 0.0,    "DCV Damper Override",     "%"),
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
        ],
        programs=[ProgramDef(10, "FREEZESTAT", "PRG09-FREEZESTAT.bas", _PRG09_FREEZESTAT, True,
                             "Freezestat latch/reset", exec_order=10)],
        requires=["uv-core"],
    )
