"""
VVT Zone Core Module — vvt-zone-core

Always present in every VVT zone controller build.
Controller: RC-FLEXair (same hardware as VAV).

Provides: occupancy modes (6), HVAC mode voting, damper control via MO7,
          network reads from MPV ({parent}), array writes to MPV (AY1-4),
          room temp setpoint calculation, alarm diagnostics.

AI1 = DAT is ALWAYS present — non-negotiable SBS standard.

Key differences from VAV core:
  - Parent is MPV (MACH-ProView), not AHU (MPS)
  - Zone-to-parent uses array writes (AY1-4), not direct AV writes
  - HVAC mode determined by zone voting, not AHU
  - Damper control via MO7 OPEN/CLOSE/IDLE, not firmware flow control
  - No flow setpoint logic — damper modulates to room temp directly
  - Staggered array writes using DEV4194303:1042 for timing offset

Factory reserved points (from RC-FLEXair blank — NOT defined here):
  AI4=VP, AI5=DMP-POS, BI6=DMP@END, BO8=CW-CLS, BV6=FLO-CTRL, MO7=DMP
  AV1=DIAM, AV2=FLO-CAL, AV3=CAL-K, AV4=FLO, AV5=FLO-SP, AV7=FLO-DB

Parent MPV instance mappings (NET-PRG):
  {parent}DEV vendor-id  → local AV53  NET-RTU-STATUS
  {parent}BI1            → local BV54  NET-RTU-SF-S
  {parent}AI2            → local AV55  NET-SAT
  {parent}BV23           → local BV56  NET-GLOBAL-ESM
  {parent}BV25           → local BV57  NET-SCHED
  {parent}MV13           → local MV58  NET-HVAC-MODE
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
# Program source code — Control-BASIC
# ═══════════════════════════════════════════════════════════════════════════

_PRG01_NET = """\
REM --- NET-PRG ---
REM Network communication: read from MPV, write to MPV arrays
REM {parent} = BACnet device ID of the MPV RTU serving this zone
REM Set {parent} to the MPV device instance at commissioning
REM
REM --- Read RTU Status ---
REM Vendor ID property check — confirms RTU is communicating
NET-RTU-STATUS = {parent}DEV4194303:121
REM
REM --- Read Supply Fan Status ---
NET-RTU-SF-S = {parent}BI1
REM
REM --- Read Supply Air Temp ---
NET-SAT = {parent}AI2
REM
REM --- Read Global ESM Flag ---
NET-GLOBAL-ESM = {parent}BV23
REM
REM --- Read Occupancy Command ---
NET-SCHED = {parent}BV25
REM
REM --- Read HVAC Mode ---
NET-HVAC-MODE = {parent}MV13
REM
REM --- Write Zone Data to MPV Arrays ---
REM Staggered timing: use MAC address for unique offset per zone
REM Write every 60 seconds to avoid BACnet congestion
REM AY1 = mode votes, AY2 = room temps, AY3 = deviations, AY4 = occ mode
REM
{parent}AY1[ CFG-ZONE-ADDR ] = HVAC-MODE-VOTE
{parent}AY2[ CFG-ZONE-ADDR ] = ACT-RMT
{parent}AY3[ CFG-ZONE-ADDR ] = RMT-SP-DEV
{parent}AY4[ CFG-ZONE-ADDR ] = OCC-MODE
REM
"""

_PRG02_CFG = """\
REM --- CFG-PRG ---
REM Configuration: setpoint limits, heating/cooling SP calc, deviation
REM
REM --- Setpoint Limits ---
RMT-SP = LIMIT( RMT-SP, CFG-RMT-SP-LO-LIMIT, CFG-RMT-SP-HI-LIMIT )
REM
REM --- Heating and Cooling Setpoints ---
REM Deadband splits around operator setpoint
RMT-HTG-SP = RMT-SP - ( CFG-RMT-SP-DB / 2.0 )
RMT-CLG-SP = RMT-SP + ( CFG-RMT-SP-DB / 2.0 )
REM
REM --- Room Temp Deviation ---
RMT-SP-DEV = ACT-RMT - ACT-RMT-SP
REM
REM --- Active Setpoint Based on Mode ---
REM Occupied: use operator setpoint
REM NSB: use night setback setpoint
REM NSF: use night setforward setpoint
IF OCC-MODE <= 3 THEN ACT-RMT-SP = RMT-SP
IF OCC-MODE = 5 THEN ACT-RMT-SP = CFG-RMT-NSB-SP
IF OCC-MODE = 6 THEN ACT-RMT-SP = CFG-RMT-NSF-SP
IF OCC-MODE = 4 THEN ACT-RMT-SP = RMT-SP
REM
REM --- Damper Limits ---
CFG-DMP-MIN = LIMIT( CFG-DMP-MIN, 0.0, 100.0 )
CFG-DMP-MAX = LIMIT( CFG-DMP-MAX, 0.0, 100.0 )
CFG-DMP-FAIL = LIMIT( CFG-DMP-FAIL, 0.0, 100.0 )
CFG-DMP-ESM = LIMIT( CFG-DMP-ESM, 0.0, 100.0 )
REM
"""

_PRG03_OCC = """\
REM --- OCC-PRG ---
REM Occupancy mode (6-mode): schedule, bypass, NSB, NSF
REM 1=Occupied, 2=Bypass, 3=Standby, 4=Unoccupied, 5=NSB, 6=NSF
REM
REM --- Schedule Source ---
REM Local schedule or network command from MPV
IF CFG-SCHED-LOCAL THEN OCC-CMD = LOCAL-SCHED
IF NOT CFG-SCHED-LOCAL THEN OCC-CMD = NET-SCHED
REM
REM --- Base Mode from Schedule ---
IF OCC-CMD THEN OCC-MODE = 1
IF NOT OCC-CMD THEN OCC-MODE = 4
REM
REM --- Motion Sensor Bypass ---
REM If motion detected while unoccupied, enter bypass mode
REM Bypass timer runs for CFG-BYPASS-SP minutes then returns to unoccupied
IF OCC-MODE = 4 AND OCC-MOTION THEN OCC-BYPASS = 1
IF OCC-BYPASS THEN OCC-MODE = 2
IF OCC-BYPASS AND TIME-ON( OCC-BYPASS ) > CFG-BYPASS-SP THEN OCC-BYPASS = 0
IF OCC-MODE = 1 THEN OCC-BYPASS = 0
REM
REM --- Standby Mode ---
REM If occupied but no motion for extended period, enter standby
IF OCC-MODE = 1 AND NOT OCC-MOTION THEN OCC-STANDBY = TIME-ON( NOT OCC-MOTION ) > CFG-BYPASS-SP
IF OCC-STANDBY AND OCC-MODE = 1 THEN OCC-MODE = 3
IF OCC-MOTION THEN OCC-STANDBY = 0
REM
REM --- Night Setback ---
REM Room temp below NSB setpoint while unoccupied
IF OCC-MODE = 4 THEN NSB-ACT = SWITCH( ACT-RMT, CFG-RMT-NSB-SP, 1.0 )
IF OCC-MODE <> 4 THEN NSB-ACT = 0
IF NSB-ACT THEN OCC-MODE = 5
REM
REM --- Night Set-Forward ---
REM Room temp above NSF setpoint while unoccupied
IF OCC-MODE = 4 THEN NSF-ACT = SWITCH( ACT-RMT, CFG-RMT-NSF-SP, 1.0 )
IF OCC-MODE <> 4 THEN NSF-ACT = 0
IF NSF-ACT THEN OCC-MODE = 6
REM
"""

_PRG04_DMP = """\
REM --- DMP-PRG ---
REM Damper control via MO7 (motor output)
REM OPEN/CLOSE/IDLE with deadband for modulating position
REM
REM --- Disable Firmware Flow Control ---
REM VVT uses room temp control, not flow control
STOP BV6
BV6 = 0
REM
REM --- RTU Communication Check ---
REM If RTU not communicating, go to fail-safe position
IF NET-RTU-STATUS < 30.0 THEN DMP-REQ = CFG-DMP-FAIL
IF NET-RTU-STATUS < 30.0 THEN GOTO 500
REM
REM --- Supply Fan Status Check ---
REM If supply fan not running, go to fail-safe position
IF NOT NET-RTU-SF-S THEN DMP-REQ = CFG-DMP-FAIL
IF NOT NET-RTU-SF-S THEN GOTO 500
REM
REM --- Unoccupied Mode ---
REM Go to minimum position when unoccupied
IF OCC-MODE = 4 THEN DMP-REQ = CFG-DMP-MIN
IF OCC-MODE = 4 THEN GOTO 500
REM
REM --- ESM Mode ---
REM Energy savings mode — go to ESM position
IF NET-GLOBAL-ESM AND OCC-MODE <= 3 THEN DMP-REQ = CFG-DMP-ESM
IF NET-GLOBAL-ESM AND OCC-MODE <= 3 THEN GOTO 500
REM
REM --- Normal Damper Control ---
REM Use DMP-LOOP output based on room temp vs setpoint
REM Loop action dynamically switched by heating/cooling mode:
REM   Cooling (HVAC-MODE-LOCAL=2): Direct — temp rises, damper opens
REM   Heating (HVAC-MODE-LOCAL=3,4): Reverse — temp drops, damper opens
REM
REM Detect local heating need from SAT vs room temp
IF NET-SAT > ACT-RMT THEN HVAC-MODE-LOCAL = 4
IF NET-SAT <= ACT-RMT THEN HVAC-MODE-LOCAL = 2
IF ABS( NET-SAT - ACT-RMT ) < 2.0 THEN HVAC-MODE-LOCAL = 1
REM
REM Calculate damper request from loop output
DMP-REQ = DMP-LOOP
DMP-REQ = LIMIT( DMP-REQ, CFG-DMP-MIN, CFG-DMP-MAX )
REM
REM --- MO7 Modulation ---
500 REM Drive MO7 to requested position
REM Use deadband to prevent hunting
IF DMP-POS < ( DMP-REQ - CFG-DMP-DB ) THEN START MO7:OPEN
IF DMP-POS > ( DMP-REQ + CFG-DMP-DB ) THEN START MO7:CLOSE
IF ABS( DMP-POS - DMP-REQ ) <= CFG-DMP-DB THEN START MO7:IDLE
REM
"""

_PRG05_MODE = """\
REM --- MODE-PRG ---
REM HVAC mode voting — calculates vote value for MPV
REM Vote encoding: negative=heat, 0=neutral, 1-9=ESM, 10+=cool
REM
REM --- Base Deviation ---
REM How far room temp is from setpoint
REM Positive = above setpoint (cooling need)
REM Negative = below setpoint (heating need)
REM
REM --- Cooling Vote ---
REM Room temp above cooling setpoint — vote for cooling
IF ACT-RMT > RMT-CLG-SP THEN GOTO 100
REM
REM --- Heating Vote ---
REM Room temp below heating setpoint — vote for heating
IF ACT-RMT < RMT-HTG-SP THEN GOTO 200
REM
REM --- ESM / Neutral Vote ---
REM Room temp in deadband — energy savings mode
HVAC-MODE-VOTE = CFG-VOTE-ESM-NORMAL
GOTO 900
REM
REM --- Cooling Votes ---
100 REM Normal cooling: deviation within VOTE-NORMAL-DEV
IF ( ACT-RMT - RMT-CLG-SP ) <= VOTE-NORMAL-DEV THEN HVAC-MODE-VOTE = 10.0 + CFG-VOTE-CLG-NORMAL
IF ( ACT-RMT - RMT-CLG-SP ) > VOTE-NORMAL-DEV THEN HVAC-MODE-VOTE = 10.0 + CFG-VOTE-CLG-NORMAL + CFG-VOTE-CLG-DEMAND
REM Demand cooling: deviation beyond VOTE-DEMAND-DEV
IF ( ACT-RMT - RMT-CLG-SP ) > VOTE-DEMAND-DEV THEN HVAC-MODE-VOTE = 20.0
GOTO 900
REM
REM --- Heating Votes ---
200 REM Normal heating: deviation within VOTE-NORMAL-DEV
IF ( RMT-HTG-SP - ACT-RMT ) <= VOTE-NORMAL-DEV THEN HVAC-MODE-VOTE = -1.0 * CFG-VOTE-HTG-NORMAL
IF ( RMT-HTG-SP - ACT-RMT ) > VOTE-NORMAL-DEV THEN HVAC-MODE-VOTE = -1.0 * ( CFG-VOTE-HTG-NORMAL + CFG-VOTE-HTG-DEMAND )
REM Demand heating: deviation beyond VOTE-DEMAND-DEV
IF ( RMT-HTG-SP - ACT-RMT ) > VOTE-DEMAND-DEV THEN HVAC-MODE-VOTE = -10.0
GOTO 900
REM
REM --- NSB/NSF Override ---
900 REM Night setback forces heating vote, night setforward forces cooling vote
IF OCC-MODE = 5 THEN HVAC-MODE-VOTE = -1.0
IF OCC-MODE = 6 THEN HVAC-MODE-VOTE = 11.0
REM
"""

_PRG06_ALARM = """\
REM --- ALARM-PRG ---
REM Zone alarms: damper deviation, high/low room temp
REM Only alarm when occupied (OCC-MODE < 4)
REM 30-minute guard after entering occupied mode
REM
REM --- Occupied Guard Timer ---
REM Don't alarm for 30 minutes after going occupied
IF OCC-MODE >= 4 THEN GOTO 999
IF TIME-ON( OCC-MODE < 4 ) < 0:30:00 THEN GOTO 999
REM
REM --- High Room Temp Alarm ---
IF ACT-RMT > ( RMT-CLG-SP + 3.0 ) THEN ALARM = 1
REM
REM --- Low Room Temp Alarm ---
IF ACT-RMT < ( RMT-HTG-SP - 3.0 ) THEN ALARM = 2
REM
REM --- Damper Position Deviation ---
REM Alarm if actual position deviates from request by 1.5x deadband for 10 min
IF ABS( DMP-POS - DMP-REQ ) > ( CFG-DMP-DB * 1.5 ) THEN DALARM DMP-POS, 0:10:00
REM
999 REM End
"""


def build():
    return Module(
        id="vvt-zone-core",
        name="VVT Zone Core",
        category="core",
        description="VVT zone damper: room temp control, HVAC voting, array writes to MPV, MO7 damper",
        is_core=True,

        # AI1 = DAT — mandatory SBS standard on ALL zone controllers
        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250",
                       "Discharge Air Temperature", "deg.F"),
            # Factory reserved inputs — display only, from RC-FLEXair blank
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
            ValuePoint(1,  "DIAM",             "AV", 0.0,   "Duct Diameter (factory)",            "in.",    module="FACTORY"),
            ValuePoint(2,  "FLO-CAL",          "AV", 0.0,   "Flow Calibration (factory)",         "CFM",   module="FACTORY"),
            ValuePoint(3,  "CAL-K",            "AV", 0.0,   "K-Factor (factory)",                 "",      module="FACTORY"),
            ValuePoint(4,  "FLO",              "AV", 0.0,   "Volumetric Flow (factory)",          "CFM",   module="FACTORY"),
            ValuePoint(5,  "FLO-SP",           "AV", 0.0,   "Flow Setpoint (factory)",            "CFM",   module="FACTORY"),
            ValuePoint(7,  "FLO-DB",           "AV", 0.0,   "Flow Deadband (factory)",            "CFM",   module="FACTORY"),
            # Factory reserved BV (display only)
            ValuePoint(6,  "FLO-CTRL",         "BV", False, "Flow Control Enable (factory)",               module="FACTORY"),

            # ── Room temperature and setpoints ──
            ValuePoint(9,  "ACT-RMT",          "AV", 72.5,  "Actual Room Temperature",            "deg.F"),
            ValuePoint(10, "ACT-RMT-SP",       "AV", 72.0,  "Actual Room Temp Setpoint",          "deg.F"),
            ValuePoint(11, "RMT-SP",           "AV", 72.0,  "Room Temp Setpoint (operator)",      "deg.F"),
            ValuePoint(12, "RMT-HTG-SP",       "AV", 71.0,  "Room Heating Setpoint (calculated)", "deg.F"),
            ValuePoint(13, "RMT-CLG-SP",       "AV", 73.0,  "Room Cooling Setpoint (calculated)", "deg.F"),
            ValuePoint(14, "RMT-SP-DEV",       "AV", 0.0,   "Room Setpoint Deviation",            "deg.F"),

            # ── Voting ──
            ValuePoint(18, "HVAC-MODE-VOTE",   "AV", 1.0,   "HVAC Mode Vote Value (to MPV)",      ""),

            # ── Damper ──
            ValuePoint(25, "DMP-REQ",          "AV", 75.0,  "Damper Position Request",            "%"),

            # ── Configuration ──
            ValuePoint(27, "CFG-ZONE-ADDR",    "AV", 1.0,   "Zone Array Address (set at gen)",    ""),
            ValuePoint(29, "CFG-RMT-SP-LO-LIMIT", "AV", 55.0, "Room SP Low Limit",               "deg.F"),
            ValuePoint(30, "CFG-RMT-SP-HI-LIMIT", "AV", 85.0, "Room SP High Limit",              "deg.F"),
            ValuePoint(31, "CFG-RMT-SP-DB",    "AV", 2.0,   "Room SP Deadband",                   "deg.F"),
            ValuePoint(32, "CFG-RMT-NSB-SP",   "AV", 60.0,  "Night Setback Setpoint",             "deg.F"),
            ValuePoint(33, "CFG-RMT-NSF-SP",   "AV", 85.0,  "Night Setforward Setpoint",          "deg.F"),
            ValuePoint(36, "CFG-BYPASS-SP",    "AV", 120.0, "Bypass Timer Setpoint",              "Min."),

            # ── Vote weights ──
            ValuePoint(38, "VOTE-NORMAL-DEV",  "AV", 2.0,   "Normal Vote Deviation Threshold",    "deg.F"),
            ValuePoint(39, "VOTE-DEMAND-DEV",  "AV", 3.0,   "Demand Vote Deviation Threshold",    "deg.F"),
            ValuePoint(41, "CFG-VOTE-HTG-NORMAL", "AV", 1.0, "Heating Normal Vote Weight",        ""),
            ValuePoint(42, "CFG-VOTE-HTG-DEMAND", "AV", 0.5, "Heating Demand Vote Weight",        ""),
            ValuePoint(43, "CFG-VOTE-CLG-NORMAL", "AV", 1.0, "Cooling Normal Vote Weight",        ""),
            ValuePoint(44, "CFG-VOTE-CLG-DEMAND", "AV", 0.5, "Cooling Demand Vote Weight",        ""),
            ValuePoint(45, "CFG-VOTE-ESM-NORMAL", "AV", 1.0, "ESM Normal Vote Weight",            ""),

            # ── Damper config ──
            ValuePoint(47, "CFG-DMP-MIN",      "AV", 10.0,  "Damper Minimum Position",            "%"),
            ValuePoint(48, "CFG-DMP-MAX",      "AV", 100.0, "Damper Maximum Position",            "%"),
            ValuePoint(49, "CFG-DMP-FAIL",     "AV", 75.0,  "Damper Fail-Safe Position",          "%"),
            ValuePoint(50, "CFG-DMP-ESM",      "AV", 50.0,  "Damper ESM Position",                "%"),
            ValuePoint(51, "CFG-DMP-DB",       "AV", 10.0,  "Damper Deadband",                    "%"),

            # ── Network values from MPV ──
            ValuePoint(53, "NET-RTU-STATUS",   "AV", 35.0,  "Network RTU Status (vendor ID)",     ""),
            ValuePoint(55, "NET-SAT",          "AV", 0.0,   "Network Supply Air Temp (from MPV)", "deg.F"),

            # ── Binary values ──
            ValuePoint(20, "OCC-CMD",          "BV", False, "Occupancy Command"),
            ValuePoint(21, "OCC-BYPASS",       "BV", False, "Bypass Mode Active"),
            ValuePoint(22, "OCC-STANDBY",      "BV", False, "Standby Mode Active"),
            ValuePoint(23, "OCC-MOTION",       "BV", False, "Motion Sensor Detected"),
            ValuePoint(35, "CFG-SCHED-LOCAL",  "BV", False, "Use Local Schedule vs Network"),
            ValuePoint(54, "NET-RTU-SF-S",     "BV", False, "Network RTU Supply Fan Status"),
            ValuePoint(56, "NET-GLOBAL-ESM",   "BV", False, "Network Global ESM Flag"),
            ValuePoint(57, "NET-SCHED",        "BV", False, "Network Schedule/Occ Command"),

            # ── Multi-state values ──
            ValuePoint(16, "OCC-MODE",         "MV", "Unoccupied",
                       "Occupancy Mode",
                       states={1: "Occupied", 2: "Bypass", 3: "Standby",
                               4: "Unoccupied", 5: "NSB", 6: "NSF"}),
            ValuePoint(17, "HVAC-MODE-LOCAL",  "MV", "Ventilation",
                       "Local HVAC Mode",
                       states={1: "Ventilation", 2: "Cool", 3: "Reheat",
                               4: "Heat", 5: "Initialize"}),
            ValuePoint(58, "NET-HVAC-MODE",    "MV", "Ventilation",
                       "Network HVAC Mode (from MPV)",
                       states={1: "Ventilation", 2: "Cool", 3: "Reheat",
                               4: "Heat", 5: "Initialize"}),
        ],

        loops=[
            # DMP-LOOP: room temp to damper position
            # Action dynamically switched by DMP-PRG:
            #   Direct in cooling (temp rises → damper opens)
            #   Reverse in heating (temp drops → damper opens)
            LoopDef(1, "DMP-LOOP", "DMP-POS", "ACT-RMT-SP", "DMP-REQ",
                    p_band=4.0, integral=20.0, action="direct",
                    description="Damper position control — action dynamically switched by DMP-PRG"),
        ],

        programs=[
            ProgramDef(1, "NET-PRG", "PRG01-NET.bas", _PRG01_NET, True,
                       "Network: reads from MPV, writes to MPV arrays (AY1-4)",
                       exec_order=1),
            ProgramDef(2, "CFG-PRG", "PRG02-CFG.bas", _PRG02_CFG, True,
                       "Configuration: setpoint limits, HTG/CLG SP calc, deviation",
                       exec_order=2),
            ProgramDef(3, "OCC-PRG", "PRG03-OCC.bas", _PRG03_OCC, True,
                       "Occupancy (6-mode): schedule, bypass, standby, NSB, NSF",
                       exec_order=3),
            ProgramDef(4, "DMP-PRG", "PRG04-DMP.bas", _PRG04_DMP, True,
                       "Damper control: MO7 OPEN/CLOSE/IDLE, fail-safe, ESM",
                       exec_order=4),
            ProgramDef(5, "MODE-PRG", "PRG05-MODE.bas", _PRG05_MODE, True,
                       "HVAC mode voting: calculates vote value for MPV",
                       exec_order=5),
            ProgramDef(6, "ALARM-PRG", "PRG06-ALARM.bas", _PRG06_ALARM, True,
                       "Alarms: damper deviation, high/low room temp",
                       exec_order=6),
        ],

        schedules=[
            ScheduleDef(1, "LOCAL-SCHED", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10,
                        "Local occupancy schedule"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-STATUS",
                           "Zone status overview: modes, temps, damper, votes"),
            SystemGroupDef("{device-name}-CONFIG",
                           "Zone configuration: setpoints, damper limits, vote weights"),
        ],

        soo_paragraph="""The VVT zone controller shall be equipped with a direct digital control (DDC)
