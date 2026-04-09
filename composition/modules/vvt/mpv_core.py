"""
VVT MPV Core Module — vvt-mpv-core

Master RTU controller for VVT systems.
Controller: MACH-ProView LCD (or MPZ-88 alternate).

Provides: zone data aggregation via arrays, HVAC mode determination from
          zone votes, supply fan control, multi-stage heating/cooling,
          warmup mode, LCD status pages, alarm diagnostics.

Parameters:
  htg_stages (int): Number of heating stages (1 or 2)
  clg_stages (int): Number of cooling stages (1 or 2)
  zone_count (int): Number of VVT zones served

Factory reserved points (MACH-ProView LCD):
  AI7=Temperature, AI8=Humidity, AI10=CO2, BI9=Occupancy
  User IO avoids these instances.

Arrays:
  AY1 = VOTES (zone mode request votes)
  AY2 = RMTS (zone room temperatures)
  AY3 = RMT-DEVS (zone setpoint deviations)
  AY4 = ZN-OCC (zone occupancy states)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, ArrayDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
# Program source code — Control-BASIC
# ═══════════════════════════════════════════════════════════════════════════

_PRG01_NET_RMT = """\
REM --- NET-RMT-PRG ---
REM Reads RMTS array — calculates min/max/avg room temps
REM Loop bound = CFG-ZONE-COUNT
REM
REM --- Initialize ---
ZN-RMT-MIN = 200.0
ZN-RMT-MAX = 0.0
ZN-RMT-AVG = 0.0
ACT-ZONES = 0
REM
REM --- Loop Through Zones ---
FOR I = 1 TO CFG-ZONE-COUNT
  IF AY2[ I ] > 0.0 THEN ACT-ZONES = ACT-ZONES + 1
  IF AY2[ I ] > 0.0 AND AY2[ I ] < ZN-RMT-MIN THEN ZN-RMT-MIN = AY2[ I ]
  IF AY2[ I ] > ZN-RMT-MAX THEN ZN-RMT-MAX = AY2[ I ]
  ZN-RMT-AVG = ZN-RMT-AVG + AY2[ I ]
NEXT I
REM
REM --- Calculate Average ---
IF ACT-ZONES > 0 THEN ZN-RMT-AVG = ZN-RMT-AVG / ACT-ZONES
IF ACT-ZONES = 0 THEN ZN-RMT-AVG = 72.0
IF ACT-ZONES = 0 THEN ZN-RMT-MIN = 72.0
IF ACT-ZONES = 0 THEN ZN-RMT-MAX = 72.0
REM
"""

_PRG02_NET_VOTES = """\
REM --- NET-VOTES-PRG ---
REM Reads VOTES array — tallies heat/ESM/cool votes
REM Vote encoding: negative=heat, 0-9=ESM, 10+=cool
REM
REM --- Initialize ---
ZN-TOTAL-VOTES = 0
ZN-HEAT-VOTES = 0
ZN-ESM-VOTES = 0
ZN-COOL-VOTES = 0
REM
REM --- Loop Through Zones ---
FOR I = 1 TO CFG-ZONE-COUNT
  ZN-TOTAL-VOTES = ZN-TOTAL-VOTES + 1
  IF AY1[ I ] < 0.0 THEN ZN-HEAT-VOTES = ZN-HEAT-VOTES + 1
  IF AY1[ I ] >= 0.0 AND AY1[ I ] < 10.0 THEN ZN-ESM-VOTES = ZN-ESM-VOTES + 1
  IF AY1[ I ] >= 10.0 THEN ZN-COOL-VOTES = ZN-COOL-VOTES + 1
NEXT I
REM
REM --- Average Deviation ---
ZN-RMT-AVG-DEV = 0.0
FOR I = 1 TO CFG-ZONE-COUNT
  ZN-RMT-AVG-DEV = ZN-RMT-AVG-DEV + AY3[ I ]
