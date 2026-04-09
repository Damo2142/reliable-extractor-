"""
VVT Modulating HW Reheat Module — vvt-rh-hw-mod

Adds modulating hot water reheat valve to VVT zone controller.
AI1 = DAT (discharge air temp), AO1 = RH-VLV (0-10V valve).
RH-LOOP (Loop 2) controls DAT directly: reverse acting.
PRG7 = RH-PRG calculates DAT-SP from HVAC mode + demand.

VVT-specific interlocks:
  1. NET-WU-MODE (warmup) → reheat OFF (RTU handles warmup)
  2. NET-HVAC-MODE = Cool AND local heat → damper to min, reheat fires
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, SystemGroupDef
)


_PRG07_RH = """\
REM --- RH-PRG ---
REM VVT modulating HW reheat: DAT-SP calc, valve enable/disable
REM RH-LOOP (Loop 2) controls valve to maintain DAT at DAT-SP
REM
REM --- VVT Warmup Lockout ---
REM If RTU is in warmup mode, reheat off — RTU handles warmup
IF NET-HVAC-MODE = 5 THEN GOTO 800
REM
REM --- Reheat Mode ---
REM In local Reheat or Heat mode: calculate DAT setpoint
IF HVAC-MODE-LOCAL = 3 THEN GOTO 100
IF HVAC-MODE-LOCAL = 4 THEN GOTO 100
REM
REM --- No Reheat ---
REM Vent, Cool, or Unoccupied — close valve
800 REM
RH-VLV = 0.0
DAT-SP = DAT-MIN-SP
RH-VLV-POS = 0.0
GOTO 999
REM
REM --- Reheat Active ---
100 REM Calculate DAT setpoint based on room temp deviation
REM More deviation below heating setpoint = higher DAT-SP
DAT-SP = SLIDE( RMT-HTG-SP - ACT-RMT, 0.0, 4.0, DAT-MIN-SP, DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP, DAT-MIN-SP, DAT-MAX-SP )
REM
REM --- Safety Limit ---
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Track Valve Position ---
RH-VLV-POS = RH-VLV
REM
999 REM End
"""


def build():
    return Module(
        id="vvt-rh-hw-mod",
        name="VVT Modulating HW Reheat",
        category="reheat",
        description="Modulating hot water reheat valve (AO 0-10V) with VVT interlocks",
        is_core=False,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250",
                       "Discharge Air Temperature", "deg.F"),
        ],

        outputs=[
            OutputPoint(1, "RH-VLV", "AO", "0.0 ->100%",
                        "HW Reheat Valve", 2.0, 10.0, False, "%"),
        ],

        values=[
            ValuePoint(34, "RH-VLV-POS",  "AV", 0.0,   "Reheat Valve Position (tracked)", "%"),
            ValuePoint(36, "DAT-MAX-SP",   "AV", 102.5, "Max DAT Setpoint",                "deg.F"),
            ValuePoint(37, "DAT-SP",       "AV", 90.0,  "Active DAT Setpoint (calculated)","deg.F"),
            ValuePoint(39, "DAT-MIN-SP",   "AV", 70.0,  "Min DAT Setpoint",                "deg.F"),
            ValuePoint(100,"RH-MAX-DAT",   "AV", 90.0,  "Reheat Max Discharge Air Temp",   "deg.F"),
        ],

        loops=[
            LoopDef(2, "RH-LOOP", "DAT", "DAT-SP", "RH-VLV",
                    p_band=2.0, integral=4.0, action="reverse",
                    description="DAT to reheat valve — reverse: DAT above SP closes valve"),
        ],

        programs=[
            ProgramDef(7, "RH-PRG", "PRG07-RH.bas", _PRG07_RH, True,
                       "VVT modulating HW reheat: DAT-SP calc, warmup lockout",
                       exec_order=7),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "Reheat valve control: DAT, setpoints, valve position"),
        ],

        soo_paragraph="""The VVT zone controller shall include a modulating hot water reheat valve
controlled by a 0-10V analog output. Discharge air temperature shall be
measured by a 10K thermistor sensor. The reheat PID loop shall modulate
the valve to maintain discharge air temperature at a calculated setpoint.
The reheat valve shall close when the RTU is in warmup mode (Initialize).
The DAT setpoint shall be reset based on room temperature deviation below
the heating setpoint, from a configurable minimum to maximum range.""",

        mutually_exclusive_group="reheat",
    )
