"""
VVT Bypass Core Module — vvt-bypass-core

Bypass damper controller for VVT systems.
Controller: RC-FLEXair (RCFA-34 minimum — needs AI1 + AI2).

Provides: duct static pressure relief via bypass damper, DAT-based
          heating/cooling lockouts published to MPV, MO7 damper control.

AI1 = STATIC-P (duct static pressure sensor)
AI2 = BYP-DAT (bypass duct discharge air temperature)

Lockout logic:
  Bypass DAT too low → SAT is cold → cooling lockout → set {parent}BV21=1
  Bypass DAT too high → SAT is hot → heating lockout → set {parent}BV20=1
  MPV ValuePoints: BV20=BYP-HTG-LOCKOUT, BV21=BYP-CLG-LOCKOUT (see mpv_core.py).
  Cross-device writes happen inside DMP-PRG — no separate publish step.

Parent MPV cross-device references (NET-PRG):
  {parent}DEV vendor-id  → local AV12  NET-RTU-S
  {parent}BI1            → local BV13  NET-RTU-SF-S
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, SystemGroupDef
)


# ═══════════════════════════════════════════════════════════════════════════
# Program source code — Control-BASIC
# ═══════════════════════════════════════════════════════════════════════════

_PRG01_NET = """\
REM --- NET-PRG ---
REM Network reads from MPV — RTU status and supply fan status.
REM Lockout publishing happens directly in DMP-PRG (cross-device write).
REM {parent} = BACnet device ID of the MPV RTU.
REM Set {parent} to the MPV device instance at commissioning.
REM
REM --- Read RTU Status (vendor ID property — confirms RTU is communicating) ---
NET-RTU-S = {parent}DEV4194303:121
REM
REM --- Read Supply Fan Status from MPV ---
NET-RTU-SF-S = {parent}BI1
"""

_PRG02_DMP = """\
REM --- DMP-PRG ---
REM Bypass damper: pressure relief via MO7 + cross-device lockout publish.
REM Flat precedence — defaults to normal control, overridden last-write-wins.
REM
REM --- Disable Firmware Flow Control (bypass uses pressure, not flow) ---
STOP BV6
BV6 = 0
REM
REM --- Default: Normal Pressure Control ---
REM DMP-LOOP reverse-acting: pressure rises → damper opens (relieves pressure)
DMP-REQ = DMP-LOOP
DMP-REQ = LIMIT( DMP-REQ , CFG-DMP-MIN , CFG-DMP-MAX )
REM
REM --- Override: supply fan off → unoccupied position ---
IF NOT NET-RTU-SF-S THEN DMP-REQ = CFG-DMP-UNOCC
REM
REM --- Override: RTU not communicating → fail-safe position ---
IF NET-RTU-S < 30.0 THEN DMP-REQ = CFG-DMP-RTU-FAIL
REM
REM --- Publish DAT Lockouts Directly to MPV ---
REM MPV BV21 = BYP-CLG-LOCKOUT, MPV BV20 = BYP-HTG-LOCKOUT (per mpv_core.py).
REM Hysteresis prevents cycling — set on the inner band, clear on the outer.
IF BYP-DAT < CFG-BYP-DAT-CLG-LO THEN {parent}BV21 = 1
IF BYP-DAT > CFG-BYP-DAT-CLG-HI THEN {parent}BV21 = 0
IF BYP-DAT > CFG-BYP-DAT-HTG-HI THEN {parent}BV20 = 1
IF BYP-DAT < CFG-BYP-DAT-HTG-LO THEN {parent}BV20 = 0
REM
REM --- Drive MO7 with Deadband ---
IF DMP-POS < ( DMP-REQ - CFG-DMP-DB ) THEN START MO7:OPEN
IF DMP-POS > ( DMP-REQ + CFG-DMP-DB ) THEN START MO7:CLOSE
IF ABS( DMP-POS - DMP-REQ ) <= CFG-DMP-DB THEN START MO7:IDLE
"""


def build():
    return Module(
        id="vvt-bypass-core",
        name="VVT Bypass Core",
        category="core",
        description="VVT bypass damper: duct static pressure relief, DAT lockouts, MO7 control",
        is_core=True,

        inputs=[
            InputPoint(1, "STATIC-P", "AI", "0.0 ->5.0 in.wc.",
                       "Duct Static Pressure", "in.wc."),
            InputPoint(2, "BYP-DAT",  "AI", "10K -40 ->250",
                       "Bypass Duct Discharge Air Temperature", "deg.F"),
            # Factory reserved inputs — display only
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
            # ── Factory reserved AV (display only) ──
            ValuePoint(1,  "DIAM",             "AV", 0.0,   "Duct Diameter (factory)",            "in.",    module="FACTORY"),
            ValuePoint(2,  "FLO-CAL",          "AV", 0.0,   "Flow Calibration (factory)",         "CFM",   module="FACTORY"),
            ValuePoint(3,  "CAL-K",            "AV", 0.0,   "K-Factor (factory)",                 "",      module="FACTORY"),
            ValuePoint(4,  "FLO",              "AV", 0.0,   "Volumetric Flow (factory)",          "CFM",   module="FACTORY"),
            ValuePoint(5,  "FLO-SP",           "AV", 0.0,   "Flow Setpoint (factory)",            "CFM",   module="FACTORY"),
            ValuePoint(7,  "FLO-DB",           "AV", 0.0,   "Flow Deadband (factory)",            "CFM",   module="FACTORY"),
            # Factory reserved BV
            ValuePoint(6,  "FLO-CTRL",         "BV", False, "Flow Control Enable (factory)",               module="FACTORY"),

            # ── Damper control ──
            ValuePoint(10, "DMP-REQ",          "AV", 100.0, "Damper Position Request",            "%"),

            # ── Network values from MPV ──
            ValuePoint(12, "NET-RTU-S",        "AV", 35.0,  "Network RTU Status (vendor ID)",     ""),

            # ── Configuration ──
            ValuePoint(15, "CFG-P-SP",         "AV", 1.0,   "Pressure Setpoint",                  "in.wc."),
            ValuePoint(16, "CFG-DMP-DB",       "AV", 10.0,  "Damper Deadband",                    "%"),
            ValuePoint(17, "CFG-DMP-UNOCC",    "AV", 100.0, "Damper Unoccupied Position",         "%"),
            ValuePoint(18, "CFG-DMP-RTU-FAIL", "AV", 50.0,  "Damper RTU Fail Position",           "%"),
            ValuePoint(19, "CFG-DMP-MIN",      "AV", 0.0,   "Damper Minimum Position",            "%"),
            ValuePoint(20, "CFG-DMP-MAX",      "AV", 100.0, "Damper Maximum Position",            "%"),

            # ── DAT lockout setpoints ──
            ValuePoint(21, "CFG-BYP-DAT-CLG-LO", "AV", 42.0,  "Bypass DAT Cooling Lockout Low",  "deg.F"),
            ValuePoint(22, "CFG-BYP-DAT-CLG-HI", "AV", 48.0,  "Bypass DAT Cooling Lockout High", "deg.F"),
            ValuePoint(23, "CFG-BYP-DAT-HTG-HI", "AV", 140.0, "Bypass DAT Heating Lockout High", "deg.F"),
            ValuePoint(24, "CFG-BYP-DAT-HTG-LO", "AV", 130.0, "Bypass DAT Heating Lockout Low",  "deg.F"),

            # ── Binary values ──
            # (BYP-CLG-LOCKOUT and BYP-HTG-LOCKOUT are written directly to MPV
            #  cross-device — no local copy needed.)
            ValuePoint(13, "NET-RTU-SF-S",     "BV", False, "Network RTU Supply Fan Status"),
        ],

        loops=[
            # DMP-LOOP: pressure to damper position
            # Reverse action: pressure rises → damper opens (relieves pressure)
            LoopDef(1, "DMP-LOOP", "STATIC-P", "CFG-P-SP", "DMP-REQ",
                    p_band=4.0, integral=20.0, action="reverse",
                    description="Pressure-based bypass damper — reverse: pressure rises, damper opens"),
        ],

        programs=[
            ProgramDef(1, "NET-PRG", "PRG01-NET.bas", _PRG01_NET, True,
                       "Network: reads from MPV, publishes lockout flags",
                       exec_order=1),
            ProgramDef(2, "DMP-PRG", "PRG02-DMP.bas", _PRG02_DMP, True,
                       "Damper control: pressure loop, DAT lockouts, MO7",
                       exec_order=2),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-STATUS",
                           "Bypass status: pressure, damper position, lockouts"),
            SystemGroupDef("{device-name}-CONFIG",
                           "Bypass configuration: setpoints, damper limits, lockout thresholds"),
        ],

        soo_paragraph="""The VVT bypass damper controller shall provide duct static pressure relief
for the VVT system. The controller (RC-FLEXair) shall include factory-integrated
differential pressure sensor and damper actuator.

The bypass controller shall monitor duct static pressure and modulate the bypass
damper to maintain the configured pressure setpoint. A reverse-acting PID loop
shall open the damper as pressure rises above setpoint.

The controller shall read supply fan status from the MPV master RTU via BACnet.
When the supply fan is not running, the bypass damper shall move to the configured
unoccupied position. When RTU communication is lost, the damper shall move to a
configurable fail-safe position.

Discharge air temperature in the bypass duct shall be monitored for heating and
cooling lockout conditions. When bypass DAT falls below the cooling lockout low
setpoint, a cooling lockout flag shall be published to the MPV to prevent further
cooling staging. When bypass DAT exceeds the heating lockout high setpoint, a
heating lockout flag shall be published. Lockout flags shall clear with deadband
hysteresis to prevent cycling.""",
    )
