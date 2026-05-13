"""
VAV Modulating HW Reheat Module — vav-rh-hw-mod

Adds modulating hot water reheat valve to any VAV family.
AI1 = DAT (discharge air temp), AO1 = RH-VLV (0-10V valve).
RH-LOOP (Loop 2) controls DAT directly: reverse acting.
PRG4 = RH-PRG calculates DAT-SP from HVAC mode + demand.

Used by: VAV-SD-HW-MOD, VAV-PF-HW-MOD, VAV-SF-HW-MOD, VAV-DD-HW-MOD
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, SystemGroupDef
)


_PRG04_RH = """\
REM --- RH-PRG ---
REM Modulating HW reheat: DAT-SP calc, valve enable/disable.
REM RH-LOOP controls RH-VLV to maintain DAT at DAT-SP when active.
REM
REM --- DAT Setpoint from room temp deviation (always computed) ---
REM SLIDE: 0..4°F below heating SP maps to DAT-MIN..DAT-MAX.
DAT-SP = SLIDE( RMT-SP-HTG - ACT-RMT , 0.0 , 4.0 , DAT-MIN-SP , DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP , DAT-MIN-SP , DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Park DAT-SP at min when not in Reheat (3) / Heat (4) mode ---
REM (collapses RH-LOOP error so the valve stays closed)
IF HVAC-MODE < 3 THEN DAT-SP = DAT-MIN-SP
IF HVAC-MODE > 4 THEN DAT-SP = DAT-MIN-SP
REM
REM --- Force-close valve out of heating mode or when HW unavailable ---
IF HVAC-MODE < 3 THEN RH-VLV = 0.0
IF HVAC-MODE > 4 THEN RH-VLV = 0.0
IF NOT HWS-OK THEN RH-VLV = 0.0
REM
REM --- Mirror valve command to feedback position AV ---
RH-VLV-POS = RH-VLV
"""


def build():
    return Module(
        id="vav-rh-hw-mod",
        name="Modulating HW Reheat",
        category="reheat",
        description="Modulating hot water reheat valve (AO 0-10V) with DAT control loop",
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
        ],

        loops=[
            LoopDef(2, "RH-LOOP", "DAT", "DAT-SP", "RH-VLV",
                    p_band=2.0, integral=4.0, action="reverse",
                    description="DAT to reheat valve — reverse: DAT above SP closes valve"),
        ],

        programs=[
            ProgramDef(4, "RH-PRG", "PRG04-RH.bas", _PRG04_RH, True,
                       "Modulating HW reheat: DAT-SP calc, valve enable/disable",
                       exec_order=4),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "Reheat valve control: DAT, setpoints, valve position"),
        ],

        soo_paragraph="""The VAV terminal unit shall include a modulating hot water reheat valve
controlled by a 0-10V analog output. Discharge air temperature shall be
measured by a 10K thermistor sensor. The reheat PID loop shall modulate
the valve to maintain discharge air temperature at a calculated setpoint.
The DAT setpoint shall be reset based on room temperature deviation below
the heating setpoint, from a configurable minimum to maximum range.
The reheat valve shall close in ventilation and cooling modes, and when
the HW system status indicates unavailable.""",

        mutually_exclusive_group="reheat",
    )
