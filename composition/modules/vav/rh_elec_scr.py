"""
VAV SCR Modulating Electric Reheat Module — vav-rh-elec-scr

AI1 = DAT, AO1 = RH-SCR (0-10V SCR controller).
RH-LOOP (Loop 2) controls SCR output: reverse acting, DAT → DAT-SP → RH-SCR.
No HWS-OK check — electric heat is self-contained.
PRG4 = RH-PRG calculates DAT-SP and enables/disables loop.

Used by: VAV-SD-ELEC-SCR, VAV-PF-ELEC-SCR, VAV-SF-ELEC-SCR
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef,
    ProgramDef, SystemGroupDef
)


_PRG04_RH = """\
REM --- RH-PRG ---
REM SCR modulating electric reheat: DAT-SP calc, SCR enable/disable.
REM RH-LOOP modulates RH-SCR to maintain DAT at DAT-SP when active.
REM No HW dependency — electric heat is self-contained.
REM
REM --- DAT Setpoint from room temp deviation (always computed) ---
DAT-SP = SLIDE( RMT-SP-HTG - ACT-RMT , 0.0 , 4.0 , DAT-MIN-SP , DAT-MAX-SP )
DAT-SP = LIMIT( DAT-SP , DAT-MIN-SP , DAT-MAX-SP )
IF DAT-SP > RH-MAX-DAT THEN DAT-SP = RH-MAX-DAT
REM
REM --- Park DAT-SP at min when not in Reheat (3) / Heat (4) mode ---
IF HVAC-MODE < 3 THEN DAT-SP = DAT-MIN-SP
IF HVAC-MODE > 4 THEN DAT-SP = DAT-MIN-SP
REM
REM --- Force SCR output to 0 out of heating mode or on safety cutoff ---
IF HVAC-MODE < 3 THEN RH-SCR = 0.0
IF HVAC-MODE > 4 THEN RH-SCR = 0.0
IF DAT > RH-MAX-DAT THEN RH-SCR = 0.0
REM
REM --- Mirror SCR output to feedback position AV ---
RH-SCR-POS = RH-SCR
"""


def build():
    return Module(
        id="vav-rh-elec-scr",
        name="SCR Modulating Electric Reheat",
        category="reheat",
        description="SCR modulating electric reheat (AO 0-10V) with DAT control loop",
        is_core=False,

        inputs=[
            InputPoint(1, "DAT", "AI", "10K -40 ->250",
                       "Discharge Air Temperature", "deg.F"),
        ],

        outputs=[
            OutputPoint(1, "RH-SCR", "AO", "0.0 ->100%",
                        "SCR Electric Reheat (0-10V)", 2.0, 10.0, False, "%"),
        ],

        values=[
            ValuePoint(34, "RH-SCR-POS",   "AV", 0.0,   "SCR Output Position (tracked)",   "%"),
            ValuePoint(36, "DAT-MAX-SP",   "AV", 102.5, "Max DAT Setpoint",                "deg.F"),
            ValuePoint(37, "DAT-SP",       "AV", 90.0,  "Active DAT Setpoint (calculated)","deg.F"),
            ValuePoint(39, "DAT-MIN-SP",   "AV", 70.0,  "Min DAT Setpoint",                "deg.F"),
        ],

        loops=[
            LoopDef(2, "RH-LOOP", "DAT", "DAT-SP", "RH-SCR",
                    p_band=2.0, integral=4.0, action="reverse",
                    description="DAT to SCR output — reverse: DAT above SP reduces output"),
        ],

        programs=[
            ProgramDef(4, "RH-PRG", "PRG04-RH.bas", _PRG04_RH, True,
                       "SCR modulating electric reheat: DAT-SP calc, SCR enable/disable",
                       exec_order=4),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-REHEAT",
                           "SCR reheat control: DAT, setpoints, SCR output"),
        ],

        soo_paragraph="""The VAV terminal unit shall include a modulating electric reheat coil
controlled by an SCR (silicon controlled rectifier) via a 0-10V analog
output. Discharge air temperature shall be measured by a 10K thermistor
sensor. The reheat PID loop shall modulate the SCR output to maintain
discharge air temperature at a calculated setpoint. The SCR output shall
be zero in ventilation and cooling modes. The SCR shall de-energize
immediately if discharge air temperature exceeds the maximum safety limit.""",

        mutually_exclusive_group="reheat",
    )
