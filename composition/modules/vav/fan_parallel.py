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
REM Start when HVAC mode is Reheat (3) or Heat (4)
REM Stop in Vent (1), Cool (2), or Unoccupied
REM
REM --- Fan Command ---
IF HVAC-MODE = 3 THEN SF-CMD = 1
IF HVAC-MODE = 4 THEN SF-CMD = 1
IF HVAC-MODE = 1 THEN SF-CMD = 0
IF HVAC-MODE = 2 THEN SF-CMD = 0
IF OCC-MODE = 4 THEN SF-CMD = 0
REM
REM --- Fan Enable Delay ---
REM Delay fan start to allow damper to reach position
IF SF-CMD = 1 AND NOT SF-STS THEN SF-CMD = TIME-ON( SF-CMD, SF-ENA-DLY )
REM
REM --- Fan Proof ---
REM Verify fan is running after command
IF SF-CMD = 1 AND NOT SF-STS THEN SF-FAIL = TIME-ON( SF-CMD AND NOT SF-STS, 0:01:00 )
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