system providing fully automatic operation. The DDC controller (RC-FLEXair)
shall include factory-integrated differential pressure sensor and damper actuator
for airflow measurement and damper modulation.

The zone controller shall communicate with the MPV master RTU via BACnet.
Network reads shall include supply fan status, supply air temperature, global
energy savings mode, occupancy command, and system HVAC mode. The zone shall
write room temperature, HVAC mode vote, setpoint deviation, and occupancy mode
to the MPV arrays every scan cycle.

Occupancy modes shall include Occupied, Bypass, Standby, Unoccupied, Night Setback,
and Night Set-Forward. Mode transitions shall be based on network occupancy commands
from the MPV or local schedule, with motion sensor bypass capability.

The zone shall calculate an HVAC mode vote based on room temperature deviation from
setpoint. Heating votes (negative values) indicate demand for heat. Cooling votes
(values above 10) indicate demand for cooling. ESM votes (0-9) indicate the zone
is satisfied. The MPV tallies all zone votes to determine system HVAC mode.

Damper control shall modulate the factory motor output (MO7) based on a PID loop
comparing room temperature to setpoint. The controller shall disable firmware flow
control and instead modulate the damper directly using OPEN/CLOSE/IDLE commands
with a configurable deadband. Fail-safe positions shall be maintained when RTU
communication is lost or supply fan is not running.""",
    )
