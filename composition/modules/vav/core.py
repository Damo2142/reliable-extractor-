"""
VAV Core Module — Always present in every VAV build.

Provides: occupancy modes (6), HVAC modes (5), room temp setpoints,
          flow setpoint calculation, damper override modes (8),
          network variables from parent AHU, array populate to parent AHU,
          fault/alarm diagnostics, local schedule.

Based on SBS tested VAV (1213.json) — 49 AVs, 24 BVs, 5 MVs, 4 LOOPs.

Factory reserved points (AV1-5, AV7, AI4, AI5, BI6, BO8, BV6, MO7)
come from the RC-FLEXair blank file and are NOT defined here.

Parent AHU instance mappings (NET-VARS-PRG):
  {parent}AV1   → local AV38  NET-OAT
  {parent}AV14  → local AV42  CFG-RMT-SP-LO
  {parent}AV15  → local AV43  CFG-RMT-SP-HI
  {parent}AV21  → local AV19  NET-SAT
  {parent}AV98  → local AV21  NET-DSP
  {parent}AV155 → local AV76  HWST
  {parent}BV13  → local BV61  AHU-WU-MODE
  {parent}BV24  → local BV78  AHU-SET-LIMITS
  {parent}BV26  → local BV20  NET-OCC-CMD
  {parent}BV151 → local BV75  HWS-OK
  {parent}BV178 → local BV74  AHU-OK
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, TrendDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
# Program source code — Control-BASIC
# ═══════════════════════════════════════════════════════════════════════════

_PRG01_CFG = """\
REM --- CFG-PRG ---
REM Configuration: setpoint limits, airflow limits, deviation calc
REM Runs first every scan to set up all calculated values
REM
REM *** {parent} = BACnet device of the AHU serving this VAV zone ***
REM *** Set {parent} to the associated AHU device ID at commissioning ***
REM
REM --- Room Temp Setpoint Limits ---
REM Apply limits from AHU if SET-LIMITS active
IF AHU-SET-LIMITS THEN RMT-SP = LIMIT( RMT-SP, CFG-RMT-SP-LO, CFG-RMT-SP-HI )
REM
REM --- Active Setpoints ---
REM Cooling setpoint = operator SP + deadband
REM Heating setpoint = operator SP - deadband
ACT-RMT-SP-DB = DB-MTPLR * CFG-RMT-SP-DB
RMT-SP-CLG = RMT-SP + ACT-RMT-SP-DB
RMT-SP-HTG = RMT-SP - ACT-RMT-SP-DB
REM
REM --- Airflow Limits ---
REM Copy config values to active setpoints
FLO-MIN-HTG-SP = CFG-MIN-HTG-FLO
FLO-MIN-CLG-SP = CFG-MIN-CLG-FLO
FLO-MAX-HTG-SP = CFG-MAX-HTG-FLO
FLO-MAX-CLG-SP = CFG-MAX-CLG-FLO
REM
REM --- Room Temp Deviation ---
RMT-DEV = ACT-RMT - RMT-SP
REM
REM --- Cooling Demand ---
REM 0% at setpoint, 100% at setpoint + p-band
IF ACT-RMT > RMT-SP-CLG THEN CLG-DMD = SLIDE( ACT-RMT, RMT-SP-CLG, RMT-SP-CLG + 4.0, 0.0, 100.0 )
IF ACT-RMT <= RMT-SP-CLG THEN CLG-DMD = 0.0
"""

_PRG02_MODE = """\
REM --- MODE-PRG ---
REM Occupancy modes (6) + HVAC modes (5) + zone state
REM
REM --- Occupancy Mode ---
REM 1=Occupied, 2=Bypass, 3=Standby, 4=Unoccupied, 5=NSB, 6=NSF
IF OCC-CMD THEN OCC-MODE = 1
IF NOT OCC-CMD THEN OCC-MODE = 4
IF BYPASS THEN OCC-MODE = 2
IF NSB-MODE THEN OCC-MODE = 5
IF NSF-MODE THEN OCC-MODE = 6
REM
REM --- Occupancy Command ---
REM Network command or local schedule
IF CFG-SCHED-LOCAL THEN OCC-CMD = LOCAL-SCHED
IF NOT CFG-SCHED-LOCAL THEN OCC-CMD = NET-OCC-CMD
REM
REM --- Night Setback ---
REM Room temp below NSB setpoint while unoccupied
IF OCC-MODE = 4 THEN NSB-MODE = ( ACT-RMT < CFG-NSB-SP )
IF OCC-MODE <> 4 THEN NSB-MODE = 0
REM
REM --- Night Set-Forward ---
REM Room temp above NSF setpoint while unoccupied
IF OCC-MODE = 4 THEN NSF-MODE = ( ACT-RMT > CFG-NSF-SP )
IF OCC-MODE <> 4 THEN NSF-MODE = 0
REM
REM --- HVAC Mode ---
REM 1=Ventilation, 2=Cool, 3=Reheat, 4=Heat, 5=Initialize
REM Based on room temp vs setpoints
IF ACT-RMT > RMT-SP-CLG THEN HVAC-MODE = 2
IF ACT-RMT < RMT-SP-HTG THEN HVAC-MODE = 3
IF ( ACT-RMT >= RMT-SP-HTG ) AND ( ACT-RMT <= RMT-SP-CLG ) THEN HVAC-MODE = 1
REM Warmup mode from AHU overrides to Heat
IF AHU-WU-MODE THEN HVAC-MODE = 4
REM
REM --- Zone State ---
REM 1=Unoccupied, 2=Hot, 3=Warm, 4=Normal, 5=Cool, 6=Cold
ZONE-STATE = 4
IF RMT-DEV > 3.0 THEN ZONE-STATE = 2
IF RMT-DEV > 1.0 AND RMT-DEV <= 3.0 THEN ZONE-STATE = 3
IF RMT-DEV < -3.0 THEN ZONE-STATE = 6
IF RMT-DEV < -1.0 AND RMT-DEV >= -3.0 THEN ZONE-STATE = 5
IF OCC-MODE = 4 THEN ZONE-STATE = 1
REM
REM --- Display Icons ---
HEAT-ICON = ( HVAC-MODE = 3 ) OR ( HVAC-MODE = 4 )
COOL-ICON = ( HVAC-MODE = 2 )
"""

_PRG03_FLO_CTRL = """\
REM --- FLO-CTRL-PRG ---
REM Flow setpoint calculation, damper command, 8-mode override.
REM Flat precedence — default to auto, then apply overrides last-write-wins.
REM
REM MV28 FLO/DMP-CTRL-OVR: 1=Auto, 2=Min, 3=Max, 4=Manual SP,
REM                       5=Flow SP %, 6=Manual Pos, 7=Close, 8=Open
REM
REM --- Default: Auto mode flow setpoint based on HVAC mode ---
REM Cooling: demand drives flow between min and max cooling
IF HVAC-MODE = 2 THEN FLO-SP = SLIDE( CLG-DMD , 0.0 , 100.0 , FLO-MIN-CLG-SP , FLO-MAX-CLG-SP )
REM Ventilation: minimum cooling flow
IF HVAC-MODE = 1 THEN FLO-SP = FLO-MIN-CLG-SP
REM Reheat: minimum heating flow (dual max — heat at min first)
IF HVAC-MODE = 3 THEN FLO-SP = FLO-MIN-HTG-SP
REM Heat: increase flow up to max heating flow as demand increases
IF HVAC-MODE = 4 THEN FLO-SP = SLIDE( CLG-DMD , 0.0 , 100.0 , FLO-MIN-HTG-SP , FLO-MAX-HTG-SP )
REM Unoccupied: unoccupied flow setpoint
IF OCC-MODE = 4 THEN FLO-SP = FLO-UNOCC-SP
REM Standby: fraction of min cooling flow
IF OCC-MODE = 3 THEN FLO-SP = FLO-MIN-CLG-SP * SB-FLO-MTPLR
REM
REM --- Manual Overrides (modes 2-5 force a specific FLO-SP) ---
IF FLO/DMP-CTRL-OVR = 2 THEN FLO-SP = FLO-MIN-CLG-SP
IF FLO/DMP-CTRL-OVR = 3 THEN FLO-SP = FLO-MAX-CLG-SP
IF FLO/DMP-CTRL-OVR = 4 THEN FLO-SP = FLO/DMP-SP-OVR
IF FLO/DMP-CTRL-OVR = 5 THEN FLO-SP = FLO-MAX-CLG-SP * FLO/DMP-SP-OVR / 100.0
REM
REM --- Apply Flow Setpoint (default path: enable factory flow control) ---
BV6 = 1
AV5 = FLO-SP
REM
REM --- Manual Position Modes (6/7/8) bypass flow control entirely ---
IF FLO/DMP-CTRL-OVR >= 6 THEN BV6 = 0
"""

_PRG07_FAULT = """\
REM --- FAULT-PRG ---
REM Airflow, damper, room temp, reheat diagnostic alarms
REM Uses DALARM for delayed alarm annunciation
REM
REM --- High Room Temp ---
HIGH-RMT = ( ACT-RMT > ( RMT-SP + 5.0 ) ) AND OCC-CMD
REM
REM --- Low Room Temp ---
LOW-RMT = ( ACT-RMT < ( RMT-SP - 5.0 ) ) AND OCC-CMD
REM
REM --- High Airflow ---
HIGH-AIRFLOW = ( FLO > ( FLO-MAX-CLG-SP * 1.2 ) ) AND OCC-CMD
REM
REM --- Low Airflow ---
LOW-AIRFLOW = ( FLO < ( FLO-MIN-CLG-SP * 0.5 ) ) AND OCC-CMD AND ( FLO-MIN-CLG-SP > 0 )
REM
REM --- High DAT ---
HIGH-DAT = ( DAT > RH-MAX-DAT )
REM
REM --- Low DAT ---
LOW-DAT = ( DAT < 45.0 ) AND OCC-CMD
REM
REM --- Fault Counter ---
IF RESET-DIAG THEN FAULT-COUNTER = 0
IF RESET-DIAG THEN RESET-DIAG = 0
IF HIGH-RMT OR LOW-RMT OR HIGH-AIRFLOW OR LOW-AIRFLOW THEN FAULT-COUNTER = FAULT-COUNTER + 1
REM
REM --- Fault Counter Reset ---
IF FLT-CNTR-RESET THEN FAULT-COUNTER = 0
IF FLT-CNTR-RESET THEN FLT-CNTR-RESET = 0
"""

_PRG08_AHU_ARRAYS = """\
REM --- AHU-ARRAYS-PRG ---
REM Array populate — writes zone data to parent AHU.
REM {parent} = BACnet device of the AHU serving this VAV zone.
REM Auto-calculates array index from device MAC address.
REM AY1=ACT-RMT, AY2=CLG-DMD, AY3=HTG-REQ, AY4=DMP-POS,
REM AY5=NSB-MODE, AY6=NSF-MODE, AY7=BYPASS, AY8=RMT-DEV,
REM AY9=zone-live validity flag (1 = box is assigned).
REM Always writes zone data to the parent AHU arrays.
REM Gated only on a valid index (Y >= 1) so a failed device-ID read
REM (Y = 0) can't default into slot 1 and clobber that box.
REM
REM --- Calculate Array Index from Device ID ---
Y = DEV4194303:1042 MOD 1000
REM
REM --- Write Zone Data to Parent Arrays (only on a valid index) ---
IF Y >= 1 THEN {parent}AY1[ Y ] = ACT-RMT
IF Y >= 1 THEN {parent}AY2[ Y ] = CLG-DMD
IF Y >= 1 THEN {parent}AY3[ Y ] = HTG-REQ
IF Y >= 1 THEN {parent}AY4[ Y ] = DMP-POS
IF Y >= 1 THEN {parent}AY5[ Y ] = NSB-MODE
IF Y >= 1 THEN {parent}AY6[ Y ] = NSF-MODE
IF Y >= 1 THEN {parent}AY7[ Y ] = BYPASS
IF Y >= 1 THEN {parent}AY8[ Y ] = RMT-DEV
REM
REM --- Write Zone Validity Flag ---
IF Y >= 1 THEN {parent}AY9[ Y ] = 1
"""

_PRG09_REQS = """\
REM --- REQS-PRG ---
REM Zone requests — heating/cooling/static demand
REM Calculates request flags for AHU reset optimization
REM
REM --- Heating Request ---
REM Request heating when in reheat or heat mode
HTG-REQ = ( HVAC-MODE = 3 ) OR ( HVAC-MODE = 4 )
REM
REM --- Bypass Request ---
REM Request bypass when unoccupied and room temp outside limits
BYPASS = 0
IF OCC-MODE = 4 AND ( ACT-RMT < CFG-NSB-SP ) THEN BYPASS = 1
IF OCC-MODE = 4 AND ( ACT-RMT > CFG-NSF-SP ) THEN BYPASS = 1
"""

_PRG10_NET_VARS = """\
REM --- NET-VARS-PRG ---
REM Read network data from parent AHU controller
REM {parent} = BACnet device of the AHU serving this VAV zone
REM Set {parent} to the associated AHU device ID at commissioning
REM
REM --- Outside Air Temp ---
NET-OAT = {parent}AV1
REM
REM --- Supply Air Temp ---
NET-SAT = {parent}AV21
REM
REM --- Duct Static Pressure ---
NET-DSP = {parent}AV98
REM
REM --- HW Supply Temp ---
HWST = {parent}AV155
REM
REM --- Setpoint Limits ---
CFG-RMT-SP-LO = {parent}AV14
CFG-RMT-SP-HI = {parent}AV15
REM
REM --- Occupancy Command ---
NET-OCC-CMD = {parent}BV26
REM
REM --- AHU Warmup Mode ---
AHU-WU-MODE = {parent}BV13
REM
REM --- System Status Flags ---
HWS-OK = {parent}BV151
AHU-OK = {parent}BV178
REM
REM --- Set Limits Flag ---
AHU-SET-LIMITS = {parent}BV24
"""


def build():
    return Module(
        id="vav-core",
        name="VAV Core",
        category="core",
        description="Base VAV: occupancy modes, HVAC modes, flow control, network vars, array populate, faults",
        is_core=True,

        # DAT mandatory on ALL VAV families (SBS standard)
        # Reheat modules also define DAT — assembler deduplicates by name
        inputs=[
            InputPoint(1, "DAT",     "AI", "10K -40 ->250",
                       "Discharge Air Temperature", "°F"),
            InputPoint(4, "VP",      "AI", "0.0 ->1.0 in.wc.",
                       "Velocity Pressure (factory)", "in.wc.", module="FACTORY"),
            InputPoint(5, "DMP-POS", "AI", "0 ->100%",
                       "Damper Position (factory)", "%", module="FACTORY"),
            InputPoint(6, "DMP@END", "BI", "Off/On",
                       "Damper at End of Travel (factory)", "", module="FACTORY"),
        ],

        # Factory reserved outputs — display only
        outputs=[
            OutputPoint(7, "DMP-ACT", "MO", "",
                        "Damper Actuator Motor Output (factory)", min_v=0, max_v=0, units="", module="FACTORY"),
            OutputPoint(8, "CW-CLS",  "BO", "Off/On",
                        "CW to Close (factory)", units="", module="FACTORY"),
        ],

        values=[
            # ── Factory reserved AV (display only — from RC-FLEXair blank) ──
            ValuePoint(1,  "DIAM",             "AV", 8.0,   "Duct Diameter (factory)",            "in.",    module="FACTORY"),
            ValuePoint(2,  "FLO-CAL",          "AV", 0.0,   "Flow Calibration (factory)",         "CFM",   module="FACTORY"),
            ValuePoint(3,  "CAL-K",            "AV", 1.0,   "K-Factor (factory)",                 "",      module="FACTORY"),
            ValuePoint(4,  "FLO",              "AV", 0.0,   "Volumetric Flow (factory)",          "CFM",   module="FACTORY"),
            ValuePoint(5,  "FLO-SP",           "AV", 120.0, "Flow Setpoint (factory)",            "CFM",   module="FACTORY"),
            ValuePoint(7,  "FLO-DB",           "AV", 12.0,  "Flow Deadband (factory)",            "CFM",   module="FACTORY"),
            # Factory reserved BV/MO (display only)
            ValuePoint(6,  "FLO-CTRL",         "BV", True,  "Flow Control Enable (factory)",               module="FACTORY"),

            # ── Room temperature and setpoints ──
            # NOTE: No AV "DAT" here. DAT is the live AI1 sensor (defined above);
            # all VAV programs reference DAT directly from AI1. A second AV named
            # "DAT" would collide with the sensor name and never be written.
            ValuePoint(9,  "ACT-RMT",          "AV", 72.0,  "Actual Room Temperature",            "deg.F"),
            ValuePoint(10, "OCC-RMT-SP",       "AV", 72.0,  "Occupied Room Temp Setpoint",        "deg.F"),
            ValuePoint(11, "RMT-SP",           "AV", 72.0,  "Operator Room Temp Setpoint",        "deg.F"),
            ValuePoint(12, "RMT-SP-HTG",       "AV", 71.0,  "Heating Setpoint (calculated)",      "deg.F"),
            ValuePoint(13, "RMT-SP-CLG",       "AV", 74.0,  "Cooling Setpoint (calculated)",      "deg.F"),
            ValuePoint(14, "RMT-DEV",          "AV", 0.0,   "Room Temp Deviation",                "deg.F"),
            ValuePoint(15, "DB-MTPLR",         "AV", 1.5,   "Deadband Multiplier",                ""),

            # ── Network values from parent AHU ──
            ValuePoint(19, "NET-SAT",          "AV", 55.0,  "Network Supply Air Temp",            "deg.F"),
            ValuePoint(21, "NET-DSP",          "AV", 1.5,   "Network Duct Static Pressure",       "in.wc."),
            ValuePoint(38, "NET-OAT",          "AV", 72.0,  "Network Outside Air Temp",           "deg.F"),
            ValuePoint(76, "HWST",             "AV", 0.0,   "HW Supply Temp (from network)",      "deg.F"),

            # ── Flow setpoints ──
            ValuePoint(29, "FLO/DMP-SP-OVR",   "AV", 0.0,   "Flow/Damper Override Setpoint",      ""),
            ValuePoint(30, "FLO-MIN-HTG-SP",   "AV", 100.0, "Min Heating Airflow SP",             "CFM"),
            ValuePoint(31, "FLO-MIN-CLG-SP",   "AV", 200.0, "Min Cooling Airflow SP",             "CFM"),
            ValuePoint(32, "FLO-MAX-HTG-SP",   "AV", 300.0, "Max Heating Airflow SP",             "CFM"),
            ValuePoint(33, "FLO-MAX-CLG-SP",   "AV", 900.0, "Max Cooling Airflow SP",             "CFM"),
            ValuePoint(35, "FLO-UNOCC-SP",     "AV", 0.0,   "Unoccupied Flow Setpoint",           "CFM"),

            # ── Config setpoints ──
            ValuePoint(42, "CFG-RMT-SP-LO",    "AV", 68.0,  "Setpoint Low Limit",                 "deg.F"),
            ValuePoint(43, "CFG-RMT-SP-HI",    "AV", 76.0,  "Setpoint High Limit",                "deg.F"),
            ValuePoint(44, "ACT-RMT-SP-DB",    "AV", 1.0,   "Active Setpoint Deadband",           "deg.F"),
            ValuePoint(45, "CFG-NSB-SP",       "AV", 64.0,  "Night Setback Setpoint",             "deg.F"),
            ValuePoint(46, "CFG-NSF-SP",       "AV", 80.0,  "Night Setforward Setpoint",          "deg.F"),
            ValuePoint(52, "CFG-BYPASS-SP",    "AV", 120.0, "Bypass Timer Setpoint",              "Min."),
            ValuePoint(60, "CFG-RMT-SP-DB",    "AV", 1.0,   "Room Temp SP Deadband",              "deg.F"),
            ValuePoint(62, "SB-FLO-MTPLR",     "AV", 0.15,  "Standby Flow Multiplier",            ""),

            # ── Airflow config ──
            ValuePoint(55, "MIN-HTG-FLO",      "AV", 100.0, "Config Min Heating Flow",            "CFM"),
            ValuePoint(56, "MIN-CLG-FLO",      "AV", 200.0, "Config Min Cooling Flow",            "CFM"),
            ValuePoint(63, "CFG-MIN-HTG-FLO",  "AV", 100.0, "Config Min HTG Flow",                "CFM"),
            ValuePoint(64, "CFG-MIN-CLG-FLO",  "AV", 200.0, "Config Min CLG Flow",                "CFM"),
            ValuePoint(65, "CFG-MAX-HTG-FLO",  "AV", 300.0, "Config Max HTG Flow",                "CFM"),
            ValuePoint(66, "CFG-MAX-CLG-FLO",  "AV", 900.0, "Config Max CLG Flow",                "CFM"),

            # ── Demand / diagnostics ──
            ValuePoint(81, "CLG-DMD",          "AV", 0.0,   "Cooling Demand",                     "%"),
            ValuePoint(100,"RH-MAX-DAT",       "AV", 90.0,  "Reheat Max Discharge Air Temp",      "deg.F"),
            ValuePoint(110,"FAULT-COUNTER",    "AV", 0.0,   "Diagnostic Fault Counter",           ""),

            # ── Binary values ──
            ValuePoint(20, "NET-OCC-CMD",      "BV", True,  "Network Occupied Command"),
            ValuePoint(23, "OCC-CMD",          "BV", True,  "Occupancy Command"),
            ValuePoint(24, "BYPASS",           "BV", False, "Bypass Mode Active"),
            ValuePoint(40, "NSB-MODE",         "BV", False, "Night Setback Mode"),
            ValuePoint(41, "NSF-MODE",         "BV", False, "Night Setforward Mode"),
            ValuePoint(51, "CFG-SCHED-LOCAL",  "BV", False, "Use Local Schedule"),
            ValuePoint(58, "HEAT-ICON",        "BV", False, "Heating Icon (display)"),
            ValuePoint(59, "COOL-ICON",        "BV", False, "Cooling Icon (display)"),
            ValuePoint(61, "AHU-WU-MODE",      "BV", False, "AHU Warmup Mode (from network)"),
            ValuePoint(74, "AHU-OK",           "BV", True,  "AHU System OK (from network)"),
            ValuePoint(75, "HWS-OK",           "BV", True,  "HW System OK (from network)"),
            ValuePoint(78, "AHU-SET-LIMITS",   "BV", False, "AHU Set Limits (from network)"),
            ValuePoint(82, "HTG-REQ",          "BV", False, "Heating Request"),
            ValuePoint(91, "HIGH-RMT",         "BV", False, "High Room Temp Alarm"),
            ValuePoint(92, "LOW-RMT",          "BV", False, "Low Room Temp Alarm"),
            ValuePoint(93, "HIGH-AIRFLOW",     "BV", False, "High Airflow Alarm"),
            ValuePoint(94, "LOW-AIRFLOW",      "BV", False, "Low Airflow Alarm"),
            ValuePoint(95, "HIGH-DAT",         "BV", False, "High DAT Alarm"),
            ValuePoint(96, "LOW-DAT",          "BV", False, "Low DAT Alarm"),
            ValuePoint(98, "RESET-DIAG",       "BV", False, "Reset Diagnostics"),
            ValuePoint(109,"FLT-CNTR-RESET",   "BV", False, "Fault Counter Reset"),

            # ── Multi-state values ──
            ValuePoint(16, "OCC-MODE",         "MV", "Unoccupied",
                       "Occupancy Mode",
                       states={1: "Occupied", 2: "Bypass", 3: "Standby",
                               4: "Unoccupied", 5: "NSB", 6: "NSF"}),
            ValuePoint(17, "HVAC-MODE",        "MV", "Ventilation",
                       "HVAC Mode",
                       states={1: "Ventilation", 2: "Cool", 3: "Reheat",
                               4: "Heat", 5: "Initialize"}),
            ValuePoint(18, "ZONE-STATE",       "MV", "Normal",
                       "Zone State",
                       states={1: "Unoccupied", 2: "Hot", 3: "Warm",
                               4: "Normal", 5: "Cool", 6: "Cold"}),
            ValuePoint(28, "FLO/DMP-CTRL-OVR", "MV", "Auto",
                       "Flow/Damper Override",
                       states={1: "Auto", 2: "Min Flow", 3: "Max Flow",
                               4: "Manual SP", 5: "Flow SP %",
                               6: "Manual Pos", 7: "Close", 8: "Open"}),
            ValuePoint(72, "ZONE",             "MV", "Zone1",
                       "Zone Assignment (legacy array)",
                       states={1: "Zone1", 2: "Zone2", 3: "Zone3",
                               4: "Zone4", 5: "Zone5", 6: "Zone6",
                               7: "Zone7", 8: "Zone8"}),
        ],

        loops=[
            # Only FLO-CTRL-LOOP in core — firmware handles damper PID internally
            # RH-LOOP and DAT-LOOP belong in reheat modules (added with reheat)
            # DMP-LOOP only needed for field-installed external actuators
            LoopDef(1, "FLO-CTRL-LOOP", "ACT-RMT", "RMT-SP-CLG", "FLO-SP",
                    p_band=2.0, integral=4.0, action="direct",
                    description="Temperature to airflow — action dynamically switched by MODE"),
        ],

        programs=[
            ProgramDef(1, "CFG-PRG", "PRG01-CFG.bas", _PRG01_CFG, True,
                       "Configuration: setpoint limits, airflow limits, deviation calc",
                       exec_order=1),
            ProgramDef(2, "MODE-PRG", "PRG02-MODE.bas", _PRG02_MODE, True,
                       "Occupancy modes (6) + HVAC modes (5) + zone state",
                       exec_order=2),
            ProgramDef(3, "FLO-CTRL-PRG", "PRG03-FLO-CTRL.bas", _PRG03_FLO_CTRL, True,
                       "Flow setpoint calc, damper command, 8-mode override",
                       exec_order=3),
            ProgramDef(7, "FAULT-PRG", "PRG07-FAULT.bas", _PRG07_FAULT, True,
                       "Airflow, damper, room temp, reheat alarms",
                       exec_order=7),
            ProgramDef(8, "AHU-ARRAYS-PRG", "PRG08-AHU-ARRAYS.bas", _PRG08_AHU_ARRAYS, True,
                       "Array populate — writes zone data to parent AHU",
                       exec_order=8),
            ProgramDef(9, "REQS-PRG", "PRG09-REQS.bas", _PRG09_REQS, True,
                       "Zone requests — heating/cooling/static demand",
                       exec_order=9),
            ProgramDef(10, "NET-VARS-PRG", "PRG10-NET-VARS.bas", _PRG10_NET_VARS, True,
                       "Network variables — reads data from parent AHU",
                       exec_order=10),
        ],

        schedules=[
            ScheduleDef(1, "LOCAL-SCHED", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10,
                        "Local occupancy schedule"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM",
                           "Status overview: schedule, modes, airflow, damper, temps"),
            SystemGroupDef("{device-name}-CONFIG-SP",
                           "Temperature setpoint configuration"),
            SystemGroupDef("{device-name}-CONFIG-AIRFLOW",
                           "Airflow setpoint configuration"),
            SystemGroupDef("{device-name}-SEQUENCE",
                           "Control sequence detail"),
        ],

        soo_paragraph="""The VAV terminal unit shall be equipped with a direct digital control (DDC)
system providing fully automatic operation. The DDC controller (RC-FLEXair)
shall include factory-integrated differential pressure sensor and damper actuator
for airflow measurement and control.

Occupancy modes shall include Occupied, Bypass, Standby, Unoccupied, Night Setback,
and Night Set-Forward. Mode transitions shall be based on network occupancy commands
from the parent AHU or local schedule override.

HVAC modes shall include Ventilation, Cooling, Reheat, Heating, and Initialization.
The controller shall automatically select the appropriate mode based on room temperature
relative to heating and cooling setpoints.

Airflow control shall maintain volumetric flow setpoints calculated from zone demand.
Cooling mode: flow modulates from minimum to maximum based on cooling demand.
Heating mode (dual maximum): reheat activates at minimum flow first, then airflow
increases to maximum heating flow as demand increases.

The controller shall read network variables from the parent AHU including outside
air temperature, supply air temperature, duct static pressure, HW supply temperature,
occupancy commands, warmup mode, and system status flags.

Zone data shall be written to parent AHU arrays for reset optimization including
room temperature, cooling demand, heating requests, damper position, and setpoint
deviation.""",
    )
