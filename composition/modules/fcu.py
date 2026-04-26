"""
FCU (Fan Coil Unit) Modules — All variants

Families: 2-pipe switchover, 2-pipe CHW only, 4-pipe CHW+HW,
          4-pipe CHW+HW+Electric, 4-pipe CHW+Electric,
          DX+HW, DX+Electric, Heat pump, Heat pump+aux

Standard I/O:
  AI1 = DAT (discharge air temp, 10K type III, mandatory)
  AI3 = RMT (room temp, 10K type III)
  BI2 = FAN-STS (fan status feedback)

Controller: MACH-ProZone 88 standard
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
REM Configuration — reads sensors, network data, mode determination
REM {parent} = parent AHU or plant device for network variables
REM
REM --- Read Sensors ---
ACT-DAT = AI1
ACT-RMT = AI3
REM
REM --- Network Reads ---
NET-OCC-CMD = {parent}BV21
HWS-OK = {parent}BV22
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
REM --- DAT Limits ---
DAT-LL-ALARM = ACT-DAT < CFG-DAT-LL
DAT-HL-ALARM = ACT-DAT > CFG-DAT-HL
REM
999 REM End
"""

_PRG_FAN_CV = """\
REM --- FCU-FAN-PRG ---
REM Fan control — constant volume on/off
REM
REM Fan runs when occupied or unoccupied deviation exceeds deadband
IF HVAC-MODE > 1 THEN FAN-CMD = 1
IF HVAC-MODE = 1 AND ACT-RMT > ( CLG-SP + CFG-UNOCC-DB ) THEN FAN-CMD = 1
IF HVAC-MODE = 1 AND ACT-RMT < ( HTG-SP - CFG-UNOCC-DB ) THEN FAN-CMD = 1
IF HVAC-MODE = 1 AND ACT-RMT <= ( CLG-SP + CFG-UNOCC-DB ) AND ACT-RMT >= ( HTG-SP - CFG-UNOCC-DB ) THEN FAN-CMD = 0
REM
FAN-S/S = FAN-CMD
REM
REM --- Fan Status / Fail ---
FAN-FAIL = FAN-CMD AND NOT FAN-STS
REM
999 REM End
"""

_PRG_FAN_MS = """\
REM --- FCU-FAN-PRG ---
REM Fan control — multi-speed (low/med/high)
REM
REM Determine speed from demand
IF HVAC-MODE = 1 THEN FAN-CMD = 0
IF HVAC-MODE = 4 THEN FAN-CMD = 1
IF HVAC-MODE = 2 THEN FAN-CMD = LIMIT( 1 + ( ACT-RMT - CLG-SP ) / 3.0, 1, 3 )
IF HVAC-MODE = 3 THEN FAN-CMD = LIMIT( 1 + ( HTG-SP - ACT-RMT ) / 3.0, 1, 3 )
REM
REM --- Stage to relays ---
FAN-LO = FAN-CMD >= 1
FAN-MED = FAN-CMD >= 2
FAN-HI = FAN-CMD >= 3
REM
FAN-FAIL = ( FAN-CMD > 0 ) AND NOT FAN-STS
REM
999 REM End
"""

_PRG_FAN_VFD = """\
REM --- FCU-FAN-PRG ---
REM Fan control — VFD speed
REM
IF HVAC-MODE = 1 THEN FAN-SPD = 0.0
IF HVAC-MODE = 4 THEN FAN-SPD = CFG-FAN-MIN-SPD
IF HVAC-MODE = 2 THEN FAN-SPD = SLIDE( ACT-RMT - CLG-SP, 0.0, 5.0, CFG-FAN-MIN-SPD, 100.0 )
IF HVAC-MODE = 3 THEN FAN-SPD = SLIDE( HTG-SP - ACT-RMT, 0.0, 5.0, CFG-FAN-MIN-SPD, 100.0 )
REM
FAN-FAIL = ( FAN-SPD > 0 ) AND NOT FAN-STS
REM
999 REM End
"""

