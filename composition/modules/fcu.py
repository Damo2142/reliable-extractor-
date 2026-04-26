"""
FCU (Fan Coil Unit) Modules — All variants

Families: 2-pipe switchover, 2-pipe CHW only, 4-pipe CHW+HW,
          4-pipe CHW+HW+Electric, 4-pipe CHW+Electric,
          DX+HW, DX+Electric, Heat pump, Heat pump+aux

Standard I/O:
  AI1 = DAT (discharge air temp, 10K type III, mandatory)
  AI3 = RMT (room temp, 10K type III)
  BI2 = FAN-STS (fan status feedback)

Control Architecture — Cascaded PID:
  Primary loops: space temp vs setpoint → resets DAT setpoint
  Secondary loops: DAT vs DAT-SP → drives valve/stage output

Controller: MACH-ProZone 88 standard, MACH-ProView LCD optional
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
#  Program Code Constants
# ═══════════════════════════════════════════════════════════════════════════

_PRG_FCU_CFG = """\
REM --- FCU-CFG-PRG ---
REM Configuration — sensors, network data, occupancy, mode
REM {parent} = parent AHU or plant device for network variables
REM
REM --- Read Sensors ---
ACT-DAT = AI1
ACT-RMT = AI3
REM
REM --- Network Reads ---
NET-OCC-CMD = {parent}BV21
HWS-OK = {parent}BV22
NET-OAT = {parent}AV20
REM
REM --- Occupancy ---
IF USE-LOC-SCHD THEN OCC-CMD = LOCAL-SCHEDULE ELSE OCC-CMD = NET-OCC-CMD
REM
REM --- Mode Determination ---
REM 1=Off, 2=Cooling, 3=Heating, 4=Deadband
IF NOT OCC-CMD THEN HVAC-MODE = 1
IF OCC-CMD AND ACT-RMT > CLG-SP THEN HVAC-MODE = 2
IF OCC-CMD AND ACT-RMT < HTG-SP THEN HVAC-MODE = 3
IF OCC-CMD AND ACT-RMT >= HTG-SP AND ACT-RMT <= CLG-SP THEN HVAC-MODE = 4
REM
REM --- Unoccupied Override ---
IF NOT OCC-CMD AND ACT-RMT > ( CLG-SP + CFG-UNOCC-DB ) THEN HVAC-MODE = 2
IF NOT OCC-CMD AND ACT-RMT < ( HTG-SP - CFG-UNOCC-DB ) THEN HVAC-MODE = 3
REM
REM --- DAT Safety Limits ---
DAT-LL-ALARM = ACT-DAT < CFG-DAT-LL
DAT-HL-ALARM = ACT-DAT > CFG-DAT-HL
IF DAT-LL-ALARM THEN HVAC-MODE = 1
REM
REM --- Loop Demand Calc ---
REM Primary loops generate DAT setpoints, secondary loops generate demand
IF HVAC-MODE = 2 THEN LOOP-DEMAND = CLG-DAT-DEMAND
IF HVAC-MODE = 3 THEN LOOP-DEMAND = HTG-DAT-DEMAND
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN LOOP-DEMAND = 0.0
REM
999 REM End
"""

_PRG_FAN_CV = """\
REM --- FCU-FAN-PRG ---
REM Fan control — constant volume on/off
REM Fan runs when any loop demand present or unoccupied override
REM
IF LOOP-DEMAND > 0.0 THEN FAN-CMD = 1
IF HVAC-MODE <= 1 AND LOOP-DEMAND = 0.0 THEN FAN-CMD = 0
IF HVAC-MODE = 4 THEN FAN-CMD = 1
REM
FAN-S/S = FAN-CMD
FAN-FAIL = FAN-CMD AND NOT FAN-STS
REM
999 REM End
"""

_PRG_FAN_MS = """\
REM --- FCU-FAN-PRG ---
REM Fan control — multi-speed from loop demand
REM Low = demand > 0 and < 33%, Med = 33-66%, High >= 66%
REM
IF HVAC-MODE <= 1 THEN FAN-CMD = 0
IF HVAC-MODE = 4 THEN FAN-CMD = 1
REM
REM --- Speed from demand ---
IF LOOP-DEMAND > 0.0 AND LOOP-DEMAND < 33.0 THEN FAN-CMD = 1
IF LOOP-DEMAND >= 33.0 AND LOOP-DEMAND < 66.0 THEN FAN-CMD = 2
IF LOOP-DEMAND >= 66.0 THEN FAN-CMD = 3
IF LOOP-DEMAND = 0.0 AND HVAC-MODE > 1 THEN FAN-CMD = 1
REM
REM --- Relay outputs (only one active at a time) ---
FAN-LO = FAN-CMD = 1
FAN-MED = FAN-CMD = 2
FAN-HI = FAN-CMD = 3
FAN-FAIL = ( FAN-CMD > 0 ) AND NOT FAN-STS
REM
999 REM End
"""

_PRG_FAN_VFD = """\
REM --- FCU-FAN-PRG ---
REM Fan control — VFD speed = max of cooling and heating demand
REM
REM --- Calculate max demand across both loops ---
FAN-DMD = MAX( CLG-DAT-DEMAND, HTG-DAT-DEMAND )
REM
IF HVAC-MODE <= 1 THEN FAN-SPD = 0.0
IF HVAC-MODE = 4 THEN FAN-SPD = CFG-FAN-MIN-SPD
IF HVAC-MODE = 2 OR HVAC-MODE = 3 THEN FAN-SPD = SLIDE( FAN-DMD, 0.0, 100.0, CFG-FAN-MIN-SPD, 100.0 )
REM
FAN-FAIL = ( FAN-SPD > 0.0 ) AND NOT FAN-STS
REM
999 REM End
"""

_PRG_CHW_MOD = """\
REM --- FCU-CLG-PRG ---
REM Cooling — CHW modulating valve from CLG-DAT-LOOP output
REM
IF HVAC-MODE = 2 THEN CHW-VLV = CLG-DAT-DEMAND
IF HVAC-MODE <> 2 THEN CHW-VLV = 0.0
REM
REM --- Safety override ---
IF DAT-LL-ALARM THEN CHW-VLV = 0.0
REM
999 REM End
"""

_PRG_CHW_FLT = """\
REM --- FCU-CLG-PRG ---
REM Cooling — CHW floating point valve from CLG-DAT-LOOP demand
REM Position estimated from pulse time vs CFG-FLT-TRAVEL
REM
REM --- Position estimation ---
IF CHW-VLV-O THEN CHW-VLV-POS = CHW-VLV-POS + ( 100.0 / CFG-FLT-TRAVEL )
IF CHW-VLV-C THEN CHW-VLV-POS = CHW-VLV-POS - ( 100.0 / CFG-FLT-TRAVEL )
CHW-VLV-POS = LIMIT( CHW-VLV-POS, 0.0, 100.0 )
REM
REM --- Open/close from demand vs position ---
IF HVAC-MODE = 2 AND CLG-DAT-DEMAND > ( CHW-VLV-POS + CFG-FLT-DB ) THEN CHW-VLV-O = 1 ELSE CHW-VLV-O = 0
IF HVAC-MODE = 2 AND CLG-DAT-DEMAND < ( CHW-VLV-POS - CFG-FLT-DB ) THEN CHW-VLV-C = 1 ELSE CHW-VLV-C = 0
IF HVAC-MODE <> 2 THEN CHW-VLV-C = 1
IF HVAC-MODE <> 2 THEN CHW-VLV-O = 0
REM
IF DAT-LL-ALARM THEN CHW-VLV-O = 0
IF DAT-LL-ALARM THEN CHW-VLV-C = 1
REM
999 REM End
"""

_PRG_HW_MOD = """\
REM --- FCU-HTG-PRG ---
REM Heating — HW modulating valve from HTG-DAT-LOOP output
REM
IF HVAC-MODE = 3 THEN HW-VLV = HTG-DAT-DEMAND
IF HVAC-MODE <> 3 THEN HW-VLV = 0.0
REM
REM --- Safety override ---
IF DAT-HL-ALARM THEN HW-VLV = 0.0
REM
999 REM End
"""

_PRG_HW_FLT = """\
REM --- FCU-HTG-PRG ---
REM Heating — HW floating point valve from HTG-DAT-LOOP demand
REM Position estimated from pulse time vs CFG-FLT-TRAVEL
REM
REM --- Position estimation ---
IF HW-VLV-O THEN HW-VLV-POS = HW-VLV-POS + ( 100.0 / CFG-FLT-TRAVEL )
IF HW-VLV-C THEN HW-VLV-POS = HW-VLV-POS - ( 100.0 / CFG-FLT-TRAVEL )
HW-VLV-POS = LIMIT( HW-VLV-POS, 0.0, 100.0 )
REM
REM --- Open/close from demand vs position ---
IF HVAC-MODE = 3 AND HTG-DAT-DEMAND > ( HW-VLV-POS + CFG-FLT-DB ) THEN HW-VLV-O = 1 ELSE HW-VLV-O = 0
IF HVAC-MODE = 3 AND HTG-DAT-DEMAND < ( HW-VLV-POS - CFG-FLT-DB ) THEN HW-VLV-C = 1 ELSE HW-VLV-C = 0
IF HVAC-MODE <> 3 THEN HW-VLV-C = 1
IF HVAC-MODE <> 3 THEN HW-VLV-O = 0
REM
IF DAT-HL-ALARM THEN HW-VLV-O = 0
IF DAT-HL-ALARM THEN HW-VLV-C = 1
REM
999 REM End
"""

_PRG_ELEC_1 = """\
REM --- FCU-ELEC-PRG ---
REM Heating — 1 stage electric from loop demand
REM Stage enables when demand > CFG-STG1-T (default 50%)
REM
IF HVAC-MODE = 3 AND HTG-DAT-DEMAND > CFG-STG1-T AND FAN-CMD THEN ELEC-HTR-S/S = 1 ELSE ELEC-HTR-S/S = 0
REM
REM --- Safety: DAT > 87F lockout ---
IF ACT-DAT > 87.0 THEN ELEC-HTR-S/S = 0
IF DAT-HL-ALARM THEN ELEC-HTR-S/S = 0
REM
999 REM End
"""

_PRG_ELEC_2 = """\
REM --- FCU-ELEC-PRG ---
REM Heating — 2 stage electric from HTG-DAT-LOOP demand
REM Stage 1: demand > CFG-STG1-T AND DAT < 87F
REM Stage 2: demand > CFG-STG2-T AND stage 1 on AND DAT < 87F
REM
ELEC-HTR1-S/S = 0
ELEC-HTR2-S/S = 0
IF HVAC-MODE = 3 AND HTG-DAT-DEMAND > CFG-STG1-T AND FAN-CMD AND ACT-DAT < 87.0 THEN ELEC-HTR1-S/S = 1
IF ELEC-HTR1-S/S AND HTG-DAT-DEMAND > CFG-STG2-T AND ACT-DAT < 87.0 THEN ELEC-HTR2-S/S = 1
REM
IF DAT-HL-ALARM THEN ELEC-HTR1-S/S = 0
IF DAT-HL-ALARM THEN ELEC-HTR2-S/S = 0
REM
999 REM End
"""

_PRG_2PIPE_MOD = """\
REM --- FCU-2PIPE-PRG ---
REM 2-pipe switchover — modulating valve controlled by active DAT loop
REM {parent} for HWS-OK network variable
REM
REM --- Switchover Logic ---
IF HWS-OK OR ( NET-OAT < CFG-SWITCHOVER-T ) THEN HTG-MODE = 1 ELSE HTG-MODE = 0
REM
REM --- Valve from active loop demand ---
IF HTG-MODE AND HVAC-MODE = 3 THEN VLV = HTG-DAT-DEMAND
IF NOT HTG-MODE AND HVAC-MODE = 2 THEN VLV = CLG-DAT-DEMAND
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN VLV = 0.0
REM
REM --- Safety ---
IF DAT-LL-ALARM AND NOT HTG-MODE THEN VLV = 0.0
IF DAT-HL-ALARM AND HTG-MODE THEN VLV = 0.0
REM
999 REM End
"""

_PRG_2PIPE_FLT = """\
REM --- FCU-2PIPE-PRG ---
REM 2-pipe switchover — floating valve from active DAT loop demand
REM Position estimated from pulse time vs CFG-FLT-TRAVEL
REM {parent} for HWS-OK network variable
REM
IF HWS-OK OR ( NET-OAT < CFG-SWITCHOVER-T ) THEN HTG-MODE = 1 ELSE HTG-MODE = 0
REM
REM --- Position estimation ---
IF VLV-O THEN VLV-POS = VLV-POS + ( 100.0 / CFG-FLT-TRAVEL )
IF VLV-C THEN VLV-POS = VLV-POS - ( 100.0 / CFG-FLT-TRAVEL )
VLV-POS = LIMIT( VLV-POS, 0.0, 100.0 )
REM
REM --- Determine active demand ---
IF HTG-MODE AND HVAC-MODE = 3 THEN ACTIVE-DMD = HTG-DAT-DEMAND
IF NOT HTG-MODE AND HVAC-MODE = 2 THEN ACTIVE-DMD = CLG-DAT-DEMAND
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN ACTIVE-DMD = 0.0
REM
REM --- Open/close from demand vs position ---
IF ACTIVE-DMD > ( VLV-POS + CFG-FLT-DB ) THEN VLV-O = 1 ELSE VLV-O = 0
IF ACTIVE-DMD < ( VLV-POS - CFG-FLT-DB ) THEN VLV-C = 1 ELSE VLV-C = 0
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN VLV-C = 1
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN VLV-O = 0
REM
999 REM End
"""

_PRG_DX_1 = """\
REM --- FCU-DX-PRG ---
REM DX cooling — single stage compressor from CLG-DAT-LOOP demand
REM ON when demand > CFG-STG1-T AND off-timer elapsed (3 min)
REM
REM --- Stage 1 enable ---
IF HVAC-MODE = 2 AND CLG-DAT-DEMAND > CFG-STG1-T THEN COMP-CMD = 1
IF HVAC-MODE <> 2 OR CLG-DAT-DEMAND < ( CFG-STG1-T - 10.0 ) THEN COMP-CMD = 0
REM
REM --- Min on/off timer (180s) protects compressor ---
IF COMP-CMD AND NOT COMP-S/S THEN COMP-S/S = TIME-ON( COMP-CMD, 0 )
IF COMP-CMD THEN COMP-S/S = 1
IF NOT COMP-CMD AND COMP-S/S THEN COMP-S/S = NOT TIME-OFF( NOT COMP-CMD, 180 )
IF NOT COMP-CMD THEN COMP-OFF-TMR = TIME-ON( NOT COMP-CMD, 180 )
IF COMP-CMD AND COMP-OFF-TMR THEN COMP-S/S = COMP-CMD
REM
999 REM End
"""

_PRG_DX_2 = """\
REM --- FCU-DX-PRG ---
REM DX cooling — two stage from CLG-DAT-LOOP demand
REM Stage 1: demand > CFG-STG1-T AND off-timer elapsed
REM Stage 2: demand > CFG-STG2-T AND stage 1 on AND stage delay elapsed (5 min)
REM
REM --- Stage 1 ---
IF HVAC-MODE = 2 AND CLG-DAT-DEMAND > CFG-STG1-T THEN COMP1-CMD = 1
IF HVAC-MODE <> 2 OR CLG-DAT-DEMAND < ( CFG-STG1-T - 10.0 ) THEN COMP1-CMD = 0
COMP1-S/S = TIME-ON( COMP1-CMD, 180 )
REM
REM --- Stage 2 (requires stage 1 on + 5 min delay) ---
IF COMP1-S/S AND CLG-DAT-DEMAND > CFG-STG2-T THEN COMP2-CMD = 1
IF NOT COMP1-S/S OR CLG-DAT-DEMAND < ( CFG-STG2-T - 10.0 ) THEN COMP2-CMD = 0
COMP2-S/S = TIME-ON( COMP2-CMD, 300 )
REM
999 REM End
"""

_PRG_HP_CORE = """\
REM --- FCU-HP-PRG ---
REM Heat pump — compressor from loop demand > CFG-HP-MIN (10%)
REM Reversing valve state from CFG-RV-CLG field config
REM Min on/off timer 3 minutes protects compressor
REM
REM --- Compressor enable from active demand ---
COMP-CMD = 0
IF HVAC-MODE = 2 AND CLG-DAT-DEMAND > CFG-HP-MIN THEN COMP-CMD = 1
IF HVAC-MODE = 3 AND HTG-DAT-DEMAND > CFG-HP-MIN THEN COMP-CMD = 1
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN COMP-CMD = 0
REM
REM --- Min On/Off Timer (180s) ---
COMP-S/S = TIME-ON( COMP-CMD, 180 )
REM
REM --- Reversing Valve ---
REM CFG-RV-CLG=True: energize in cooling, de-energize in heating
REM CFG-RV-CLG=False: energize in heating, de-energize in cooling
IF CFG-RV-CLG THEN RV = ( HVAC-MODE = 2 )
IF NOT CFG-RV-CLG THEN RV = ( HVAC-MODE = 3 )
REM
REM --- Safety ---
IF DAT-LL-ALARM AND HVAC-MODE = 2 THEN COMP-CMD = 0
IF DAT-HL-ALARM AND HVAC-MODE = 3 THEN COMP-CMD = 0
REM
999 REM End
"""

_PRG_HP_AUX = """\
REM --- FCU-AUX-PRG ---
REM Heat pump aux electric — enables on high demand after delay
REM Aux when HP running AND HTG-DAT-DEMAND > CFG-STG2-T after CFG-AUX-DELAY
REM
AUX-DEMAND = COMP-S/S AND ( HVAC-MODE = 3 ) AND ( HTG-DAT-DEMAND > CFG-STG2-T )
AUX-HTR-S/S = TIME-ON( AUX-DEMAND, CFG-AUX-DELAY )
REM
REM --- Lockout: DAT > 87F ---
IF ACT-DAT > 87.0 THEN AUX-HTR-S/S = 0
IF DAT-HL-ALARM THEN AUX-HTR-S/S = 0
REM
999 REM End
"""

_PRG_ECON_MOD = """\
REM --- FCU-ECON-PRG ---
REM Economizer — modulating OA damper
REM Enable when OAT < RAT and OAT < CFG-ECON-ENABLE-T
REM
ECON-ENABLE = ( NET-OAT < ACT-RMT ) AND ( NET-OAT < CFG-ECON-ENABLE-T ) AND OCC-CMD
REM
IF ECON-ENABLE AND HVAC-MODE = 2 THEN OAD = CLG-DAT-DEMAND
IF NOT ECON-ENABLE OR HVAC-MODE <> 2 THEN OAD = 0.0
REM
999 REM End
"""

_PRG_ECON_FLT = """\
REM --- FCU-ECON-PRG ---
REM Economizer — floating point OA damper from loop demand
REM
ECON-ENABLE = ( NET-OAT < ACT-RMT ) AND ( NET-OAT < CFG-ECON-ENABLE-T ) AND OCC-CMD
REM
IF ECON-ENABLE AND HVAC-MODE = 2 AND CLG-DAT-DEMAND > ( OAD-POS + 3.0 ) THEN OAD-O = 1 ELSE OAD-O = 0
IF ECON-ENABLE AND HVAC-MODE = 2 AND CLG-DAT-DEMAND < ( OAD-POS - 3.0 ) THEN OAD-C = 1 ELSE OAD-C = 0
IF NOT ECON-ENABLE OR HVAC-MODE <> 2 THEN OAD-C = 1
IF NOT ECON-ENABLE OR HVAC-MODE <> 2 THEN OAD-O = 0
REM
999 REM End
"""

_PRG_FREEZESTAT = """\
REM --- FCU-FREEZE-PRG ---
REM Freezestat protection — trips on BI or DAT below CFG-FREEZE-T
REM Manual reset required via FREEZE-RESET BV
REM
IF FREEZE-STAT OR ( ACT-DAT < CFG-FREEZE-T ) THEN FREEZE-TRIP = 1
REM
REM --- Latch until manual reset ---
IF FREEZE-TRIP AND NOT FREEZE-RESET THEN FREEZE-LATCH = 1
IF FREEZE-RESET THEN FREEZE-LATCH = 0
IF FREEZE-RESET THEN FREEZE-TRIP = 0
IF FREEZE-RESET THEN FREEZE-RESET = 0
REM
REM --- Shutdown when latched ---
IF FREEZE-LATCH THEN FAN-CMD = 0
IF FREEZE-LATCH THEN HVAC-MODE = 1
REM
FREEZE-ALARM = FREEZE-LATCH
REM
999 REM End
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Core Module — Always present in every FCU build
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_core():
    """FCU core — sensors, cascade loops, mode determination"""
    return Module(
        id="fcu-core",
        name="FCU Core",
        category="core",
        description="Base FCU: DAT/RMT sensors, cascade loops, occupancy, HVAC mode, DAT limits",
        is_core=True,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250", "Discharge Air Temperature", "°F"),
            InputPoint(2, "FAN-STS", "BI", "Off/On", "Fan Status Feedback"),
            InputPoint(3, "RMT", "AI", "10K -40 ->250", "Room Temperature", "°F"),
        ],

        values=[
            # Sensors / calculated
            ValuePoint(1, "ACT-RMT",          "AV", 72.0,  "Actual Room Temperature",     "°F"),
            ValuePoint(2, "ACT-DAT",          "AV", 55.0,  "Actual Discharge Air Temp",   "°F"),
            ValuePoint(3, "CLG-SP",           "AV", 75.0,  "Cooling Setpoint",            "°F"),
            ValuePoint(4, "HTG-SP",           "AV", 70.0,  "Heating Setpoint",            "°F"),
            ValuePoint(5, "CFG-DAT-LL",       "AV", 45.0,  "DAT Low Limit (safety)",      "°F"),
            ValuePoint(6, "CFG-DAT-HL",       "AV", 95.0,  "DAT High Limit (safety)",     "°F"),
            ValuePoint(7, "CFG-UNOCC-DB",     "AV", 4.0,   "Unoccupied Deadband",         "°F"),
            ValuePoint(8, "NET-OAT",          "AV", 65.0,  "Network OAT",                 "°F"),
            # DAT setpoint reset (loop outputs)
            ValuePoint(31, "CLG-DAT-SP",      "AV", 55.0,  "Cooling DAT Setpoint",        "°F"),
            ValuePoint(32, "HTG-DAT-SP",      "AV", 95.0,  "Heating DAT Setpoint",        "°F"),
            ValuePoint(33, "CFG-CLG-DAT-MIN", "AV", 52.0,  "Min Cooling DAT SP",          "°F"),
            ValuePoint(34, "CFG-CLG-DAT-MAX", "AV", 65.0,  "Max Cooling DAT SP",          "°F"),
            ValuePoint(35, "CFG-HTG-DAT-MIN", "AV", 85.0,  "Min Heating DAT SP",          "°F"),
            ValuePoint(36, "CFG-HTG-DAT-MAX", "AV", 110.0, "Max Heating DAT SP",          "°F"),
            # Loop demand outputs
            ValuePoint(37, "CLG-DAT-DEMAND",  "AV", 0.0,   "Cooling DAT Loop Demand",     "%"),
            ValuePoint(38, "HTG-DAT-DEMAND",  "AV", 0.0,   "Heating DAT Loop Demand",     "%"),
            ValuePoint(39, "LOOP-DEMAND",     "AV", 0.0,   "Active Loop Demand",          "%"),
            # Stage thresholds
            ValuePoint(40, "CFG-STG1-T",      "AV", 50.0,  "Stage 1 Threshold",           "%"),
            ValuePoint(41, "CFG-STG2-T",      "AV", 80.0,  "Stage 2 Threshold",           "%"),
            # Occupancy
            ValuePoint(10, "NET-OCC-CMD",     "BV", True,  "Network Occupied Command"),
            ValuePoint(11, "OCC-CMD",         "BV", True,  "Occupancy Command"),
            ValuePoint(12, "USE-LOC-SCHD",    "BV", False, "Use Local Schedule"),
            # Status
            ValuePoint(13, "FAN-CMD",         "BV", False, "Fan Command"),
            ValuePoint(14, "FAN-FAIL",        "BV", False, "Fan Failure Alarm"),
            ValuePoint(15, "DAT-LL-ALARM",    "BV", False, "DAT Low Limit Alarm"),
            ValuePoint(16, "DAT-HL-ALARM",    "BV", False, "DAT High Limit Alarm"),
            ValuePoint(17, "HWS-OK",          "BV", True,  "Hot Water Available (network)"),
            # Modes
            ValuePoint(20, "HVAC-MODE",       "MV", "Off",
                       "HVAC Mode",
                       states={1: "Off", 2: "Cooling", 3: "Heating", 4: "Deadband"}),
        ],

        loops=[
            # Primary: space temp → DAT setpoint reset
            LoopDef(1, "CLG-RESET-LOOP", "ACT-RMT", "CLG-SP", "CLG-DAT-SP",
                    p_band=4.0, integral=10.0, action="direct",
                    description="Cooling reset: space temp resets CLG-DAT-SP"),
            LoopDef(2, "HTG-RESET-LOOP", "ACT-RMT", "HTG-SP", "HTG-DAT-SP",
                    p_band=4.0, integral=10.0, action="reverse",
                    description="Heating reset: space temp resets HTG-DAT-SP"),
            # Secondary: DAT → valve/stage demand
            LoopDef(3, "CLG-DAT-LOOP", "ACT-DAT", "CLG-DAT-SP", "CLG-DAT-DEMAND",
                    p_band=8.0, integral=20.0, action="direct",
                    description="Cooling DAT loop: DAT vs CLG-DAT-SP"),
            LoopDef(4, "HTG-DAT-LOOP", "ACT-DAT", "HTG-DAT-SP", "HTG-DAT-DEMAND",
                    p_band=8.0, integral=20.0, action="reverse",
                    description="Heating DAT loop: DAT vs HTG-DAT-SP"),
        ],

        programs=[
            ProgramDef(1, "FCU-CFG-PRG", "PRG01-FCU-CFG.bas", _PRG_FCU_CFG, True,
                       "Configuration — sensors, network, mode, loop demand",
                       exec_order=1),
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
providing fully automatic cascaded control. Primary PID loops shall reset
discharge air temperature setpoints based on space temperature deviation
from setpoint. Secondary PID loops shall modulate valve position or stage
outputs to maintain the discharge air temperature setpoint. Occupancy
shall be determined by network command or local schedule.""",
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
        description="Constant volume fan — single on/off relay",

        outputs=[
            OutputPoint(1, "FAN-S/S", "BO", "Stop/Start", "Fan Start/Stop Command"),
        ],

        programs=[
            ProgramDef(2, "FCU-FAN-PRG", "PRG02-FCU-FAN.bas", _PRG_FAN_CV, True,
                       "Fan control — constant volume on/off", exec_order=2),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-fan-ms", "fcu-fan-vfd"],
        mutually_exclusive_group="fcu-fan",
    )


def build_fcu_fan_ms():
    """FCU fan — multi-speed 3 relays"""
    return Module(
        id="fcu-fan-ms",
        name="FCU Fan Multi-Speed",
        category="fan",
        description="Multi-speed fan — low/med/high from loop demand",

        outputs=[
            OutputPoint(1, "FAN-LO", "BO", "Stop/Start", "Fan Low Speed"),
            OutputPoint(2, "FAN-MED", "BO", "Stop/Start", "Fan Medium Speed"),
            OutputPoint(3, "FAN-HI", "BO", "Stop/Start", "Fan High Speed"),
        ],

        programs=[
            ProgramDef(2, "FCU-FAN-PRG", "PRG02-FCU-FAN.bas", _PRG_FAN_MS, True,
                       "Fan control — multi-speed from loop demand", exec_order=2),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-fan-cv", "fcu-fan-vfd"],
        mutually_exclusive_group="fcu-fan",
    )


def build_fcu_fan_vfd():
    """FCU fan — VFD speed control"""
    return Module(
        id="fcu-fan-vfd",
        name="FCU Fan VFD",
        category="fan",
        description="VFD fan — speed tracks loop demand",

        outputs=[
            OutputPoint(1, "FAN-SPD", "AO", "0.0 ->100%", "Fan Speed Command", 0.0, 10.0),
        ],

        values=[
            ValuePoint(30, "CFG-FAN-MIN-SPD", "AV", 30.0, "Fan Minimum Speed",      "%"),
            ValuePoint(48, "FAN-DMD",         "AV", 0.0,  "Fan Demand (max of loops)", "%"),
        ],

        programs=[
            ProgramDef(2, "FCU-FAN-PRG", "PRG02-FCU-FAN.bas", _PRG_FAN_VFD, True,
                       "Fan control — VFD speed from demand", exec_order=2),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-fan-cv", "fcu-fan-ms"],
        mutually_exclusive_group="fcu-fan",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Cooling Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_chw_mod():
    """CHW cooling — modulating valve"""
    return Module(
        id="fcu-chw-mod",
        name="FCU CHW Modulating",
        category="cooling",
        description="CHW cooling — modulating valve driven by CLG-DAT-LOOP",

        outputs=[
            OutputPoint(4, "CHW-VLV", "AO", "0.0 ->100%", "CHW Valve", 2.0, 10.0),
        ],

        programs=[
            ProgramDef(3, "FCU-CLG-PRG", "PRG03-FCU-CLG.bas", _PRG_CHW_MOD, True,
                       "Cooling — CHW modulating from DAT loop", exec_order=3),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-chw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-dx-1", "fcu-dx-2", "fcu-hp-core"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_chw_flt():
    """CHW cooling — floating point valve"""
    return Module(
        id="fcu-chw-flt",
        name="FCU CHW Floating",
        category="cooling",
        description="CHW cooling — floating point valve from CLG-DAT-LOOP demand",

        outputs=[
            OutputPoint(4, "CHW-VLV-O", "BO", "Stop/Start", "CHW Valve Open"),
            OutputPoint(5, "CHW-VLV-C", "BO", "Stop/Start", "CHW Valve Close"),
        ],

        values=[
            ValuePoint(45, "CHW-VLV-POS",    "AV", 0.0,   "CHW Valve Position (est)",  "%"),
            ValuePoint(90, "CFG-FLT-DB",     "AV", 2.0,   "Float Valve Deadband",      "%"),
            ValuePoint(91, "CFG-FLT-TRAVEL", "AV", 150.0, "Float Valve Travel Time",   "Sec"),
        ],

        programs=[
            ProgramDef(3, "FCU-CLG-PRG", "PRG03-FCU-CLG.bas", _PRG_CHW_FLT, True,
                       "Cooling — CHW floating from DAT loop", exec_order=3),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-dx-1", "fcu-dx-2", "fcu-hp-core"],
        mutually_exclusive_group="fcu-cooling",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Heating Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_hw_mod():
    """HW heating — modulating valve"""
    return Module(
        id="fcu-hw-mod",
        name="FCU HW Modulating",
        category="heating",
        description="HW heating — modulating valve driven by HTG-DAT-LOOP",

        outputs=[
            OutputPoint(6, "HW-VLV", "AO", "0.0 ->100%", "HW Valve (reverse)", 10.0, 2.0, True),
        ],

        programs=[
            ProgramDef(4, "FCU-HTG-PRG", "PRG04-FCU-HTG.bas", _PRG_HW_MOD, True,
                       "Heating — HW modulating from DAT loop", exec_order=4),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-hw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-hp-core", "fcu-hp-aux"],
        mutually_exclusive_group="fcu-heating",
    )


def build_fcu_hw_flt():
    """HW heating — floating point valve"""
    return Module(
        id="fcu-hw-flt",
        name="FCU HW Floating",
        category="heating",
        description="HW heating — floating point valve from HTG-DAT-LOOP demand",

        outputs=[
            OutputPoint(6, "HW-VLV-O", "BO", "Stop/Start", "HW Valve Open"),
            OutputPoint(7, "HW-VLV-C", "BO", "Stop/Start", "HW Valve Close"),
        ],

        values=[
            ValuePoint(46, "HW-VLV-POS",    "AV", 0.0,   "HW Valve Position (est)",   "%"),
            ValuePoint(90, "CFG-FLT-DB",     "AV", 2.0,   "Float Valve Deadband",      "%"),
            ValuePoint(91, "CFG-FLT-TRAVEL", "AV", 150.0, "Float Valve Travel Time",   "Sec"),
        ],

        programs=[
            ProgramDef(4, "FCU-HTG-PRG", "PRG04-FCU-HTG.bas", _PRG_HW_FLT, True,
                       "Heating — HW floating from DAT loop", exec_order=4),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-hw-mod", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-hp-core", "fcu-hp-aux"],
        mutually_exclusive_group="fcu-heating",
    )


def build_fcu_elec_1():
    """Electric heating — 1 stage"""
    return Module(
        id="fcu-elec-1",
        name="FCU Electric 1-Stage",
        category="heating",
        description="Electric heating — stage from HTG-DAT-LOOP demand > threshold",

        outputs=[
            OutputPoint(8, "ELEC-HTR-S/S", "BO", "Stop/Start", "Electric Heater"),
        ],

        programs=[
            ProgramDef(5, "FCU-ELEC-PRG", "PRG05-FCU-ELEC.bas", _PRG_ELEC_1, True,
                       "Heating — 1 stage electric from loop demand", exec_order=5),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-elec-2", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-hp-core", "fcu-hp-aux"],
    )


def build_fcu_elec_2():
    """Electric heating — 2 stage"""
    return Module(
        id="fcu-elec-2",
        name="FCU Electric 2-Stage",
        category="heating",
        description="Electric heating — 2 stages from HTG-DAT-LOOP demand > thresholds",

        outputs=[
            OutputPoint(8, "ELEC-HTR1-S/S", "BO", "Stop/Start", "Electric Heater Stage 1"),
            OutputPoint(9, "ELEC-HTR2-S/S", "BO", "Stop/Start", "Electric Heater Stage 2"),
        ],

        programs=[
            ProgramDef(5, "FCU-ELEC-PRG", "PRG05-FCU-ELEC.bas", _PRG_ELEC_2, True,
                       "Heating — 2 stage electric from loop demand", exec_order=5),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-elec-1", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-hp-core", "fcu-hp-aux"],
    )


# ═══════════════════════════════════════════════════════════════════════════
#  2-Pipe Switchover Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_2pipe_mod():
    """2-pipe switchover — modulating valve"""
    return Module(
        id="fcu-2pipe-mod",
        name="FCU 2-Pipe Modulating",
        category="cooling",
        description="2-pipe switchover — valve from active DAT loop, reverses by mode",

        outputs=[
            OutputPoint(4, "VLV", "AO", "0.0 ->100%", "2-Pipe Valve", 2.0, 10.0),
        ],

        values=[
            ValuePoint(42, "HTG-MODE",          "BV", False, "Heating Mode Active"),
            ValuePoint(43, "CFG-SWITCHOVER-T",  "AV", 55.0,  "Switchover Temperature", "°F"),
        ],

        programs=[
            ProgramDef(3, "FCU-2PIPE-PRG", "PRG03-FCU-2PIPE.bas", _PRG_2PIPE_MOD, True,
                       "2-pipe switchover — modulating from DAT loop", exec_order=3),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-flt",
                   "fcu-dx-1", "fcu-dx-2", "fcu-hp-core",
                   "fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_2pipe_flt():
    """2-pipe switchover — floating point valve"""
    return Module(
        id="fcu-2pipe-flt",
        name="FCU 2-Pipe Floating",
        category="cooling",
        description="2-pipe switchover — floating valve from active DAT loop",

        outputs=[
            OutputPoint(4, "VLV-O", "BO", "Stop/Start", "2-Pipe Valve Open"),
            OutputPoint(5, "VLV-C", "BO", "Stop/Start", "2-Pipe Valve Close"),
        ],

        values=[
            ValuePoint(42, "HTG-MODE",          "BV", False, "Heating Mode Active"),
            ValuePoint(43, "CFG-SWITCHOVER-T",  "AV", 55.0,  "Switchover Temperature", "°F"),
            ValuePoint(44, "VLV-POS",           "AV", 0.0,   "Valve Position (est)",   "%"),
            ValuePoint(47, "ACTIVE-DMD",        "AV", 0.0,   "Active Demand",          "%"),
            ValuePoint(90, "CFG-FLT-DB",        "AV", 2.0,   "Float Valve Deadband",   "%"),
            ValuePoint(91, "CFG-FLT-TRAVEL",    "AV", 150.0, "Float Valve Travel Time", "Sec"),
        ],

        programs=[
            ProgramDef(3, "FCU-2PIPE-PRG", "PRG03-FCU-2PIPE.bas", _PRG_2PIPE_FLT, True,
                       "2-pipe switchover — floating from DAT loop", exec_order=3),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-mod",
                   "fcu-dx-1", "fcu-dx-2", "fcu-hp-core",
                   "fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-cooling",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  DX Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_dx_1():
    """DX cooling — single stage compressor"""
    return Module(
        id="fcu-dx-1",
        name="FCU DX 1-Stage",
        category="cooling",
        description="DX cooling — stage from CLG-DAT-LOOP demand > threshold, 3min timer",

        outputs=[
            OutputPoint(4, "COMP-S/S", "BO", "Stop/Start", "Compressor Start/Stop"),
        ],

        values=[
            ValuePoint(50, "COMP-CMD", "BV", False, "Compressor Command"),
        ],

        programs=[
            ProgramDef(3, "FCU-DX-PRG", "PRG03-FCU-DX.bas", _PRG_DX_1, True,
                       "DX cooling — single stage, 3 min timer", exec_order=3),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-dx-2", "fcu-hp-core"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_dx_2():
    """DX cooling — two stage compressor"""
    return Module(
        id="fcu-dx-2",
        name="FCU DX 2-Stage",
        category="cooling",
        description="DX cooling — 2 stages from CLG-DAT-LOOP demand > thresholds",

        outputs=[
            OutputPoint(4, "COMP1-S/S", "BO", "Stop/Start", "Compressor Stage 1"),
            OutputPoint(5, "COMP2-S/S", "BO", "Stop/Start", "Compressor Stage 2"),
        ],

        values=[
            ValuePoint(50, "COMP1-CMD", "BV", False, "Compressor 1 Command"),
            ValuePoint(51, "COMP2-CMD", "BV", False, "Compressor 2 Command"),
        ],

        programs=[
            ProgramDef(3, "FCU-DX-PRG", "PRG03-FCU-DX.bas", _PRG_DX_2, True,
                       "DX cooling — two stage, 3/5 min timers", exec_order=3),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-dx-1", "fcu-hp-core"],
        mutually_exclusive_group="fcu-cooling",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Economizer Modules (optional)
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_econ_mod():
    """Economizer — modulating OA damper"""
    return Module(
        id="fcu-econ-mod",
        name="FCU Economizer Modulating",
        category="economizer",
        description="Economizer OA damper — modulating from CLG-DAT-LOOP demand",

        outputs=[
            OutputPoint(10, "OAD", "AO", "0.0 ->100%", "OA Damper", 2.0, 10.0),
        ],

        values=[
            ValuePoint(60, "CFG-ECON-ENABLE-T", "AV", 65.0, "Economizer Enable Temp", "°F"),
            ValuePoint(61, "ECON-ENABLE",       "BV", False, "Economizer Enabled"),
        ],

        programs=[
            ProgramDef(6, "FCU-ECON-PRG", "PRG06-FCU-ECON.bas", _PRG_ECON_MOD, True,
                       "Economizer — modulating from loop demand", exec_order=6),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-econ-flt"],
        mutually_exclusive_group="fcu-econ",
    )


def build_fcu_econ_flt():
    """Economizer — floating point OA damper"""
    return Module(
        id="fcu-econ-flt",
        name="FCU Economizer Floating",
        category="economizer",
        description="Economizer OA damper — floating point from loop demand",

        outputs=[
            OutputPoint(10, "OAD-O", "BO", "Stop/Start", "OA Damper Open"),
            OutputPoint(11, "OAD-C", "BO", "Stop/Start", "OA Damper Close"),
        ],

        values=[
            ValuePoint(60, "CFG-ECON-ENABLE-T", "AV", 65.0, "Economizer Enable Temp", "°F"),
            ValuePoint(61, "ECON-ENABLE",       "BV", False, "Economizer Enabled"),
            ValuePoint(62, "OAD-POS",           "AV", 0.0,  "OA Damper Position (est)", "%"),
        ],

        programs=[
            ProgramDef(6, "FCU-ECON-PRG", "PRG06-FCU-ECON.bas", _PRG_ECON_FLT, True,
                       "Economizer — floating from loop demand", exec_order=6),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-econ-mod"],
        mutually_exclusive_group="fcu-econ",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Heat Pump Modules
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_hp_core():
    """Heat pump — reversing valve + compressor"""
    return Module(
        id="fcu-hp-core",
        name="FCU Heat Pump",
        category="cooling",
        description="Heat pump — compressor from loop demand, CFG-RV-CLG config",

        outputs=[
            OutputPoint(4, "COMP-S/S", "BO", "Stop/Start", "Compressor Start/Stop"),
            OutputPoint(5, "RV", "BO", "Stop/Start", "Reversing Valve"),
        ],

        values=[
            ValuePoint(50, "COMP-CMD",    "BV", False, "Compressor Command"),
            ValuePoint(55, "CFG-RV-CLG",  "BV", True,  "RV Energized in Cooling (field config)"),
            ValuePoint(58, "CFG-HP-MIN",  "AV", 10.0,  "HP Compressor Min Demand",    "%"),
        ],

        programs=[
            ProgramDef(3, "FCU-HP-PRG", "PRG03-FCU-HP.bas", _PRG_HP_CORE, True,
                       "Heat pump — compressor + RV from loop demand", exec_order=3),
        ],

        requires=["fcu-core"],
        conflicts=["fcu-chw-mod", "fcu-chw-flt", "fcu-2pipe-mod", "fcu-2pipe-flt",
                   "fcu-dx-1", "fcu-dx-2",
                   "fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-cooling",
    )


def build_fcu_hp_aux():
    """Heat pump aux — electric backup heat"""
    return Module(
        id="fcu-hp-aux",
        name="FCU HP Aux Electric",
        category="heating",
        description="HP aux heat — enables on high demand after delay",

        outputs=[
            OutputPoint(6, "AUX-HTR-S/S", "BO", "Stop/Start", "Auxiliary Electric Heater"),
        ],

        values=[
            ValuePoint(56, "CFG-AUX-DELAY", "AV", 600.0, "Aux Heat Enable Delay", "Sec"),
            ValuePoint(57, "AUX-DEMAND",    "BV", False,  "Aux Heat Demand"),
        ],

        programs=[
            ProgramDef(4, "FCU-AUX-PRG", "PRG04-FCU-AUX.bas", _PRG_HP_AUX, True,
                       "Aux electric — from loop demand after delay", exec_order=4),
        ],

        requires=["fcu-hp-core"],
        conflicts=["fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-heating",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Freezestat Module (optional)
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_freezestat():
    """Freezestat protection — trips on BI or low DAT"""
    return Module(
        id="fcu-freezestat",
        name="FCU Freezestat",
        category="safety",
        description="Freezestat BI + low DAT backup — latching shutdown, manual reset",

        inputs=[
            InputPoint(4, "FREEZE-STAT", "BI", "Normal/Alarm", "Freezestat Contact"),
        ],

        values=[
            ValuePoint(70, "CFG-FREEZE-T",  "AV", 38.0,  "Freeze Protection DAT Limit", "°F"),
            ValuePoint(71, "FREEZE-TRIP",   "BV", False, "Freeze Trip Active"),
            ValuePoint(72, "FREEZE-LATCH",  "BV", False, "Freeze Latch (manual reset)"),
            ValuePoint(73, "FREEZE-RESET",  "BV", False, "Freeze Reset Command"),
            ValuePoint(74, "FREEZE-ALARM",  "BV", False, "Freeze Alarm"),
        ],

        programs=[
            ProgramDef(7, "FCU-FREEZE-PRG", "PRG07-FCU-FREEZE.bas", _PRG_FREEZESTAT, True,
                       "Freezestat — latching shutdown", exec_order=7),
        ],

        requires=["fcu-core"],
    )
