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
REM VVT modulating HW reheat: DAT-SP calc, valve enable/disable.
REM RH-LOOP controls RH-VLV to maintain DAT at DAT-SP when active.
REM Reheat off during RTU warmup (NET-HVAC-MODE=5) — RTU handles warmup.
REM
REM --- DAT Setpoint from room temp deviation (always computed) ---
DAT-SP = SLIDE( RMT-HTG-SP - ACT-RMT , 0.0 , 4.0 , DAT-MIN-SP , DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP , DAT-MIN-SP , DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Park DAT-SP at min when reheat is not active ---
IF HVAC-MODE-LOCAL < 3 THEN DAT-SP = DAT-MIN-SP
IF HVAC-MODE-LOCAL > 4 THEN DAT-SP = DAT-MIN-SP
IF NET-HVAC-MODE = 5 THEN DAT-SP = DAT-MIN-SP
REM
REM --- Force-close valve when reheat is not active ---
IF HVAC-MODE-LOCAL < 3 THEN RH-VLV = 0.0
IF HVAC-MODE-LOCAL > 4 THEN RH-VLV = 0.0
IF NET-HVAC-MODE = 5 THEN RH-VLV = 0.0
REM
REM --- Mirror valve command to feedback position AV ---
RH-VLV-POS = RH-VLV
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
            ValuePoint(57, "DAT-MAX-SP",   "AV", 102.5, "Max DAT Setpoint",                "deg.F"),
            ValuePoint(37, "DAT-SP",       "AV", 90.0,  "Active DAT Setpoint (calculated)","deg.F"),
            ValuePoint(58, "DAT-MIN-SP",   "AV", 70.0,  "Min DAT Setpoint",                "deg.F"),
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
