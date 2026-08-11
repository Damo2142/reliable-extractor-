"""
UV (Unit Ventilator) — Single-Zone Constant-Volume Control

ARCHITECTURE: Single-path constant-volume terminal. Not VAV. One supply stream
cannot simultaneously heat and cool, so exactly one mode is active at any time.

Core Modules:
  uv-core: DAT/OAT/RMT sensors, unified DAT-SP, HVAC-MODE arbiter,
           zone loop resets DAT-SP, single reverse-acting DAT loop,
           freeze protection, humidity monitor
  uv-hw-mod: HW modulating valve (reverse-acting), gated on HVAC-MODE=Heat
  uv-chw-mod: CHW modulating valve (direct-acting), gated on HVAC-MODE=Cool,
              closed until OAD reaches 100% during economizer
  uv-oad: OA damper ASHRAE Cycle 1+2 economizer
  uv-freezestat: Hardware freezestat + DAT low limit detection

Standard I/O:
  AI1 = DAT (discharge air temp, 10K type III, mandatory)
  AI2 = OAT (outdoor air temp, 10K type III)
  RMT (room temp) — from thermostat module (vav-stat-comm or hardwired)
  RH (relative humidity) — from communicating stat, monitor only
  BI = SF-STS (fan status feedback)

Control Flow:
  PRG01 MODE-CTRL: occupancy mode, active setpoints, HVAC-MODE arbiter
  PRG02 DAT-RESET: zone loop resets unified DAT-SP with mode clamps
  PRG03 UNOCC-OAT: freeze protection based on OAT low limit
  PRG05 HTG-OUTPUT: HW valve from DAT-LOOP, gated on mode, freeze override
  PRG06 CLG-OUTPUT: CHW valve from DAT-LOOP, gated on mode, economizer gate
  PRG07 OAD-CTRL: OA damper ASHRAE Cycle 1+2
  PRG08 FAN-CTRL: fan on/off or VFD speed (from fan module)
  PRG09 FREEZESTAT: hardware freezestat edge detect + rolling window counter

Controller: MACH-ProZone 88 standard, MACH-ProView LCD optional
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
#  Program Code
# ═══════════════════════════════════════════════════════════════════════════

_PRG01_MODE_CTRL = """\
REM --- MODE-CTRL ---
REM Occupancy mode and setpoint selection. HVAC-MODE arbiter.
REM {parent} = parent device for network variables
REM
IF NET-OCC-CMD = 1 THEN OCC-MODE = 1 ELSE OCC-MODE = 0
REM
REM --- Active Setpoints ---
REM Single operator zone setpoint (RMT-SP) with symmetric deadband.
REM Cooling setpoint = operator SP + deadband; heating setpoint = operator SP - deadband.
REM Occupied: both actives from one setpoint so they stay locked and cannot drift.
REM Unoccupied: use unoccupied setback pair.
ACT-RMT-SP-DB = DB-MTPLR * CFG-RMT-SP-DB
IF OCC-MODE = 1 THEN ACT-CLG-SP = RMT-SP + ACT-RMT-SP-DB
IF OCC-MODE = 1 THEN ACT-HTG-SP = RMT-SP - ACT-RMT-SP-DB
IF OCC-MODE = 0 THEN ACT-CLG-SP = CFG-UNOCC-CLG-SP
IF OCC-MODE = 0 THEN ACT-HTG-SP = CFG-UNOCC-HTG-SP
REM Display mirrors of active setpoints
CLG-SP = ACT-CLG-SP
HTG-SP = ACT-HTG-SP
REM
REM --- HVAC-MODE Arbiter (single-path discharge control) ---
REM Space temp vs active setpoints determines one mode. Exactly one mode active
REM because single supply stream cannot heat and cool simultaneously.
REM Modes: 1=Vent(deadband) 2=Cool 3=Heat 5=Init
REM Vent mode (deadband) maintains supply fan with no heating or cooling;
REM used during mild weather and unoccupied deadband periods.
IF ACT-RMT > ACT-CLG-SP THEN HVAC-MODE = 2
IF ACT-RMT < ACT-HTG-SP THEN HVAC-MODE = 3
IF ( ACT-RMT >= ACT-HTG-SP ) AND ( ACT-RMT <= ACT-CLG-SP ) THEN HVAC-MODE = 1
REM
REM --- Actual Temperature ---
REM ACT-RMT is set by the selected thermostat module (communicating or hardwired).
REM ACT-DAT comes from discharge air temperature sensor.
ACT-DAT = DAT
REM
REM --- OAT Source ---
REM Network OAT (preferred) from parent controller (AV1). Falls back to local
REM OAT sensor if network value is implausible (range check).
NET-OAT = {parent}AV1
IF NET-OAT > -60 AND NET-OAT < 140 THEN NET-OAT-OK = 1 ELSE NET-OAT-OK = 0
IF CFG-OAT-LOCAL OR NOT NET-OAT-OK THEN ACT-OAT = OAT
IF NOT CFG-OAT-LOCAL AND NET-OAT-OK THEN ACT-OAT = NET-OAT
REM
REM --- Network Signals ---
REM Occupancy command from parent BV21 (AHU occupancy schedule).
REM HW-available status from parent BV22 (HW plant availability).
NET-OCC-CMD = {parent}BV21
HWS-OK = {parent}BV22
REM
REM --- Humidity Monitor (from communicating stat) ---
REM ZN-RH is read by the communicating thermostat module and stored in ZN-RH AV.
REM This program only reads it and makes it available for trending. No control
REM logic uses humidity; monitor only.
"""

_PRG02_DAT_RESET = """\
REM --- DAT-RESET ---
REM Zone loop resets unified DAT-SP. Mode-dependent clamps ensure:
REM   Heat mode: DAT-SP in HTG range (CFG-HTG-DAT-MIN to CFG-HTG-DAT-MAX)
REM   Cool mode: DAT-SP in CLG range (CFG-CLG-DAT-MIN to CFG-CLG-DAT-MAX)
REM   Vent mode: DAT-SP held at HTG-MIN (no heating, no cooling)
REM Constraint: CFG-HTG-DAT-MIN must be <= CFG-CLG-DAT-MIN or simultaneous
REM heat and cool occurs when space setpoints overlap.
REM
REM Unified DAT setpoint reset from zone loop (direct-acting, space temp input).
REM SLIDE output 0-100% to appropriate range based on active mode.
REM
IF HVAC-MODE = 3 THEN DAT-SP = SLIDE( DAT-RESET-LOOP, 0.0, 100.0, CFG-HTG-DAT-MIN, CFG-HTG-DAT-MAX )
IF HVAC-MODE = 2 THEN DAT-SP = SLIDE( DAT-RESET-LOOP, 0.0, 100.0, CFG-CLG-DAT-MIN, CFG-CLG-DAT-MAX )
IF HVAC-MODE = 1 THEN DAT-SP = CFG-HTG-DAT-MIN
IF HVAC-MODE = 5 THEN DAT-SP = CFG-HTG-DAT-MIN
"""

_PRG03_UNOCC_OAT = """\
REM --- UNOCC-OAT-LIMIT ---
REM Unoccupied freeze protection: disable economizer and close discharge
REM cooling when unoccupied AND outdoor air temperature drops below limit.
REM
UNOCC-OAT-LOW = 0
IF OCC-MODE = 0 AND ACT-OAT < CFG-UNOCC-OAT-LIM THEN UNOCC-OAT-LOW = 1
REM When freeze protection active, close OA damper and CHW valve
IF UNOCC-OAT-LOW = 1 THEN OAD = 0
"""

_PRG05_HW_MOD = """\
REM --- HTG-OUTPUT (HW modulating valve) ---
REM HW valve driven by DAT loop in Heat mode only. Freeze override opens valve 100%.
REM Discharge high limit check prevents simultaneous heat and cool.
REM Freeze protection syntax: comma-END (no GOTO).
REM
REM Freeze override: if FREEZE-TRIP active, open valve fully and stop all other logic
IF FREEZE-TRIP = 1 THEN HW-VLV = 100 , END
REM
REM Normal mode-based control
IF HVAC-MODE = 3 THEN HW-VLV = DAT-LOOP
IF HVAC-MODE = 2 THEN HW-VLV = 0
IF HVAC-MODE = 1 THEN HW-VLV = 0
REM
REM Discharge high limit check: safety cutoff to prevent overshoot
REM Applied BEFORE any output scaling; limits are in °F.
IF ACT-DAT > CFG-DAT-HL THEN HW-VLV = 0
"""

_PRG06_CLG_MOD = """\
REM --- CLG-OUTPUT (CHW modulating valve) ---
REM CHW valve driven by DAT loop in Cool mode only. Economizer gate: valve closed
REM until OAD reaches 100% (free cooling exhausted). Freeze protection closes valve.
REM
REM Economizer gate: do not open CHW until OA damper is at 100%
REM (when OAD < 100, economizer is still available, do not use CHW yet)
REM This prevents simultaneous economizer and mechanical cooling.
IF OAD < 100 AND CYCLE2-ENABLE = 1 THEN CHW-VLV = 0
REM
REM Normal mode-based control
IF HVAC-MODE = 2 AND OAD >= 100 THEN CHW-VLV = DAT-LOOP
IF HVAC-MODE = 3 THEN CHW-VLV = 0
IF HVAC-MODE = 1 THEN CHW-VLV = 0
REM
REM Safety: close CHW below low limit
IF ACT-DAT < CFG-DAT-LL THEN CHW-VLV = 0
REM
REM Freeze protection: close CHW
IF UNOCC-OAT-LOW = 1 THEN CHW-VLV = 0
"""

_PRG07_OAD = """\
REM --- OAD-CTRL ---
REM ASHRAE Cycle 1 (minimum OA) + Cycle 2 (free cooling economizer)
REM Cycle 1: always open damper to minimum position when occupied.
REM Cycle 2: when free cooling available (OAT < space return temp AND OAT < enable temp),
REM open damper to modulate cooling DAT demand.
REM
OAD = CFG-OAD-MIN
REM Unoccupied: close OA damper
IF OCC-MODE = 0 THEN OAD = 0
REM Freeze protection: close OA damper
IF UNOCC-OAT-LOW = 1 THEN OAD = 0
REM Economizer Cycle 2 enable condition
IF ACT-OAT < ACT-RMT AND ACT-OAT < CFG-ECON-ENABLE-T THEN CYCLE2-ENABLE = 1 ELSE CYCLE2-ENABLE = 0
REM Cycle 2 modulation: open OA damper to meet cooling demand
IF CYCLE2-ENABLE = 1 AND OCC-MODE = 1 THEN OAD = SLIDE( DAT-LOOP, 0.0, 100.0, CFG-OAD-MIN, 100.0 )
"""

_PRG09_FREEZESTAT = """\
REM --- FREEZESTAT ---
REM Hardware freezestat + DAT low limit detection with rolling-window lockout.
REM CFG-FSTAT-NC=TRUE (default): NC switch, freeze on FSTAT=0 (fail-safe wiring).
REM CFG-FSTAT-NC=FALSE: NO switch, freeze on FSTAT=1.
REM
REM Normalize freezestat contact to FSTAT-TRIP (1=freeze alarm, 0=normal)
IF CFG-FSTAT-NC THEN FSTAT-TRIP = NOT FREEZE-STAT ELSE FSTAT-TRIP = FREEZE-STAT
REM
REM DAT low limit check
IF ACT-DAT < CFG-DAT-FREEZE THEN FSTAT-TRIP = 1
REM
REM Edge detect: capture rising edge only
IF FSTAT-TRIP = 1 AND FREEZE-TRIP-EDGE = 0 THEN FREEZE-TRIP-EDGE = 1
IF FSTAT-TRIP = 0 THEN FREEZE-TRIP-EDGE = 0
REM
REM Rolling-window counter: increment on rising edge, decay timer on clear
IF FREEZE-TRIP-EDGE = 1 THEN FREEZE-TRIP-COUNTER = FREEZE-TRIP-COUNTER + 1
IF FSTAT-TRIP = 0 THEN FREEZE-WINDOW-TIMER = FREEZE-WINDOW-TIMER + 1
IF FREEZE-WINDOW-TIMER > CFG-FREEZE-WINDOW * 60 THEN FREEZE-TRIP-COUNTER = 0 : FREEZE-WINDOW-TIMER = 0
REM
REM Lockout: hard stop when trip count exceeded
IF FREEZE-TRIP-COUNTER >= CFG-FREEZE-TRIP-COUNT THEN FREEZE-LOCKOUT = 1
REM Manual reset: clears counter and lockout, but NOT if FSTAT-TRIP still active
IF FREEZE-RST = 1 AND FSTAT-TRIP = 0 THEN FREEZE-TRIP-COUNTER = 0 : FREEZE-LOCKOUT = 0 : FREEZE-WINDOW-TIMER = 0
REM
REM Latched trip: active if FSTAT-TRIP OR FREEZE-LOCKOUT
FREEZE-TRIP = FSTAT-TRIP OR FREEZE-LOCKOUT
FREEZE-ALARM = FREEZE-TRIP OR FREEZE-LOCKOUT
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Core Module
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_core():
    """UV core — single-zone constant-volume base module

    Provides:
      - DAT/OAT/RMT sensor inputs
      - Unified DAT-SP (single setpoint, not dual)
      - Zone loop (direct-acting) resets DAT-SP per HVAC mode
      - Single reverse-acting DAT loop (drives valve outputs)
      - HVAC-MODE arbiter (1=Vent, 2=Cool, 3=Heat, 5=Init)
      - Occupancy/freeze protection logic
      - Humidity monitor (from communicating stat, monitor only)

    Does NOT include valve outputs or fan control — those are separate modules.
    """
    return Module(
        id="uv-core",
        name="UV Core",
        category="core",
        description="Single-zone CV base: sensors, unified DAT-SP, HVAC-MODE arbiter, freeze protection",
        is_core=True,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40->250", "Discharge Air Temperature", "°F"),
            InputPoint(2, "OAT", "AI", "10K -40->250", "Outdoor Air Temperature", "°F"),
            # RMT comes from selected thermostat module (communicating or hardwired)
            InputPoint(4, "SF-STS", "BI", "Off/On", "Fan Status Feedback"),
            # Freezestat input (optional freezestat module, defaults to 1 if not wired)
            InputPoint(9, "FREEZE-STAT", "BI", "Off/On", "Hardware Freezestat (NC=0 when freeze)"),
        ],

        values=[
            # Actual Temperatures
            ValuePoint(1, "ACT-RMT",           "AV", 72.0,  "Actual Room Temp",            "°F"),
            ValuePoint(2, "ACT-DAT",           "AV", 55.0,  "Actual DAT",                  "°F"),
            ValuePoint(3, "ACT-OAT",           "AV", 65.0,  "Actual OAT",                  "°F"),
            ValuePoint(14, "NET-OAT",          "AV", 65.0,  "Network OAT from parent",     "°F"),

            # Single Zone Setpoint + Deadband
            ValuePoint(4, "RMT-SP",            "AV", 72.0,  "Operator Room Temp Setpoint", "°F"),
            ValuePoint(5, "CFG-RMT-SP-DB",     "AV", 1.0,   "Room Temp SP Deadband",       "°F"),
            ValuePoint(12, "DB-MTPLR",         "AV", 1.5,   "Deadband Multiplier",         ""),
            ValuePoint(13, "ACT-RMT-SP-DB",    "AV", 1.5,   "Active Setpoint Deadband",    "°F"),

            # Occupied/Unoccupied Setpoints
            ValuePoint(6, "CFG-UNOCC-CLG-SP",  "AV", 85.0,  "Unoccupied Cooling SP",       "°F"),
            ValuePoint(7, "CFG-UNOCC-HTG-SP",  "AV", 60.0,  "Unoccupied Heating SP",       "°F"),
            ValuePoint(8, "ACT-CLG-SP",        "AV", 73.5,  "Active Cooling SP",           "°F"),
            ValuePoint(9, "ACT-HTG-SP",        "AV", 70.5,  "Active Heating SP",           "°F"),
            ValuePoint(10, "CLG-SP",           "AV", 73.5,  "Current Cooling SP (display)","°F"),
            ValuePoint(11, "HTG-SP",           "AV", 70.5,  "Current Heating SP (display)","°F"),

            # Unified DAT Setpoint + Mode-Dependent Clamps
            ValuePoint(31, "DAT-SP",           "AV", 75.0,  "Unified Discharge Air Setpoint", "°F"),
            ValuePoint(33, "CFG-CLG-DAT-MIN",  "AV", 52.0,  "Min Cooling DAT SP",          "°F"),
            ValuePoint(34, "CFG-CLG-DAT-MAX",  "AV", 65.0,  "Max Cooling DAT SP",          "°F"),
            ValuePoint(35, "CFG-HTG-DAT-MIN",  "AV", 85.0,  "Min Heating DAT SP",          "°F"),
            ValuePoint(36, "CFG-HTG-DAT-MAX",  "AV", 110.0, "Max Heating DAT SP",          "°F"),

            # Safety Limits
            ValuePoint(37, "CFG-DAT-LL",       "AV", 45.0,  "DAT Low Limit (safety)",      "°F"),
            ValuePoint(38, "CFG-DAT-HL",       "AV", 110.0, "DAT High Limit (safety)",     "°F"),
            ValuePoint(39, "CFG-DAT-FREEZE",   "AV", 38.0,  "DAT Freeze Protection",       "°F"),
            ValuePoint(40, "CFG-UNOCC-OAT-LIM","AV", 35.0,  "Unoccupied Freeze Enable OAT","°F"),

            # Humidity Monitor (from communicating stat, monitor only)
            ValuePoint(49, "ZN-RH",            "AV", 50.0,  "Zone Relative Humidity", "%"),

            # OA Economizer Config
            ValuePoint(80, "CFG-OAD-MIN",      "AV", 10.0,  "Min OA Damper Position",      "%"),
            ValuePoint(81, "CFG-ECON-ENABLE-T","AV", 65.0,  "Economizer Enable Temp",      "°F"),

            # Freezestat Config
            ValuePoint(41, "CFG-FSTAT-NC",     "BV", True,  "Freezestat NC wiring (default TRUE)"),
            ValuePoint(42, "CFG-FREEZE-WINDOW","AV", 30.0,  "Freeze Counter Window (minutes)","min"),
            ValuePoint(43, "CFG-FREEZE-TRIP-COUNT", "AV", 3.0, "Freeze Trips to Lockout", "trips"),
            ValuePoint(44, "FREEZE-RST",       "BV", False, "Freeze Counter Manual Reset"),

            # Status/Mode BVs
            ValuePoint(100, "NET-OCC-CMD",     "BV", True,  "Network Occupied Command"),
            ValuePoint(101, "OCC-MODE",        "BV", True,  "Occupancy Mode (1=Occ, 0=Unocc)"),
            ValuePoint(102, "HWS-OK",          "BV", True,  "Hot Water Available"),
            ValuePoint(103, "UNOCC-OAT-LOW",   "BV", False, "Unoccupied OAT Low Freeze Active"),
            ValuePoint(104, "CFG-OAT-LOCAL",   "BV", False, "Use Local OAT (default FALSE=network)"),
            ValuePoint(105, "NET-OAT-OK",      "BV", True,  "Network OAT Plausible"),
            ValuePoint(106, "CYCLE2-ENABLE",   "BV", False, "Economizer Cycle 2 Available"),

            # HVAC Mode Arbiter
            ValuePoint(20, "HVAC-MODE",        "MV", 1,     "HVAC Mode", states={1:"Vent", 2:"Cool", 3:"Heat", 5:"Init"}),

            # Freeze Protection
            ValuePoint(107, "FSTAT-TRIP",      "BV", False, "Freezestat Normalized Trip"),
            ValuePoint(108, "FREEZE-TRIP-EDGE","BV", False, "Freeze Trip Rising Edge"),
            ValuePoint(109, "FREEZE-TRIP-COUNTER", "AV", 0.0, "Freeze Trip Rolling Counter", "trips"),
            ValuePoint(110, "FREEZE-WINDOW-TIMER", "AV", 0.0, "Freeze Window Decay Timer", "sec"),
            ValuePoint(111, "FREEZE-LOCKOUT",  "BV", False, "Freeze Lockout Active"),
            ValuePoint(112, "FREEZE-TRIP",     "BV", False, "Freeze Trip (valve override)"),
            ValuePoint(113, "FREEZE-ALARM",    "BV", False, "Freeze Alarm (display)"),
        ],

        loops=[
            LoopDef(1, "DAT-RESET-LOOP", "ACT-RMT", "ACT-CLG-SP", "DAT-SP",
                    p_band=4.0, integral=10.0, action="direct",
                    description="Zone temp resets unified DAT-SP (direct-acting)"),
            LoopDef(2, "DAT-LOOP", "ACT-DAT", "DAT-SP", "DAT-LOOP",
                    p_band=8.0, integral=20.0, action="reverse",
                    description="DAT feedback loop drives valve outputs (reverse)"),
        ],

        programs=[
            ProgramDef(1, "MODE-CTRL", "PRG01-MODE-CTRL.bas", _PRG01_MODE_CTRL, True,
                       "Occupancy mode, setpoint selection, HVAC-MODE arbiter", exec_order=1),
            ProgramDef(2, "DAT-RESET", "PRG02-DAT-RESET.bas", _PRG02_DAT_RESET, True,
                       "Zone loop resets unified DAT-SP with mode clamps", exec_order=2),
            ProgramDef(3, "UNOCC-OAT-LIMIT", "PRG03-UNOCC-OAT-LIMIT.bas", _PRG03_UNOCC_OAT, True,
                       "Unoccupied OAT low limit freeze protection", exec_order=3),
            ProgramDef(9, "FREEZESTAT", "PRG09-FREEZESTAT.bas", _PRG09_FREEZESTAT, True,
                       "Hardware freezestat + DAT low limit with rolling lockout", exec_order=9),
        ],

        schedules=[
            ScheduleDef(1, "LOCAL-SCHEDULE", "Occupancy",
                        ["Unoccupied", "Occupied"], 10, "Local occupancy schedule"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM", "UV system overview"),
            SystemGroupDef("{device-name}-SET-POINTS", "Setpoints and configuration"),
            SystemGroupDef("{device-name}-FREEZE", "Freeze protection status"),
        ],

        soo_paragraph="""The unit ventilator shall be equipped with a direct digital controller
providing cascaded PID control. A zone temperature loop resets a unified discharge
air temperature setpoint. A discharge air loop maintains that setpoint via valve
modulation. HVAC-MODE arbiter (Vent/Cool/Heat) gates outputs to prevent simultaneous
heating and cooling. Freeze protection activates unoccupied with low outdoor temperature
and includes both hardware freezestat and discharge air low limit detection with
rolling-window lockout.""",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  HW Module
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_hw_mod():
    """HW modulating valve — single-zone constant-volume

    Reverse-acting valve (100% = fully open, driven by output scaling).
    Gated on HVAC-MODE = Heat (mode 3). Includes freeze override (comma-END syntax).
    Reads DAT-LOOP output from uv-core. Discharge high limit applied as safety cutoff.
    """
    return Module(
        id="uv-hw-mod",
        name="UV HW Modulating",
        category="heating",
        description="HW modulating valve, reverse-acting, gated on Heat mode",
        outputs=[OutputPoint(6, "HW-VLV", "AO", "0.0->100%", "HW Valve (reverse)", 10.0, 2.0, True)],
        programs=[
            ProgramDef(5, "HTG-OUTPUT", "PRG05-HTG-OUTPUT.bas", _PRG05_HW_MOD, True,
                       "HW valve from DAT-LOOP, Heat-mode gated, freeze override", exec_order=5)
        ],
        requires=["uv-core"],
        conflicts=["uv-chw-mod"],
        mutually_exclusive_group=None,  # Can be combined with other modules
        trends=True,  # HW-VLV trended
    )


# ═══════════════════════════════════════════════════════════════════════════
#  CHW Module
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_chw_mod():
    """CHW modulating valve — single-zone constant-volume

    Direct-acting valve (0% = closed, 100% = fully open).
    Gated on HVAC-MODE = Cool (mode 2). Economizer gate: valve stays closed until
    OAD reaches 100% (economizer exhausted). Discharge low limit safety cutoff.
    Reads DAT-LOOP output from uv-core.
    """
    return Module(
        id="uv-chw-mod",
        name="UV CHW Modulating",
        category="cooling",
        description="CHW modulating valve, direct-acting, gated on Cool mode, economizer gate",
        outputs=[OutputPoint(4, "CHW-VLV", "AO", "0.0->100%", "CHW Valve", 2.0, 10.0)],
        requires=["uv-core"],
        conflicts=["uv-hw-mod"],
        mutually_exclusive_group=None,
        programs=[
            ProgramDef(6, "CLG-OUTPUT", "PRG06-CLG-OUTPUT.bas", _PRG06_CLG_MOD, True,
                       "CHW valve from DAT-LOOP, Cool-mode gated, economizer gate", exec_order=6)
        ],
        trends=True,  # CHW-VLV trended
    )


# ═══════════════════════════════════════════════════════════════════════════
#  OA Damper Module
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_oad():
    """OA damper — ASHRAE Cycle 1 (minimum) + Cycle 2 (free cooling)

    Cycle 1: maintains minimum OA position when occupied.
    Cycle 2: opens damper to modulate economizer cooling when available
    (OAT < return temp AND OAT < enable threshold).
    """
    return Module(
        id="uv-oad",
        name="UV OA Damper Economizer",
        category="economizer",
        description="OA damper ASHRAE Cycle 1+2 economizer control",
        outputs=[OutputPoint(10, "OAD", "AO", "0.0->100%", "OA Damper Position", 2.0, 10.0)],
        requires=["uv-core"],
        programs=[
            ProgramDef(7, "OAD-CTRL", "PRG07-OAD-CTRL.bas", _PRG07_OAD, True,
                       "OA damper Cycle 1+2 economizer", exec_order=7)
        ],
        trends=True,  # OAD trended
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Freezestat Module
# ═══════════════════════════════════════════════════════════════════════════

def build_uv_freezestat():
    """Optional hardware freezestat with rolling-window lockout

    Detects freeze via hardwired contact (NC or NO configurable) OR discharge
    air low limit. Rolling-window counter prevents nuisance trips; manual reset
    clears lockout. Outputs FREEZE-TRIP signal that overrides heating/cooling
    outputs in hw-mod/chw-mod programs.
    """
    return Module(
        id="uv-freezestat",
        name="UV Freezestat",
        category="safety",
        description="Hardware freezestat + DAT low limit with rolling lockout",
        requires=["uv-core"],
        # No additional I/O, values, or programs — all logic is in uv-core PRG09
        # This module's presence simply indicates freezestat feature is selected.
        description_detail="""Hardware freezestat contact input (BI9) provides freeze detection
with NC/NO wiring option. DAT low-limit check in same program. Rolling-window counter
with lockout prevents nuisance trips. Manual reset BV44 clears counter and lockout.""",
    )
