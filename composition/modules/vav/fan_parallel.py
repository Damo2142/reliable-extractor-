"""
VAV Parallel Fan Module — vav-fan-parallel

Adds parallel fan-powered box fan control.
BI1 = SF-STS (fan status), BO3 = SF-CMD (fan start/stop).
Parallel fan runs on heating demand only — not continuous.
PRG5 = FAN-PRG handles start/stop, proof, and fail detection.

Fan IO uses BI row 1 and BO row 3 to avoid conflict with reheat on BO1/BO2.

Used by: VAV-PF-HW-MOD, VAV-PF-HW-FLT, VAV-PF-ELEC-2, VAV-PF-ELEC-SCR
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG05_FAN = """\
REM --- FAN-PRG ---
REM Parallel fan: runs on heating demand, not continuous
REM Fan ON when HVAC mode is Reheat (3) or Heat (4) — including unoccupied heating
REM Fan OFF in Vent (1) or Cool (2), or when there is no heating demand
REM Interlock is heating demand, NOT occupancy mode
REM
REM --- Fan Command ---
REM Heating-demand latch drives the fan; TIME-ON delays start to let damper reach position
B = HVAC-MODE = 3 OR HVAC-MODE = 4
SF-CMD = B AND TIME-ON( B ) > SF-ENA-DLY
REM
REM --- Fan Proof ---
REM Verify fan is running after command
A = SF-CMD AND NOT SF-STS
SF-FAIL = A AND TIME-ON( A ) > 0:01:00
IF SF-STS THEN SF-FAIL = 0
REM
REM --- Fan Status Alarm ---
SF-STS-ALARM = SF-FAIL
"""


def build():
    return Module(
        id="vav-fan-parallel",
        name="Parallel Fan",
        category="fan",
        description="Parallel fan-powered box fan: runs on heating demand, BO start/stop + BI status",
        is_core=False,

        inputs=[
            # Row 2 — row 1 reserved for DAT (reheat module)
            InputPoint(2, "SF-STS", "BI", "Off/On",
                       "Supply Fan Status", ""),
        ],

        outputs=[
            # BO row 3 — avoids conflict with reheat on BO1/BO2
            OutputPoint(3, "SF-CMD", "BO", "Off/On",
                        "Supply Fan Command", units=""),
        ],

        values=[
            ValuePoint(86, "SF-ENA-FLO",     "AV", 0.0,   "Fan Enable Flow Setpoint",      "CFM"),
            ValuePoint(87, "SF-ENA-DLY",     "AV", 30.0,  "Fan Enable Delay",              "Sec."),
            ValuePoint(88, "SF-DIS-DLY",     "AV", 30.0,  "Fan Disable Delay",             "Sec."),
            ValuePoint(89, "SF-FAIL",        "BV", False,  "Fan Fail Alarm"),
            ValuePoint(97, "SF-STS-ALARM",   "BV", False,  "Fan Status Alarm"),
        ],

        loops=[],

        programs=[
            ProgramDef(5, "FAN-PRG", "PRG05-FAN.bas", _PRG05_FAN, True,
                       "Parallel fan: start on heating demand, proof, fail detect",
                       exec_order=5),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-FAN",
                           "Fan control: command, status, fail, delays"),
        ],

        soo_paragraph="""The VAV terminal unit shall include a parallel fan-powered box with
an integral supply fan. The fan shall start when the HVAC mode transitions
to Reheat or Heat, providing recirculated plenum air to supplement
primary airflow during heating. The fan shall stop in ventilation and
cooling modes. Fan status shall be monitored via a current switch.
A fan failure alarm shall annunciate if the fan fails to prove running
within 60 seconds of the start command.""",

        mutually_exclusive_group="fan",
    )