_PRG_CHW_MOD = """\
REM --- FCU-CLG-PRG ---
REM Cooling control — CHW modulating valve
REM
IF HVAC-MODE = 2 THEN CHW-VLV = SLIDE( ACT-RMT - CLG-SP, 0.0, 3.0, 0.0, 100.0 )
IF HVAC-MODE <> 2 THEN CHW-VLV = 0.0
REM
REM --- DAT low limit override ---
IF DAT-LL-ALARM THEN CHW-VLV = 0.0
REM
999 REM End
"""

_PRG_CHW_FLT = """\
REM --- FCU-CLG-PRG ---
REM Cooling control — CHW floating point valve
REM
IF HVAC-MODE = 2 AND ACT-RMT > ( CLG-SP + 0.5 ) THEN CHW-VLV-O = 1 ELSE CHW-VLV-O = 0
IF HVAC-MODE = 2 AND ACT-RMT < ( CLG-SP - 0.5 ) THEN CHW-VLV-C = 1 ELSE CHW-VLV-C = 0
IF HVAC-MODE <> 2 THEN CHW-VLV-C = 1
REM
IF DAT-LL-ALARM THEN CHW-VLV-O = 0
IF DAT-LL-ALARM THEN CHW-VLV-C = 1
REM
999 REM End
"""

_PRG_HW_MOD = """\
REM --- FCU-HTG-PRG ---
REM Heating control — HW modulating valve
REM
IF HVAC-MODE = 3 THEN HW-VLV = SLIDE( HTG-SP - ACT-RMT, 0.0, 3.0, 0.0, 100.0 )
IF HVAC-MODE <> 3 THEN HW-VLV = 0.0
REM
REM --- DAT high limit override ---
IF DAT-HL-ALARM THEN HW-VLV = 0.0
REM
999 REM End
"""

_PRG_HW_FLT = """\
REM --- FCU-HTG-PRG ---
REM Heating control — HW floating point valve
REM
IF HVAC-MODE = 3 AND ACT-RMT < ( HTG-SP - 0.5 ) THEN HW-VLV-O = 1 ELSE HW-VLV-O = 0
IF HVAC-MODE = 3 AND ACT-RMT > ( HTG-SP + 0.5 ) THEN HW-VLV-C = 1 ELSE HW-VLV-C = 0
IF HVAC-MODE <> 3 THEN HW-VLV-C = 1
REM
IF DAT-HL-ALARM THEN HW-VLV-O = 0
IF DAT-HL-ALARM THEN HW-VLV-C = 1
REM
999 REM End
"""

_PRG_ELEC_1 = """\
REM --- FCU-HTG-PRG ---
REM Heating control — 1 stage electric
REM
REM Electric lockout at DAT > 87F
IF HVAC-MODE = 3 AND ACT-DAT < 87.0 AND FAN-CMD THEN ELEC-HTR-S/S = 1 ELSE ELEC-HTR-S/S = 0
REM
REM --- DAT high limit override ---
IF DAT-HL-ALARM THEN ELEC-HTR-S/S = 0
REM
999 REM End
"""

_PRG_ELEC_2 = """\
REM --- FCU-HTG-PRG ---
REM Heating control — 2 stage electric
REM
REM Stage 1: enable on heating demand with fan proven
IF HVAC-MODE = 3 AND ACT-DAT < 87.0 AND FAN-CMD THEN ELEC-HTR1-S/S = 1 ELSE ELEC-HTR1-S/S = 0
REM Stage 2: enable when temp still below SP after stage 1
IF ELEC-HTR1-S/S AND ( HTG-SP - ACT-RMT ) > 3.0 AND ACT-DAT < 87.0 THEN ELEC-HTR2-S/S = 1 ELSE ELEC-HTR2-S/S = 0
REM
IF DAT-HL-ALARM THEN ELEC-HTR1-S/S = 0
IF DAT-HL-ALARM THEN ELEC-HTR2-S/S = 0
REM
999 REM End
"""