NEXT I
IF CFG-ZONE-COUNT > 0 THEN ZN-RMT-AVG-DEV = ZN-RMT-AVG-DEV / CFG-ZONE-COUNT
REM
"""

_PRG03_NET_OCC = """\
REM --- NET-OCC-PRG ---
REM Reads ZN-OCC array — tallies occupancy requests by mode
REM OCC mode encoding: 1=Occ, 2=Bypass, 3=Standby, 4=Unocc, 5=NSB, 6=NSF
REM
REM --- Initialize ---
OCC-OCC-REQ = 0
OCC-BYP-REQ = 0
OCC-UNOCC-REQ = 0
OCC-NSB-REQ = 0
OCC-NSF-REQ = 0
REM
REM --- Loop Through Zones ---
FOR I = 1 TO CFG-ZONE-COUNT
  IF AY4[ I ] = 1 THEN OCC-OCC-REQ = OCC-OCC-REQ + 1
  IF AY4[ I ] = 2 THEN OCC-BYP-REQ = OCC-BYP-REQ + 1
  IF AY4[ I ] = 4 THEN OCC-UNOCC-REQ = OCC-UNOCC-REQ + 1
  IF AY4[ I ] = 5 THEN OCC-NSB-REQ = OCC-NSB-REQ + 1
  IF AY4[ I ] = 6 THEN OCC-NSF-REQ = OCC-NSF-REQ + 1
