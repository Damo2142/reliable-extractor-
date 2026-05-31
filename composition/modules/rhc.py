"""
SBS-RHC-801 — Standalone Duct Reheat Coil Modules

A self-contained reheat coil controller (no fan, no cooling) for a duct-mounted
hot water reheat coil. Controller: MACH-ProZone 44 (MPZ-44).

Standard I/O:
  AI1 = DAT (discharge air temp, 10K type III, mandatory)
  AI3 = RMT (room temp) — only when the hard-wired stat module is selected
        (vav-stat-hardwired). With vav-stat-comm the room temp arrives via BACnet.

Control Architecture — Cascaded PID (same pattern as FCU / UV):
  PRG01 MODE-CTRL : occupancy mode + heating setpoint selection, sensor reads
  PRG02 HTG-RESET : space-temp loop (HTG-RESET-LOOP) resets HTG-DAT-SP
  PRG03 HTG-OUTPUT: DAT loop (HTG-DAT-LOOP) drives the reheat valve

  HTG-RESET-LOOP : input ACT-RMT vs ACT-HTG-SP, reverse acting
                   (low space temp -> higher DAT setpoint)
  HTG-DAT-LOOP   : input ACT-DAT vs HTG-DAT-SP, reverse acting
                   (DAT below setpoint -> valve opens)

Zone sensor (mutually exclusive, reuse existing VAV stat modules):
  vav-stat-hardwired (default) — AI3 RMT, copies to ACT-RMT
  vav-stat-comm                — Smart-Net communicating, ACT-RMT via BACnet

Valve options (mutually exclusive):
  rhc-hw-mod — modulating AO HW valve
  rhc-hw-flt — floating point HW valve, CBAS FLOAT() (same as vav-rh-hw-flt)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
#  Program code
# ═══════════════════════════════════════════════════════════════════════════

_PRG01_MODE = """\
REM --- MODE-CTRL ---
REM Occupancy mode and heating setpoint selection.
REM Room temp (ACT-RMT) is supplied by the selected stat module:
REM   vav-stat-hardwired copies AI3 to ACT-RMT, vav-stat-comm writes it via BACnet.
REM
IF NET-OCC-CMD = 1 THEN OCC-MODE = 1 ELSE OCC-MODE = 0
IF OCC-MODE = 0 THEN HTG-SP = CFG-UNOCC-HTG-SP ELSE HTG-SP = CFG-OCC-HTG-SP
ACT-HTG-SP = HTG-SP
ACT-DAT = DAT
"""

_PRG02_HTG_RESET = """\
REM --- HTG-RESET ---
REM Space temp loop resets the heating discharge-air setpoint.
REM HTG-RESET-LOOP: input=ACT-RMT vs setpoint=ACT-HTG-SP, reverse acting.
REM Low space temp = higher DAT-SP (more reheat).
REM
HTG-DAT-SP = SLIDE( HTG-RESET-LOOP , 0.0 , 100.0 , CFG-HTG-DAT-MIN , CFG-HTG-DAT-MAX )
"""

_PRG03_HW_MOD = """\
REM --- HTG-OUTPUT ---
REM HW modulating reheat valve driven by HTG-DAT-LOOP.
REM HTG-DAT-LOOP: input=ACT-DAT vs setpoint=HTG-DAT-SP, reverse acting.
REM
HW-VLV = HTG-DAT-LOOP
IF ACT-DAT > CFG-DAT-HL THEN HW-VLV = 0
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP THEN HW-VLV = 0
IF NOT HWS-OK THEN HW-VLV = 0
HW-VLV-POS = HW-VLV
"""

_PRG03_HW_FLT = """\
REM --- HTG-OUTPUT ---
REM HW floating reheat valve using CBAS FLOAT() function.
REM FLOAT( open-BO , close-BO , pos-cmd , drive-time , deadband , sync )
REM
REM Position command from the heating DAT loop.
RH-POS-CMD = HTG-DAT-LOOP
REM
REM Safety / availability overrides force the valve closed.
IF ACT-DAT > CFG-DAT-HL THEN RH-POS-CMD = 0
IF OCC-MODE = 0 AND ACT-RMT > CFG-UNOCC-HTG-SP THEN RH-POS-CMD = 0
IF NOT HWS-OK THEN RH-POS-CMD = 0
REM
REM Floating sync on power cycle and transition to unoccupied.
IF+ POWER-LOSS THEN START RH-FLOAT-SYNC
IF+ OCC-MODE = 0 THEN START RH-FLOAT-SYNC
IF TIME-ON( RH-FLOAT-SYNC ) > 0:00:05 THEN STOP RH-FLOAT-SYNC
REM
REM FLOAT() drives the open/close relays and tracks position.
RH-POS = FLOAT( RH-OPEN , RH-CLOSE , RH-POS-CMD , CFG-RH-DRV-TIME , CFG-RH-POS-DB , RH-FLOAT-SYNC )
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Core module — always present
# ═══════════════════════════════════════════════════════════════════════════