_PRG_2PIPE_MOD = """\
REM --- FCU-2PIPE-PRG ---
REM 2-pipe switchover — single modulating valve
REM {parent} for HWS-OK network variable
REM
REM --- Switchover Logic ---
REM Heating mode when HW available OR OAT below switchover temp
IF HWS-OK OR ( NET-OAT < CFG-SWITCHOVER-T ) THEN HTG-MODE = 1 ELSE HTG-MODE = 0
REM
REM --- Valve Control ---
IF HTG-MODE AND HVAC-MODE = 3 THEN VLV = SLIDE( HTG-SP - ACT-RMT, 0.0, 3.0, 0.0, 100.0 )
IF NOT HTG-MODE AND HVAC-MODE = 2 THEN VLV = SLIDE( ACT-RMT - CLG-SP, 0.0, 3.0, 0.0, 100.0 )
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN VLV = 0.0
REM
REM --- DAT Limits ---
IF DAT-LL-ALARM AND NOT HTG-MODE THEN VLV = 0.0
IF DAT-HL-ALARM AND HTG-MODE THEN VLV = 0.0
REM
999 REM End
"""

_PRG_2PIPE_FLT = """\
REM --- FCU-2PIPE-PRG ---
REM 2-pipe switchover — floating point valve
REM {parent} for HWS-OK network variable
REM
REM --- Switchover Logic ---
IF HWS-OK OR ( NET-OAT < CFG-SWITCHOVER-T ) THEN HTG-MODE = 1 ELSE HTG-MODE = 0
REM
REM --- Valve Control (heating mode) ---
IF HTG-MODE AND HVAC-MODE = 3 AND ACT-RMT < ( HTG-SP - 0.5 ) THEN VLV-O = 1 ELSE VLV-O = 0
IF HTG-MODE AND HVAC-MODE = 3 AND ACT-RMT > ( HTG-SP + 0.5 ) THEN VLV-C = 1 ELSE VLV-C = 0
REM --- Valve Control (cooling mode) ---
IF NOT HTG-MODE AND HVAC-MODE = 2 AND ACT-RMT > ( CLG-SP + 0.5 ) THEN VLV-O = 1
IF NOT HTG-MODE AND HVAC-MODE = 2 AND ACT-RMT < ( CLG-SP - 0.5 ) THEN VLV-C = 1
REM --- Off ---
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN VLV-C = 1
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN VLV-O = 0
REM
999 REM End
"""

_PRG_DX_1 = """\
REM --- FCU-DX-PRG ---
REM DX cooling — single stage compressor
REM Min on/off timer 3 minutes (180 seconds)
REM
IF HVAC-MODE = 2 AND ACT-RMT > ( CLG-SP + 1.0 ) THEN COMP-CMD = 1
IF HVAC-MODE <> 2 OR ACT-RMT < ( CLG-SP - 1.0 ) THEN COMP-CMD = 0
REM
REM --- Min On/Off Timer ---
COMP-S/S = TIME-ON( COMP-CMD, 180 )
IF NOT COMP-CMD THEN COMP-S/S = NOT TIME-ON( NOT COMP-CMD, 180 )
REM
999 REM End
"""

_PRG_DX_2 = """\
REM --- FCU-DX-PRG ---
REM DX cooling — two stage compressor
REM Stage 1 min on/off 3 min, stage 2 delay 5 min after stage 1
REM
REM --- Stage 1 ---
IF HVAC-MODE = 2 AND ACT-RMT > ( CLG-SP + 1.0 ) THEN COMP1-CMD = 1
IF HVAC-MODE <> 2 OR ACT-RMT < ( CLG-SP - 1.0 ) THEN COMP1-CMD = 0
COMP1-S/S = TIME-ON( COMP1-CMD, 180 )
REM
REM --- Stage 2 (5 min delay after stage 1) ---
IF COMP1-S/S AND ACT-RMT > ( CLG-SP + 2.0 ) THEN COMP2-CMD = 1
IF NOT COMP1-S/S OR ACT-RMT < ( CLG-SP - 0.5 ) THEN COMP2-CMD = 0
COMP2-S/S = TIME-ON( COMP2-CMD, 300 )
REM
999 REM End
"""

