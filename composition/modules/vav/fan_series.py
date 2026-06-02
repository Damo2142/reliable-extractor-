"""
VAV Series Fan Module — vav-fan-series

Adds series fan-powered box fan control.
BI1 = SF-STS (fan status), BO3 = SF-CMD (fan start/stop).
Series fan runs CONTINUOUSLY whenever occupied — not just on heating call.
PRG5 = FAN-PRG handles start/stop, proof, and fail detection.

Key difference from parallel fan:
  Parallel: runs only on heating demand (HVAC mode 3 or 4)
  Series:   runs whenever occupied (OCC-CMD = true)

Used by: VAV-SF-HW-MOD, VAV-SF-HW-FLT, VAV-SF-ELEC-2, VAV-SF-ELEC-SCR
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG05_FAN = """\
REM --- FAN-PRG ---
REM Series fan: runs continuously when occupied
REM Series fan is in the primary airstream — must run whenever unit is active
REM Stops only when unoccupied
REM
REM --- Fan Command ---
REM Series fan ON whenever occupied, OFF when unoccupied
IF OCC-CMD THEN SF-CMD = 1
IF NOT OCC-CMD THEN SF-CMD = 0
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
        id="vav-fan-series",
        name="Series Fan",
        category="fan",
        description="Series fan-powered box fan: runs continuously when occupied, BO start/stop + BI status",
        is_core=False,

        inputs=[
            # Row 2 — row 1 reserved for DAT (reheat module)
            InputPoint(2, "SF-STS", "BI", "Off/On",
                       "Supply Fan Status", ""),
        ],

        outputs=[
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
                       "Series fan: runs continuously when occupied, proof, fail detect",
                       exec_order=5),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-FAN",
                           "Fan control: command, status, fail, delays"),
        ],

        soo_paragraph="""The VAV terminal unit shall include a series fan-powered box with
an integral supply fan located in the primary airstream. The fan shall
run continuously whenever the unit is in an occupied mode, providing
constant airflow to the zone regardless of primary air damper position.
The fan shall stop only when the unit transitions to unoccupied mode.
Fan status shall be monitored via a current switch. A fan failure alarm
shall annunciate if the fan fails to prove running within 60 seconds
of the start command.""",

        mutually_exclusive_group="fan",
    )