def build_rhc_core():
    """RHC core — DAT sensor, cascade loops, occupancy, heating setpoints."""
    return Module(
        id="rhc-core",
        name="Reheat Coil Core",
        category="core",
        description="Standalone duct reheat coil: DAT sensor, cascade reset + DAT loops, occupancy, setpoints",
        is_core=True,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250", "Discharge Air Temperature", "deg.F"),
        ],

        values=[
            # Sensor reads / active values
            ValuePoint(1,  "ACT-RMT",          "AV", 72.0,  "Actual Room Temperature",        "deg.F"),
            ValuePoint(2,  "ACT-DAT",          "AV", 90.0,  "Actual Discharge Air Temp",      "deg.F"),
            # Heating setpoints
            ValuePoint(3,  "CFG-OCC-HTG-SP",   "AV", 70.0,  "Occupied Heating Setpoint",      "deg.F"),
            ValuePoint(4,  "CFG-UNOCC-HTG-SP", "AV", 60.0,  "Unoccupied Heating Setpoint",    "deg.F"),
            ValuePoint(5,  "HTG-SP",           "AV", 70.0,  "Current Heating SP",             "deg.F"),
            ValuePoint(6,  "ACT-HTG-SP",       "AV", 70.0,  "Active Heating Setpoint",        "deg.F"),
            # DAT reset setpoint + limits
            ValuePoint(7,  "HTG-DAT-SP",       "AV", 95.0,  "Heating DAT Setpoint",           "deg.F"),
            ValuePoint(8,  "CFG-HTG-DAT-MIN",  "AV", 85.0,  "Min Heating DAT SP",             "deg.F"),
            ValuePoint(9,  "CFG-HTG-DAT-MAX",  "AV", 110.0, "Max Heating DAT SP",             "deg.F"),
            ValuePoint(10, "CFG-DAT-HL",       "AV", 120.0, "DAT High Limit (safety)",        "deg.F"),
            # Binary
            ValuePoint(11, "NET-OCC-CMD",      "BV", True,  "Network Occupied Command"),
            ValuePoint(12, "OCC-MODE",         "BV", True,  "Occupancy Mode (1=occ)"),
            ValuePoint(13, "HWS-OK",           "BV", True,  "Hot Water Available"),
        ],

        loops=[
            LoopDef(1, "HTG-RESET-LOOP", "ACT-RMT", "ACT-HTG-SP", "HTG-DAT-SP",
                    p_band=4.0, integral=10.0, action="reverse",
                    description="Heating: space temp resets HTG-DAT-SP"),
            LoopDef(2, "HTG-DAT-LOOP", "ACT-DAT", "HTG-DAT-SP", "HTG-DAT-SP",
                    p_band=8.0, integral=20.0, action="reverse",
                    description="Heating DAT loop drives the reheat valve"),
        ],

        programs=[
            ProgramDef(1, "MODE-CTRL", "PRG01-MODE-CTRL.bas", _PRG01_MODE, True,
                       "Occupancy mode and heating setpoint selection", exec_order=1),
            ProgramDef(2, "HTG-RESET", "PRG02-HTG-RESET.bas", _PRG02_HTG_RESET, True,
                       "Space temp loop resets HTG-DAT-SP", exec_order=2),
        ],

        schedules=[
            ScheduleDef(1, "LOCAL-SCHEDULE", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10, "Local occupancy schedule"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM", "Reheat coil system overview"),
            SystemGroupDef("{device-name}-SET-POINTS", "Setpoints and configuration"),
        ],

        soo_paragraph="""The duct reheat coil shall be controlled by a direct digital controller
providing fully automatic cascaded PID control. A primary loop resets the discharge
air temperature setpoint based on space temperature. A secondary discharge air
temperature loop drives the hot water valve to maintain the calculated discharge
setpoint. The reheat valve shall close when the discharge air high limit is exceeded,
during unoccupied periods once the space is satisfied, and when the hot water system
status indicates unavailable.""",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Valve modules (select one)
# ═══════════════════════════════════════════════════════════════════════════

def build_rhc_hw_mod():
    """Modulating HW reheat valve (AO 0-10V)."""
    return Module(
        id="rhc-hw-mod", name="RHC HW Modulating", category="heating",
        description="Modulating hot water reheat valve (AO) driven by HTG-DAT-LOOP",
        outputs=[
            OutputPoint(1, "HW-VLV", "AO", "0.0 ->100%", "HW Reheat Valve (reverse)", 10.0, 2.0, True, "%"),
        ],
        values=[
            ValuePoint(20, "HW-VLV-POS", "AV", 0.0, "HW Valve Position (tracked)", "%"),
        ],
        programs=[
            ProgramDef(3, "HTG-OUTPUT", "PRG03-HTG-OUTPUT.bas", _PRG03_HW_MOD, True,
                       "HW mod valve = HTG-DAT-LOOP", exec_order=3),
        ],
        requires=["rhc-core"],
        conflicts=["rhc-hw-flt"],
        mutually_exclusive_group="rhc-valve",
    )


def build_rhc_hw_flt():
    """Floating point HW reheat valve (BO open/close) using CBAS FLOAT()."""
    return Module(
        id="rhc-hw-flt", name="RHC HW Floating", category="heating",
        description="Floating hot water reheat valve (BO open/close) with FLOAT() position tracking",
        outputs=[
            OutputPoint(1, "RH-OPEN",  "BO", "Off/On", "Reheat Valve Open",  units=""),
            OutputPoint(2, "RH-CLOSE", "BO", "Off/On", "Reheat Valve Close", units=""),
        ],
        values=[
            ValuePoint(20, "RH-POS",          "AV", 0.0,   "Reheat Valve Actual Position",    "%"),
            ValuePoint(21, "RH-POS-CMD",      "AV", 0.0,   "Reheat Valve Commanded Position", "%"),
            ValuePoint(22, "CFG-RH-DRV-TIME", "AV", 150.0, "Reheat Valve Full Stroke Time",   "Sec."),
            ValuePoint(23, "CFG-RH-POS-DB",   "AV", 2.0,   "Reheat Float Position Deadband",  "%"),
            ValuePoint(24, "RH-FLOAT-SYNC",   "BV", False, "Reheat Float Sync Trigger"),
        ],
        programs=[
            ProgramDef(3, "HTG-OUTPUT", "PRG03-HTG-OUTPUT.bas", _PRG03_HW_FLT, True,
                       "HW floating valve = HTG-DAT-LOOP via FLOAT()", exec_order=3),
        ],
        requires=["rhc-core"],
        conflicts=["rhc-hw-mod"],
        mutually_exclusive_group="rhc-valve",
    )