_PRG_HP_CORE = """\
REM --- FCU-HP-PRG ---
REM Heat pump — compressor and reversing valve control
REM CFG-RV-CLG: True = RV energized in cooling, False = RV energized in heating
REM
REM --- Compressor Command ---
IF HVAC-MODE = 2 AND ACT-RMT > ( CLG-SP + 1.0 ) THEN COMP-CMD = 1
IF HVAC-MODE = 3 AND ACT-RMT < ( HTG-SP - 1.0 ) THEN COMP-CMD = 1
IF HVAC-MODE <= 1 OR HVAC-MODE = 4 THEN COMP-CMD = 0
IF HVAC-MODE = 2 AND ACT-RMT < ( CLG-SP - 1.0 ) THEN COMP-CMD = 0
IF HVAC-MODE = 3 AND ACT-RMT > ( HTG-SP + 1.0 ) THEN COMP-CMD = 0
REM
REM --- Min On/Off Timer (3 minutes) ---
COMP-S/S = TIME-ON( COMP-CMD, 180 )
REM
REM --- Reversing Valve ---
REM CFG-RV-CLG=True: energize in cooling, de-energize in heating
REM CFG-RV-CLG=False: energize in heating, de-energize in cooling
IF CFG-RV-CLG THEN RV = ( HVAC-MODE = 2 )
IF NOT CFG-RV-CLG THEN RV = ( HVAC-MODE = 3 )
REM
REM --- DAT Limits ---
IF DAT-LL-ALARM AND HVAC-MODE = 2 THEN COMP-CMD = 0
IF DAT-HL-ALARM AND HVAC-MODE = 3 THEN COMP-CMD = 0
REM
999 REM End
"""

_PRG_HP_AUX = """\
REM --- FCU-AUX-PRG ---
REM Heat pump auxiliary electric heat
REM Enables when HP running but room temp still falling after delay
REM CFG-AUX-DELAY default 10 min (600 seconds)
REM
REM --- Aux Enable Logic ---
REM HP must be running in heating AND room temp below setpoint after delay
AUX-DEMAND = COMP-S/S AND ( HVAC-MODE = 3 ) AND ( ACT-RMT < ( HTG-SP - 2.0 ) )
AUX-HTR-S/S = TIME-ON( AUX-DEMAND, CFG-AUX-DELAY )
REM
REM --- Lockout: DAT > 87F ---
IF ACT-DAT > 87.0 THEN AUX-HTR-S/S = 0
REM
999 REM End
"""

_PRG_ECON_MOD = """\
REM --- FCU-ECON-PRG ---
REM Economizer — modulating OA damper
REM Enable when OAT < RAT and OAT < CFG-ECON-ENABLE-T
REM
REM --- Economizer Enable ---
ECON-ENABLE = ( NET-OAT < ACT-RMT ) AND ( NET-OAT < CFG-ECON-ENABLE-T ) AND OCC-CMD
REM
REM --- Damper Control ---
IF ECON-ENABLE AND HVAC-MODE = 2 THEN OAD = SLIDE( ACT-RMT - CLG-SP, 0.0, 3.0, 0.0, 100.0 )
IF NOT ECON-ENABLE OR HVAC-MODE <> 2 THEN OAD = 0.0
REM
999 REM End
"""