NEXT I
REM
"""

_PRG04_OCC_MODE = """\
REM --- OCC-MODE-PRG ---
REM Determines system occupancy mode from zone tallies
REM Uses master schedule + zone request override
REM
REM --- Master Schedule Base ---
IF OCC-MASTER-SCHED THEN OCC-MODE = 1
IF NOT OCC-MASTER-SCHED THEN OCC-MODE = 4
REM
REM --- Zone Occupied Requests Override ---
REM If enough zones request occupied, system goes occupied
IF OCC-OCC-REQ >= CFG-OCC-MIN-ENA-REQ THEN OCC-MODE = 1
IF OCC-BYP-REQ >= CFG-OCC-MIN-ENA-REQ THEN OCC-MODE = 1
REM
REM --- NSB/NSF Override ---
IF OCC-MODE = 4 AND OCC-NSB-REQ > 0 THEN OCC-MODE = 5
IF OCC-MODE = 4 AND OCC-NSF-REQ > 0 THEN OCC-MODE = 6
REM
REM --- Update Occupancy Display ---
IF OCC-MODE = 1 THEN VIEW-OCC-S = 1
IF OCC-MODE = 4 THEN VIEW-OCC-S = 0
REM
"""

_PRG05_HVAC_MODE = """\
REM --- HVAC-MODE-PRG ---
REM Determines system HVAC mode from vote tallies
REM Enforces CFG-HVAC-MODE-MIN-TIME before switching
REM 1=Ventilation, 2=Cool, 3=Reheat, 4=Heat, 5=Initialize
REM
REM --- Track Mode Active Time ---
MODE-ACTIVE-TIME = TIME-ON( HVAC-MODE = HVAC-MODE )
REM
REM --- Minimum Time Check ---
REM Don't switch modes until minimum time has elapsed
IF MODE-ACTIVE-TIME < CFG-HVAC-MODE-MIN-TIME THEN GOTO 999
REM
REM --- Determine New Mode ---
REM Priority: most votes wins
REM Heat if heating votes > cooling votes AND heat votes > ESM votes
IF ZN-HEAT-VOTES > ZN-COOL-VOTES AND ZN-HEAT-VOTES > ZN-ESM-VOTES THEN HVAC-MODE = 4
REM Cool if cooling votes > heating votes AND cool votes > ESM votes
IF ZN-COOL-VOTES > ZN-HEAT-VOTES AND ZN-COOL-VOTES > ZN-ESM-VOTES THEN HVAC-MODE = 2
REM ESM if ESM votes are highest (or tied)
IF ZN-ESM-VOTES >= ZN-HEAT-VOTES AND ZN-ESM-VOTES >= ZN-COOL-VOTES THEN HVAC-MODE = 1
REM
REM --- Unoccupied Override ---
IF OCC-MODE = 4 THEN HVAC-MODE = 1
REM
REM --- ESM Override ---
IF MODE-GLOBAL-ESM AND OCC-MODE <= 3 THEN HVAC-MODE = 1
REM
999 REM End
"""

_PRG06_SF = """\
REM --- SF-PRG ---
REM Supply fan start/stop with delay timer
REM
REM --- Fan Enable ---
REM Fan runs when occupied or bypass or standby or NSB/NSF
IF OCC-MODE <= 3 THEN SF-REQ = 2
IF OCC-MODE = 5 OR OCC-MODE = 6 THEN SF-REQ = 2
IF OCC-MODE = 4 THEN SF-REQ = 1
REM
REM --- Fan Start with Delay ---
IF SF-REQ >= 2 AND TIME-ON( SF-REQ >= 2 ) > CFG-SF-DELAY THEN START SF-CMD
IF SF-REQ = 1 THEN STOP SF-CMD
REM
REM --- Fan Status ---
IF SF-STS THEN VIEW-FAN-S = 3
IF NOT SF-STS THEN VIEW-FAN-S = 1
IF SF-CMD AND NOT SF-STS AND TIME-ON( SF-CMD AND NOT SF-STS ) > 0:01:00 THEN VIEW-FAN-S = 4
REM
"""

_PRG07_HTG = """\
REM --- HTG-PRG ---
REM Heating staging: OAT enable, DAT high limit, vote-based, min timers
REM Checks BYP-HTG-LOCKOUT before staging
REM
REM --- Heating Enable Check ---
REM OAT must be below heating enable setpoint
IF CFG-ACT-OAT > CFG-HTG-ENA-SP THEN HTG-ENABLE = 1
IF CFG-ACT-OAT > CFG-HTG-ENA-SP THEN GOTO 800
REM
REM --- Bypass Heating Lockout ---
IF BYP-HTG-LOCKOUT THEN HTG-ENABLE = 1
IF BYP-HTG-LOCKOUT THEN GOTO 800
REM
REM --- DAT High Limit ---
IF DAT > CFG-DAT-HI-LIMIT THEN HTG-ENABLE = 1
IF DAT > CFG-DAT-HI-LIMIT THEN GOTO 800
REM
REM --- HVAC Mode Check ---
IF HVAC-MODE <> 4 THEN HTG-ENABLE = 1
IF HVAC-MODE <> 4 THEN GOTO 800
REM
REM --- Heating Enabled ---
HTG-ENABLE = 2
REM
REM --- Fan Must Be Running ---
IF NOT SF-STS THEN GOTO 800
REM
REM --- Stage 1 ---
REM On: heating enabled and fan proven
REM Off: minimum on time expired and mode changed
IF HTG-DEMAND < 2 AND HVAC-MODE = 4 THEN HTG-DEMAND = 2
IF HTG-DEMAND >= 2 THEN START W1
IF HTG-DEMAND >= 2 AND TIME-ON( W1 ) > CFG-HTG-MIN-ON THEN GOTO 300
IF HVAC-MODE <> 4 AND TIME-ON( W1 ) > CFG-HTG-MIN-ON THEN STOP W1
IF HVAC-MODE <> 4 AND TIME-ON( W1 ) > CFG-HTG-MIN-ON THEN HTG-DEMAND = 1
GOTO 900
REM
REM --- Stage 2 ---
300 REM Stage 2 enable: OAT below stage 2 setpoint + interstage delay
IF CFG-ACT-OAT > CFG-HTG-STG02-ENA-SP THEN GOTO 900
IF TIME-ON( W1 ) < CFG-HTG-INSTG THEN GOTO 900
IF ZN-HEAT-VOTES > ( CFG-ZONE-COUNT / 2 ) THEN HTG-DEMAND = 3
IF HTG-DEMAND >= 3 THEN START W2
IF HVAC-MODE <> 4 THEN STOP W2
IF HVAC-MODE <> 4 THEN HTG-DEMAND = 2
GOTO 900
REM
REM --- All Off ---
800 REM Turn off all heating
STOP W1
STOP W2
HTG-DEMAND = 1
REM
900 REM End
"""

_PRG08_CLG = """\
REM --- CLG-PRG ---
REM Cooling staging: OAT enable, DAT low limit, vote-based, min timers
REM Checks BYP-CLG-LOCKOUT before staging
REM
REM --- Cooling Enable Check ---
REM OAT must be above cooling enable setpoint
IF CFG-ACT-OAT < CFG-CLG-ENA-SP THEN CLG-ENABLE = 1
IF CFG-ACT-OAT < CFG-CLG-ENA-SP THEN GOTO 800
REM
REM --- Bypass Cooling Lockout ---
IF BYP-CLG-LOCKOUT THEN CLG-ENABLE = 1
IF BYP-CLG-LOCKOUT THEN GOTO 800
REM
REM --- DAT Low Limit ---
IF DAT < CFG-DAT-LO-LIMIT THEN CLG-ENABLE = 1
IF DAT < CFG-DAT-LO-LIMIT THEN GOTO 800
REM
REM --- HVAC Mode Check ---
IF HVAC-MODE <> 2 THEN CLG-ENABLE = 1
IF HVAC-MODE <> 2 THEN GOTO 800
REM
REM --- Cooling Enabled ---
CLG-ENABLE = 2
REM
REM --- Fan Must Be Running ---
IF NOT SF-STS THEN GOTO 800
REM
REM --- Stage 1 ---
IF CLG-DEMAND < 2 AND HVAC-MODE = 2 THEN CLG-DEMAND = 2
IF CLG-DEMAND >= 2 THEN START Y1
IF CLG-DEMAND >= 2 AND TIME-ON( Y1 ) > CFG-CLG-MIN-ON THEN GOTO 300
IF HVAC-MODE <> 2 AND TIME-ON( Y1 ) > CFG-CLG-MIN-ON THEN STOP Y1
IF HVAC-MODE <> 2 AND TIME-ON( Y1 ) > CFG-CLG-MIN-ON THEN CLG-DEMAND = 1
GOTO 900
REM
REM --- Stage 2 ---
300 REM Stage 2: OAT above stage 2 setpoint + interstage delay
IF CFG-ACT-OAT < CFG-CLG-STG02-ENA-SP THEN GOTO 900
IF TIME-ON( Y1 ) < CFG-CLG-INSTG THEN GOTO 900
IF ZN-COOL-VOTES > ( CFG-ZONE-COUNT / 2 ) THEN CLG-DEMAND = 3
IF CLG-DEMAND >= 3 THEN START Y2
IF HVAC-MODE <> 2 THEN STOP Y2
IF HVAC-MODE <> 2 THEN CLG-DEMAND = 2
GOTO 900
REM
REM --- All Off ---
800 REM Turn off all cooling
STOP Y1
STOP Y2
CLG-DEMAND = 1
REM
900 REM End
"""

_PRG09_ALARMS = """\
REM --- ALARMS-PRG ---
REM Sensor failures, fan failure, DAT limits
REM DALARM for delayed annunciation
REM
REM --- Sensor Failures ---
IF SENSOR-ON( DAT ) THEN DALARM DAT, 0:05:00
IF SENSOR-OFF( DAT ) THEN DALARM DAT, 0:05:00
IF SENSOR-ON( RAT ) THEN DALARM RAT, 0:05:00
IF SENSOR-OFF( RAT ) THEN DALARM RAT, 0:05:00
IF SENSOR-ON( OAT ) THEN DALARM OAT, 0:05:00
IF SENSOR-OFF( OAT ) THEN DALARM OAT, 0:05:00
REM
REM --- Fan Failure ---
REM Fan commanded on but no status after 60 seconds
IF SF-CMD AND NOT SF-STS AND TIME-ON( SF-CMD AND NOT SF-STS ) > 0:01:00 THEN ALARM = 1
REM
REM --- DAT Limits ---
IF DAT > CFG-DAT-HI-LIMIT THEN ALARM = 2
IF DAT < CFG-DAT-LO-LIMIT THEN ALARM = 3
REM
"""

_PRG10_MPV_STATUS = """\
REM --- MPV-STATUS-PRG ---
REM Updates ProView LCD display status MVs
REM VIEW-SYSTEM-S: 1=Off, 2=Starting, 3=Running, 4=Alarm
REM VIEW-FAN-S: 1=Off, 2=Starting, 3=Running, 4=Alarm
REM
REM --- System Status ---
IF OCC-MODE = 4 THEN VIEW-SYSTEM-S = 1
IF OCC-MODE <= 3 AND NOT SF-STS THEN VIEW-SYSTEM-S = 2
IF OCC-MODE <= 3 AND SF-STS THEN VIEW-SYSTEM-S = 3
REM
"""

_PRG11_WU = """\
REM --- WU-PRG ---
REM Warmup mode: if OAT below heating enable and first occupied transition
REM Sets MODE-GLOBAL-ESM = False during warmup, BV23 WU-MODE active
REM
REM --- Warmup Check ---
REM Only on transition to occupied
IF+ OCC-MODE <= 3 THEN GOTO 100
GOTO 999
REM
100 REM Check if warmup needed
IF CFG-ACT-OAT > CFG-HTG-ENA-SP THEN GOTO 999
REM Warmup active for configurable period
MODE-GLOBAL-ESM = 0
REM Warmup runs until zone temps reach setpoints
IF ZN-RMT-AVG > 68.0 THEN MODE-GLOBAL-ESM = 1
REM
999 REM End
"""

_PRG12_PAGE1 = """\
REM --- MPV-PAGE1-PRG ---
REM LCD Page 1: System status — fan/mode/OAT/DAT
REM Updates ProView LCD display fields
REM
REM Page 1 displays:
REM   Line 1: System status (VIEW-SYSTEM-S)
REM   Line 2: Fan status (VIEW-FAN-S)
REM   Line 3: HVAC Mode
REM   Line 4: OAT / DAT
REM
"""

_PRG13_PAGE2 = """\
REM --- MPV-PAGE2-PRG ---
REM LCD Page 2: Zone summary — min/max/avg temps, zone count
REM
REM Page 2 displays:
REM   Line 1: Zone Count (ACT-ZONES / CFG-ZONE-COUNT)
REM   Line 2: Avg Room Temp (ZN-RMT-AVG)
REM   Line 3: Min Room Temp (ZN-RMT-MIN)
REM   Line 4: Max Room Temp (ZN-RMT-MAX)
REM
"""

_PRG14_PAGE3 = """\
REM --- MPV-PAGE3-PRG ---
REM LCD Page 3: Vote tallies — heat/ESM/cool counts
REM
REM Page 3 displays:
REM   Line 1: Heat Votes (ZN-HEAT-VOTES)
REM   Line 2: ESM Votes (ZN-ESM-VOTES)
REM   Line 3: Cool Votes (ZN-COOL-VOTES)
REM   Line 4: Total Votes (ZN-TOTAL-VOTES)
REM
"""

_PRG15_PAGE4 = """\
REM --- MPV-PAGE4-PRG ---
REM LCD Page 4: Staging status — active heat/cool stages
REM
REM Page 4 displays:
REM   Line 1: Heating Enable (HTG-ENABLE)
REM   Line 2: Heating Demand (HTG-DEMAND)
REM   Line 3: Cooling Enable (CLG-ENABLE)
REM   Line 4: Cooling Demand (CLG-DEMAND)
REM
"""


def build(htg_stages=2, clg_stages=2, zone_count=8):
    """Build VVT MPV core module with parameterized stages and zone count.

    Args:
        htg_stages: Number of heating stages (1 or 2)
        clg_stages: Number of cooling stages (1 or 2)
        zone_count: Number of VVT zones served
    """

    # ── Physical IO ──
    inputs = [
        InputPoint(1, "SF-STS", "BI", "Off/On",
                   "Supply Fan Status (current switch)", ""),
        InputPoint(2, "DAT",    "AI", "10K -40 ->250",
                   "Discharge Air Temperature", "deg.F"),
        InputPoint(3, "RAT",    "AI", "10K -40 ->250",
                   "Return Air Temperature", "deg.F"),
        InputPoint(4, "OAT",    "AI", "10K -40 ->250",
                   "Outside Air Temperature", "deg.F"),
        # Factory reserved (MPV LCD)
        InputPoint(7, "TEMPERATURE", "AI", "10K -40 ->250",
                   "Onboard LCD Temp Sensor (factory)", "deg.F", module="FACTORY"),
        InputPoint(8, "HUMIDITY",    "AI", "0.0 ->100%",
                   "Onboard LCD Humidity Sensor (factory)", "%", module="FACTORY"),
        InputPoint(10, "CO2",        "AI", "0 ->5000 PPM",
                    "Onboard LCD CO2 Sensor (factory)", "PPM", module="FACTORY"),
        InputPoint(9, "OCCUPANCY",   "BI", "Off/On",
                   "Onboard PIR Occupancy (factory)", "", module="FACTORY"),
    ]

    outputs = [
        OutputPoint(1, "SF-CMD", "BO", "Off/On",
                    "Supply Fan Start/Stop", units=""),
        OutputPoint(2, "W1",     "BO", "Off/On",
                    "Heat Stage 1", units=""),
    ]
    if htg_stages >= 2:
        outputs.append(
            OutputPoint(3, "W2", "BO", "Off/On",
                        "Heat Stage 2", units=""))
    outputs.append(
        OutputPoint(4, "Y1", "BO", "Off/On",
                    "Cool Stage 1", units=""))
    if clg_stages >= 2:
        outputs.append(
            OutputPoint(5, "Y2", "BO", "Off/On",
                        "Cool Stage 2", units=""))

    # ── Arrays ──
    arrays = [
        ArrayDef(1, "VOTES",    zone_count, "Zone mode request votes"),
        ArrayDef(2, "RMTS",     zone_count, "Zone room temperatures"),
        ArrayDef(3, "RMT-DEVS", zone_count, "Zone setpoint deviations"),
        ArrayDef(4, "ZN-OCC",   zone_count, "Zone occupancy states"),
    ]

    # ── Values ──
    values = [
        # Zone aggregation
        ValuePoint(1,  "ACT-ZONES",         "AV", 0.0,   "Number of Communicating Zones",       ""),
        ValuePoint(2,  "ZN-RMT-MIN",        "AV", 200.0, "Minimum Zone Room Temp",              "deg.F"),
        ValuePoint(3,  "ZN-RMT-MAX",        "AV", 0.0,   "Maximum Zone Room Temp",              "deg.F"),
        ValuePoint(4,  "ZN-RMT-AVG",        "AV", 72.0,  "Average Zone Room Temp",              "deg.F"),
        ValuePoint(5,  "ZN-RMT-AVG-DEV",    "AV", 0.0,   "Average Zone Setpoint Deviation",     "deg.F"),

        # Vote tallies
        ValuePoint(7,  "ZN-TOTAL-VOTES",    "AV", 0.0,   "Total Votes from Zones",              ""),
        ValuePoint(8,  "ZN-HEAT-VOTES",     "AV", 0.0,   "Heating Votes",                       ""),
        ValuePoint(9,  "ZN-ESM-VOTES",      "AV", 0.0,   "Energy Savings Mode Votes",           ""),
        ValuePoint(10, "ZN-COOL-VOTES",     "AV", 0.0,   "Cooling Votes",                       ""),

        # Published setpoints
        ValuePoint(14, "SP-LO",             "AV", 55.0,  "Room Setpoint Low Limit (to zones)",  "deg.F"),
        ValuePoint(15, "SP-HI",             "AV", 85.0,  "Room Setpoint High Limit (to zones)", "deg.F"),

        # Occupancy tallies
        ValuePoint(16, "OCC-OCC-REQ",       "AV", 0.0,   "Occupied Requests Tally",             ""),
        ValuePoint(17, "OCC-BYP-REQ",       "AV", 0.0,   "Bypass Requests Tally",               ""),
        ValuePoint(18, "OCC-UNOCC-REQ",     "AV", 0.0,   "Unoccupied Requests Tally",           ""),
        ValuePoint(19, "OCC-NSB-REQ",       "AV", 0.0,   "Night Setback Requests Tally",        ""),
        ValuePoint(20, "OCC-NSF-REQ",       "AV", 0.0,   "Night Setforward Requests Tally",     ""),

        # Mode timing
        ValuePoint(24, "MODE-ACTIVE-TIME",  "AV", 0.0,   "Current HVAC Mode Active Time",       "Min."),

        # Configuration
        ValuePoint(36, "CFG-OCC-MIN-ENA-REQ",    "AV", 1.0,    "Min Occupied Requests to Enable",    ""),
        ValuePoint(37, "CFG-HVAC-MODE-MIN-TIME",  "AV", 16.67,  "Min Time Before HVAC Mode Change",   "Min."),
        ValuePoint(38, "CFG-SF-DELAY",            "AV", 8.33,   "Supply Fan On/Off Delay",            "Min."),
        ValuePoint(39, "CFG-DAT-HI-LIMIT",       "AV", 140.0,  "DAT High Limit Lockout",             "deg.F"),
        ValuePoint(40, "CFG-DAT-LO-LIMIT",       "AV", 45.0,   "DAT Low Limit Lockout",              "deg.F"),
        ValuePoint(42, "CFG-ACT-OAT",            "AV", 72.0,   "Active OAT (local or network)",      "deg.F"),
        ValuePoint(43, "CFG-HTG-ENA-SP",          "AV", 55.0,   "OAT Heating Enable Setpoint",        "deg.F"),
        ValuePoint(44, "CFG-HTG-STG02-ENA-SP",    "AV", 45.0,   "OAT Heating Stage 2 Enable",         "deg.F"),
        ValuePoint(45, "CFG-ZONE-COUNT",          "AV", float(zone_count), "Zone Count (set at gen)",  ""),
        ValuePoint(46, "CFG-HTG-MIN-ON",          "AV", 8.33,   "Heating Minimum On Time",            "Min."),
        ValuePoint(47, "CFG-HTG-MIN-OFF",         "AV", 8.33,   "Heating Minimum Off Time",           "Min."),
        ValuePoint(48, "CFG-HTG-INSTG",           "AV", 8.33,   "Heating Interstage Delay",           "Min."),
        ValuePoint(49, "CFG-CLG-ENA-SP",          "AV", 65.0,   "OAT Cooling Enable Setpoint",        "deg.F"),
        ValuePoint(50, "CFG-CLG-STG02-ENA-SP",    "AV", 70.0,   "OAT Cooling Stage 2 Enable",         "deg.F"),
        ValuePoint(51, "CFG-CLG-MIN-ON",          "AV", 8.33,   "Cooling Minimum On Time",            "Min."),
        ValuePoint(52, "CFG-CLG-MIN-OFF",         "AV", 8.33,   "Cooling Minimum Off Time",           "Min."),
        ValuePoint(53, "CFG-CLG-INSTG",           "AV", 8.33,   "Cooling Interstage Delay",           "Min."),

        # BV values
        ValuePoint(20, "BYP-HTG-LOCKOUT",         "BV", False, "Bypass Heating Lockout (from bypass)"),
        ValuePoint(21, "BYP-CLG-LOCKOUT",         "BV", False, "Bypass Cooling Lockout (from bypass)"),
        ValuePoint(23, "MODE-GLOBAL-ESM",          "BV", True,  "Global Energy Savings Mode"),
        ValuePoint(25, "OCC-MASTER-SCHED",         "BV", False, "Master Schedule Occupancy Command"),
        ValuePoint(34, "CFG-OCC-NSB-ENABLE",       "BV", False, "Enable Night Setback"),
        ValuePoint(35, "CFG-OCC-NSF-ENABLE",       "BV", False, "Enable Night Setforward"),
        ValuePoint(41, "CFG-NET-OAT",              "BV", False, "Use Network OAT vs Local AI4"),
        ValuePoint(56, "VIEW-OCC-S",               "BV", False, "MPV Occupancy Display Status"),

        # MV values
        ValuePoint(12, "OCC-MODE",      "MV", "Unoccupied",
                   "System Occupancy Mode",
                   states={1: "Occupied", 2: "Bypass", 3: "Standby",
                           4: "Unoccupied", 5: "NSB", 6: "NSF"}),
        ValuePoint(13, "HVAC-MODE",     "MV", "Ventilation",
                   "System HVAC Mode",
                   states={1: "Ventilation", 2: "Cool", 3: "Reheat",
                           4: "Heat", 5: "Initialize"}),
        ValuePoint(26, "SF-REQ",        "MV", "Off",
                   "Supply Fan Request",
                   states={1: "Off", 2: "Low", 3: "High"}),
        ValuePoint(28, "HTG-ENABLE",    "MV", "Off",
                   "Heating Enable",
                   states={1: "Off", 2: "Low", 3: "High"}),
        ValuePoint(29, "HTG-DEMAND",    "MV", "Off",
                   "Heating Demand",
                   states={1: "Off", 2: "Low", 3: "High"}),
        ValuePoint(31, "CLG-ENABLE",    "MV", "Off",
                   "Cooling Enable",
                   states={1: "Off", 2: "Low", 3: "High"}),
        ValuePoint(32, "CLG-DEMAND",    "MV", "Off",
                   "Cooling Demand",
                   states={1: "Off", 2: "Low", 3: "High"}),
        ValuePoint(54, "VIEW-SYSTEM-S", "MV", "Running",
                   "MPV System Status Display",
                   states={1: "Off", 2: "Starting", 3: "Running", 4: "Alarm"}),
        ValuePoint(55, "VIEW-FAN-S",    "MV", "Alarm",
                   "MPV Fan Status Display",
                   states={1: "Off", 2: "Starting", 3: "Running", 4: "Alarm"}),
    ]

    programs = [
        ProgramDef(1,  "NET-RMT-PRG",        "PRG01-NET-RMT.bas",        _PRG01_NET_RMT, True,
                   "Reads RMTS array — min/max/avg room temps", exec_order=1),
        ProgramDef(2,  "NET-VOTES-PRG",       "PRG02-NET-VOTES.bas",      _PRG02_NET_VOTES, True,
                   "Reads VOTES array — tallies heat/ESM/cool votes", exec_order=2),
        ProgramDef(3,  "NET-OCC-PRG",         "PRG03-NET-OCC.bas",        _PRG03_NET_OCC, True,
                   "Reads ZN-OCC array — tallies occupancy requests", exec_order=3),
        ProgramDef(4,  "OCC-MODE-PRG",        "PRG04-OCC-MODE.bas",       _PRG04_OCC_MODE, True,
                   "System occupancy mode from zone tallies", exec_order=4),
        ProgramDef(5,  "HVAC-MODE-PRG",       "PRG05-HVAC-MODE.bas",      _PRG05_HVAC_MODE, True,
                   "System HVAC mode from vote tallies", exec_order=5),
        ProgramDef(6,  "SF-PRG",              "PRG06-SF.bas",             _PRG06_SF, True,
                   "Supply fan start/stop with delay", exec_order=6),
        ProgramDef(7,  "HTG-PRG",             "PRG07-HTG.bas",            _PRG07_HTG, True,
                   "Two-stage heating: OAT lockout, DAT limit, vote staging", exec_order=7),
        ProgramDef(8,  "CLG-PRG",             "PRG08-CLG.bas",            _PRG08_CLG, True,
                   "Two-stage cooling: OAT lockout, DAT limit, vote staging", exec_order=8),
        ProgramDef(9,  "ALARMS-PRG",          "PRG09-ALARMS.bas",         _PRG09_ALARMS, True,
                   "Sensor failures, fan failure, DAT limits", exec_order=9),
        ProgramDef(10, "MPV-STATUS-PRG",      "PRG10-MPV-STATUS.bas",     _PRG10_MPV_STATUS, True,
                   "LCD display status MVs", exec_order=10),
        ProgramDef(11, "WU-PRG",              "PRG11-WU.bas",             _PRG11_WU, True,
                   "Warmup mode logic", exec_order=11),
        ProgramDef(12, "MPV-PAGE1-PRG",       "PRG12-MPV-PAGE1.bas",      _PRG12_PAGE1, True,
                   "LCD page 1: system status", exec_order=12),
        ProgramDef(13, "MPV-PAGE2-PRG",       "PRG13-MPV-PAGE2.bas",      _PRG13_PAGE2, True,
                   "LCD page 2: zone summary", exec_order=13),
        ProgramDef(14, "MPV-PAGE3-PRG",       "PRG14-MPV-PAGE3.bas",      _PRG14_PAGE3, True,
                   "LCD page 3: vote tallies", exec_order=14),
        ProgramDef(15, "MPV-PAGE4-PRG",       "PRG15-MPV-PAGE4.bas",      _PRG15_PAGE4, True,
                   "LCD page 4: staging status", exec_order=15),
    ]

    return Module(
        id="vvt-mpv-core",
        name="VVT MPV Core",
        category="core",
        description=f"VVT MPV RTU master: {htg_stages}H/{clg_stages}C stages, {zone_count} zones, arrays, LCD pages",
        is_core=True,

        inputs=inputs,
        outputs=outputs,
        values=values,
        loops=[],  # No PID loops on MPV — staging is direct on/off
        arrays=arrays,
        programs=programs,

        schedules=[
            ScheduleDef(1, "NORMAL-SCHED", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10,
                        "Master occupancy schedule"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM",
                           "System status: fan, mode, temps, zone counts"),
            SystemGroupDef("{device-name}-ZONE-DATA",
                           "Zone aggregation: min/max/avg temps, vote tallies"),
            SystemGroupDef("{device-name}-STAGING",
                           "Heating/cooling staging: enable, demand, stages"),
            SystemGroupDef("{device-name}-CONFIG",
                           "Configuration: OAT setpoints, timers, zone count"),
        ],

        soo_paragraph=f"""The VVT master RTU controller (MACH-ProView LCD) shall aggregate data from
{zone_count} VVT zone controllers via BACnet arrays. Four arrays shall be maintained:
VOTES for HVAC mode requests, RMTS for room temperatures, RMT-DEVS for setpoint
deviations, and ZN-OCC for zone occupancy states.

The controller shall tally zone votes to determine the system HVAC mode. Heating
votes (negative values) indicate heating demand. Cooling votes (values above 10)
indicate cooling demand. ESM votes (0-9) indicate zones are satisfied. The mode
with the most votes shall be selected, subject to a configurable minimum hold time.

Supply fan control shall include a configurable start/stop delay timer. Fan failure
shall be alarmed if the fan is commanded on but status is not proven within 60 seconds.

Heating staging shall provide up to {htg_stages} stage(s) of heat with OAT enable
lockout, DAT high limit safety, bypass heating lockout from the bypass controller,
minimum on/off timers, and interstage delay. Cooling staging shall provide up to
{clg_stages} stage(s) with equivalent protections.

The ProView LCD shall display four status pages: system status, zone summary,
vote tallies, and staging status. Warmup mode shall be activated on the first
occupied transition when OAT is below the heating enable setpoint.""",
    )