_PRG_ECON_FLT = """\
REM --- FCU-ECON-PRG ---
REM Economizer — floating point OA damper
REM Enable when OAT < RAT and OAT < CFG-ECON-ENABLE-T
REM
ECON-ENABLE = ( NET-OAT < ACT-RMT ) AND ( NET-OAT < CFG-ECON-ENABLE-T ) AND OCC-CMD
REM
IF ECON-ENABLE AND HVAC-MODE = 2 AND ACT-RMT > ( CLG-SP + 0.5 ) THEN OAD-O = 1 ELSE OAD-O = 0
IF ECON-ENABLE AND HVAC-MODE = 2 AND ACT-RMT < ( CLG-SP - 0.5 ) THEN OAD-C = 1 ELSE OAD-C = 0
IF NOT ECON-ENABLE OR HVAC-MODE <> 2 THEN OAD-C = 1
IF NOT ECON-ENABLE OR HVAC-MODE <> 2 THEN OAD-O = 0
REM
999 REM End
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Core Module — Always present in every FCU build
# ═══════════════════════════════════════════════════════════════════════════

def build_fcu_core():
    """FCU core — DAT, room temp, occupancy, mode determination"""
    return Module(
        id="fcu-core",
        name="FCU Core",
        category="core",
        description="Base FCU: DAT sensor, room temp, occupancy, HVAC mode, DAT limits",
        is_core=True,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250", "Discharge Air Temperature", "°F"),
            InputPoint(2, "FAN-STS", "BI", "Off/On", "Fan Status Feedback"),
            InputPoint(3, "RMT", "AI", "10K -40 ->250", "Room Temperature", "°F"),
        ],

        values=[
            # Sensors / calculated
            ValuePoint(1, "ACT-RMT",        "AV", 72.0,  "Actual Room Temperature",     "°F"),
            ValuePoint(2, "ACT-DAT",        "AV", 55.0,  "Actual Discharge Air Temp",   "°F"),
            ValuePoint(3, "CLG-SP",         "AV", 75.0,  "Cooling Setpoint",            "°F"),
            ValuePoint(4, "HTG-SP",         "AV", 70.0,  "Heating Setpoint",            "°F"),
            ValuePoint(5, "CFG-DAT-LL",     "AV", 45.0,  "DAT Low Limit",               "°F"),
            ValuePoint(6, "CFG-DAT-HL",     "AV", 95.0,  "DAT High Limit",              "°F"),
            ValuePoint(7, "CFG-UNOCC-DB",   "AV", 4.0,   "Unoccupied Deadband",         "°F"),
            ValuePoint(8, "NET-OAT",        "AV", 65.0,  "Network OAT",                 "°F"),
            # Occupancy
            ValuePoint(10, "NET-OCC-CMD",   "BV", True,  "Network Occupied Command"),
            ValuePoint(11, "OCC-CMD",       "BV", True,  "Occupancy Command"),
            ValuePoint(12, "USE-LOC-SCHD",  "BV", False, "Use Local Schedule"),
            # Status
            ValuePoint(13, "FAN-CMD",       "BV", False, "Fan Command"),
            ValuePoint(14, "FAN-FAIL",      "BV", False, "Fan Failure Alarm"),
            ValuePoint(15, "DAT-LL-ALARM",  "BV", False, "DAT Low Limit Alarm"),
            ValuePoint(16, "DAT-HL-ALARM",  "BV", False, "DAT High Limit Alarm"),
            # Modes
            ValuePoint(20, "HVAC-MODE",     "MV", "Off",
                       "HVAC Mode",
                       states={1: "Off", 2: "Cooling", 3: "Heating", 4: "Deadband"}),
        ],

        programs=[
            ProgramDef(1, "FCU-CFG-PRG", "PRG01-FCU-CFG.bas", _PRG_FCU_CFG, True,
                       "Configuration — sensors, network, mode determination",
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
providing fully automatic operation. The controller shall monitor discharge
air temperature and room temperature, and control fan speed and valve
position to maintain space temperature setpoint. Occupancy shall be
determined by network command or local schedule.""",
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
        description="Multi-speed fan — low/med/high relays",

        outputs=[
            OutputPoint(1, "FAN-LO", "BO", "Stop/Start", "Fan Low Speed"),
            OutputPoint(2, "FAN-MED", "BO", "Stop/Start", "Fan Medium Speed"),
            OutputPoint(3, "FAN-HI", "BO", "Stop/Start", "Fan High Speed"),
        ],

        programs=[
            ProgramDef(2, "FCU-FAN-PRG", "PRG02-FCU-FAN.bas", _PRG_FAN_MS, True,
                       "Fan control — multi-speed low/med/high", exec_order=2),
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
        description="VFD fan — modulating speed signal",

        outputs=[
            OutputPoint(1, "FAN-SPD", "AO", "0.0 ->100%", "Fan Speed Command", 0.0, 10.0),
        ],

        values=[
            ValuePoint(30, "CFG-FAN-MIN-SPD", "AV", 30.0, "Fan Minimum Speed", "%"),
        ],

        programs=[
            ProgramDef(2, "FCU-FAN-PRG", "PRG02-FCU-FAN.bas", _PRG_FAN_VFD, True,
                       "Fan control — VFD speed", exec_order=2),
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
        description="Chilled water cooling — modulating valve AO",

        outputs=[
            OutputPoint(4, "CHW-VLV", "AO", "0.0 ->100%", "CHW Valve", 2.0, 10.0),
        ],

        programs=[
            ProgramDef(3, "FCU-CLG-PRG", "PRG03-FCU-CLG.bas", _PRG_CHW_MOD, True,
                       "Cooling control — CHW modulating valve", exec_order=3),
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
        description="Chilled water cooling — floating point valve (open/close)",

        outputs=[
            OutputPoint(4, "CHW-VLV-O", "BO", "Stop/Start", "CHW Valve Open"),
            OutputPoint(5, "CHW-VLV-C", "BO", "Stop/Start", "CHW Valve Close"),
        ],

        programs=[
            ProgramDef(3, "FCU-CLG-PRG", "PRG03-FCU-CLG.bas", _PRG_CHW_FLT, True,
                       "Cooling control — CHW floating point valve", exec_order=3),
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
        description="Hot water heating — modulating valve AO",

        outputs=[
            OutputPoint(6, "HW-VLV", "AO", "0.0 ->100%", "HW Valve (reverse)", 10.0, 2.0, True),
        ],

        values=[
            ValuePoint(40, "HWS-OK", "BV", True, "Hot Water Available (network)"),
        ],

        programs=[
            ProgramDef(4, "FCU-HTG-PRG", "PRG04-FCU-HTG.bas", _PRG_HW_MOD, True,
                       "Heating control — HW modulating valve", exec_order=4),
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
        description="Hot water heating — floating point valve (open/close)",

        outputs=[
            OutputPoint(6, "HW-VLV-O", "BO", "Stop/Start", "HW Valve Open"),
            OutputPoint(7, "HW-VLV-C", "BO", "Stop/Start", "HW Valve Close"),
        ],

        values=[
            ValuePoint(40, "HWS-OK", "BV", True, "Hot Water Available (network)"),
        ],

        programs=[
            ProgramDef(4, "FCU-HTG-PRG", "PRG04-FCU-HTG.bas", _PRG_HW_FLT, True,
                       "Heating control — HW floating point valve", exec_order=4),
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
        description="Electric heating — single stage relay (also serves as backup with HW)",

        outputs=[
            OutputPoint(8, "ELEC-HTR-S/S", "BO", "Stop/Start", "Electric Heater"),
        ],

        programs=[
            ProgramDef(5, "FCU-ELEC-PRG", "PRG05-FCU-ELEC.bas", _PRG_ELEC_1, True,
                       "Heating control — 1 stage electric", exec_order=5),
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
        description="Electric heating — 2 stage relays (also serves as backup with HW)",

        outputs=[
            OutputPoint(8, "ELEC-HTR1-S/S", "BO", "Stop/Start", "Electric Heater Stage 1"),
            OutputPoint(9, "ELEC-HTR2-S/S", "BO", "Stop/Start", "Electric Heater Stage 2"),
        ],

        programs=[
            ProgramDef(5, "FCU-ELEC-PRG", "PRG05-FCU-ELEC.bas", _PRG_ELEC_2, True,
                       "Heating control — 2 stage electric", exec_order=5),
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
        description="2-pipe switchover — single modulating valve, reverse acting in heating",

        outputs=[
            OutputPoint(4, "VLV", "AO", "0.0 ->100%", "2-Pipe Valve", 2.0, 10.0),
        ],

        values=[
            ValuePoint(40, "HWS-OK",            "BV", False, "Hot Water Available (network)"),
            ValuePoint(41, "HTG-MODE",          "BV", False, "Heating Mode Active"),
            ValuePoint(42, "CFG-SWITCHOVER-T",  "AV", 55.0,  "Switchover Temperature", "°F"),
        ],

        programs=[
            ProgramDef(3, "FCU-2PIPE-PRG", "PRG03-FCU-2PIPE.bas", _PRG_2PIPE_MOD, True,
                       "2-pipe switchover — modulating valve", exec_order=3),
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
        description="2-pipe switchover — floating point valve, reverse acting in heating",

        outputs=[
            OutputPoint(4, "VLV-O", "BO", "Stop/Start", "2-Pipe Valve Open"),
            OutputPoint(5, "VLV-C", "BO", "Stop/Start", "2-Pipe Valve Close"),
        ],

        values=[
            ValuePoint(40, "HWS-OK",            "BV", False, "Hot Water Available (network)"),
            ValuePoint(41, "HTG-MODE",          "BV", False, "Heating Mode Active"),
            ValuePoint(42, "CFG-SWITCHOVER-T",  "AV", 55.0,  "Switchover Temperature", "°F"),
        ],

        programs=[
            ProgramDef(3, "FCU-2PIPE-PRG", "PRG03-FCU-2PIPE.bas", _PRG_2PIPE_FLT, True,
                       "2-pipe switchover — floating point valve", exec_order=3),
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
        description="DX cooling — single stage compressor with min on/off timer",

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
        description="DX cooling — two stage compressor with staging timers",

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
        description="Economizer OA damper — modulating AO",

        outputs=[
            OutputPoint(8, "OAD", "AO", "0.0 ->100%", "OA Damper", 2.0, 10.0),
        ],

        values=[
            ValuePoint(60, "CFG-ECON-ENABLE-T", "AV", 65.0, "Economizer Enable Temp", "°F"),
            ValuePoint(61, "ECON-ENABLE",       "BV", False, "Economizer Enabled"),
        ],

        programs=[
            ProgramDef(5, "FCU-ECON-PRG", "PRG05-FCU-ECON.bas", _PRG_ECON_MOD, True,
                       "Economizer — modulating OA damper", exec_order=5),
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
        description="Economizer OA damper — floating point (open/close)",

        outputs=[
            OutputPoint(8, "OAD-O", "BO", "Stop/Start", "OA Damper Open"),
            OutputPoint(9, "OAD-C", "BO", "Stop/Start", "OA Damper Close"),
        ],

        values=[
            ValuePoint(60, "CFG-ECON-ENABLE-T", "AV", 65.0, "Economizer Enable Temp", "°F"),
            ValuePoint(61, "ECON-ENABLE",       "BV", False, "Economizer Enabled"),
        ],

        programs=[
            ProgramDef(5, "FCU-ECON-PRG", "PRG05-FCU-ECON.bas", _PRG_ECON_FLT, True,
                       "Economizer — floating point OA damper", exec_order=5),
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
        description="Heat pump — reversing valve + compressor, CFG-RV-CLG config variable",

        outputs=[
            OutputPoint(4, "COMP-S/S", "BO", "Stop/Start", "Compressor Start/Stop"),
            OutputPoint(5, "RV", "BO", "Stop/Start", "Reversing Valve"),
        ],

        values=[
            ValuePoint(50, "COMP-CMD",    "BV", False, "Compressor Command"),
            ValuePoint(55, "CFG-RV-CLG",  "BV", True,  "RV Energized in Cooling (field config)"),
        ],

        programs=[
            ProgramDef(3, "FCU-HP-PRG", "PRG03-FCU-HP.bas", _PRG_HP_CORE, True,
                       "Heat pump — compressor + reversing valve", exec_order=3),
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
        description="Heat pump auxiliary electric heat — enables after delay when HP insufficient",

        outputs=[
            OutputPoint(6, "AUX-HTR-S/S", "BO", "Stop/Start", "Auxiliary Electric Heater"),
        ],

        values=[
            ValuePoint(56, "CFG-AUX-DELAY", "AV", 600.0, "Aux Heat Enable Delay", "Sec"),
            ValuePoint(57, "AUX-DEMAND",    "BV", False,  "Aux Heat Demand"),
        ],

        programs=[
            ProgramDef(4, "FCU-AUX-PRG", "PRG04-FCU-AUX.bas", _PRG_HP_AUX, True,
                       "Aux electric heat — delay after HP insufficiency", exec_order=4),
        ],

        requires=["fcu-hp-core"],
        conflicts=["fcu-hw-mod", "fcu-hw-flt", "fcu-elec-1", "fcu-elec-2"],
        mutually_exclusive_group="fcu-heating",
    )



# DAT Cascade Control Module (optional)

_PRG_DAT_CTRL = """\
REM --- FCU-DAT-CTRL-PRG ---
REM DAT cascade control - hard limits or full PID cascade
REM CFG-DAT-CASCADE: True = full PID, False = hard limits only
REM
REM --- Freeze Protection (always active) ---
IF ACT-DAT < CFG-DAT-FREEZE THEN FREEZE-TRIP = 1
IF ACT-DAT < CFG-DAT-FREEZE THEN HVAC-MODE = 1
IF ACT-DAT < CFG-DAT-FREEZE THEN FAN-CMD = 0
REM
REM --- Hard Limits Mode ---
IF NOT CFG-DAT-CASCADE THEN GOTO 200
REM Full cascade - DAT loop output limits valve demand
GOTO 999
REM
200 REM --- Hard Limit Clamping ---
IF HVAC-MODE = 3 AND ACT-DAT > CFG-DAT-HTG-MAX THEN DAT-HTG-CLAMP = 1 ELSE DAT-HTG-CLAMP = 0
IF HVAC-MODE = 2 AND ACT-DAT < CFG-DAT-CLG-MIN THEN DAT-CLG-CLAMP = 1 ELSE DAT-CLG-CLAMP = 0
REM
999 REM End
"""


def build_fcu_dat_ctrl():
    """DAT cascade control - hard limits or full PID"""
    return Module(
        id="fcu-dat-ctrl",
        name="FCU DAT Cascade Control",
        category="safety",
        description="DAT cascade control - configurable hard limits or full PID cascade mode",

        values=[
            ValuePoint(80, "CFG-DAT-CASCADE",  "BV", False, "DAT Cascade Mode (True=PID, False=limits)"),
            ValuePoint(81, "CFG-DAT-HTG-MAX",  "AV", 110.0, "Max DAT in Heating",         "deg.F"),
            ValuePoint(82, "CFG-DAT-CLG-MIN",  "AV", 52.0,  "Min DAT in Cooling",         "deg.F"),
            ValuePoint(83, "CFG-DAT-FREEZE",   "AV", 38.0,  "DAT Freeze Protection",      "deg.F"),
            ValuePoint(84, "DAT-HTG-CLAMP",    "BV", False, "Heating DAT Clamp Active"),
            ValuePoint(85, "DAT-CLG-CLAMP",    "BV", False, "Cooling DAT Clamp Active"),
            ValuePoint(86, "DAT-CORRECTION",   "AV", 100.0, "DAT Loop Correction Factor",  "%"),
        ],

        loops=[
            LoopDef(1, "DAT-LOOP", "ACT-DAT", "CFG-DAT-HTG-MAX", "DAT-CORRECTION",
                    p_band=15.0, integral=30.0, action="reverse",
                    description="DAT Cascade PID (active when CFG-DAT-CASCADE=True)"),
        ],

        programs=[
            ProgramDef(7, "FCU-DAT-CTRL-PRG", "PRG07-FCU-DAT-CTRL.bas", _PRG_DAT_CTRL, True,
                       "DAT cascade control - limits or PID", exec_order=7),
        ],

        requires=["fcu-core"],
    )



# ═══════════════════════════════════════════════════════════════════════════
#  Freezestat Module (optional)
# ═══════════════════════════════════════════════════════════════════════════

_PRG_FREEZESTAT = """\
REM --- FCU-FREEZE-PRG ---
REM Freezestat protection — trips on BI or DAT below CFG-FREEZE-T
REM Manual reset required via FREEZE-RESET BV
REM
REM --- Freezestat Trip Detection ---
IF FREEZE-STAT OR ( ACT-DAT < CFG-FREEZE-T ) THEN FREEZE-TRIP = 1
REM
REM --- Latch until manual reset ---
IF FREEZE-TRIP AND NOT FREEZE-RESET THEN FREEZE-LATCH = 1
IF FREEZE-RESET THEN FREEZE-LATCH = 0
IF FREEZE-RESET THEN FREEZE-TRIP = 0
IF FREEZE-RESET THEN FREEZE-RESET = 0
REM
REM --- Shutdown sequence when latched ---
IF FREEZE-LATCH THEN FAN-CMD = 0
IF FREEZE-LATCH THEN HVAC-MODE = 1
REM
REM --- Alarm ---
FREEZE-ALARM = FREEZE-LATCH
REM
999 REM End
"""


def build_fcu_freezestat():
    """Freezestat protection — trips on BI or low DAT"""
    return Module(
        id="fcu-freezestat",
        name="FCU Freezestat",
        category="safety",
        description="Freezestat BI + low DAT backup — latching shutdown, manual reset required",

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
            ProgramDef(6, "FCU-FREEZE-PRG", "PRG06-FCU-FREEZE.bas", _PRG_FREEZESTAT, True,
                       "Freezestat protection — latching shutdown", exec_order=6),
        ],

        requires=["fcu-core"],
    )
