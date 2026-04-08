"""
VAV Communicating Stat CO2 Add-on — vav-stat-comm-co2

Adds DCV (demand controlled ventilation) based on CO2 from SS3.
AV48=RM-CO2, AV49=RM-CO2-SP, AV50=RM-CO2-SP-DB, BV47=CO2-PRESENT.
Modifies min airflow based on CO2 level.
Requires: vav-stat-comm
"""

from composition.models import Module, ValuePoint, ProgramDef


_CO2_CODE = """\
REM --- CO2-PRG ---
REM DCV: boost min airflow when CO2 exceeds setpoint
REM CO2 data from SMART-Sensor SS3 via BACnet
REM
IF NOT CO2-PRESENT THEN GOTO 999
REM
REM --- CO2 Demand ---
REM If CO2 above setpoint, increase min cooling flow
IF RM-CO2 > RM-CO2-SP THEN FLO-MIN-CLG-SP = CFG-MAX-CLG-FLO
IF RM-CO2 > ( RM-CO2-SP + RM-CO2-SP-DB ) THEN FLO-MIN-CLG-SP = CFG-MAX-CLG-FLO
REM
REM --- CO2 Satisfied ---
IF RM-CO2 < ( RM-CO2-SP - RM-CO2-SP-DB ) THEN FLO-MIN-CLG-SP = CFG-MIN-CLG-FLO
REM
999 REM End
"""


def build():
    return Module(
        id="vav-stat-comm-co2",
        name="CO2 Sensor (DCV)",
        category="thermostat-addon",
        description="CO2 demand controlled ventilation from SMART-Sensor SS3",
        is_core=False,

        inputs=[],
        outputs=[],

        values=[
            ValuePoint(47, "CO2-PRESENT",  "BV", False, "CO2 Sensor Present"),
            ValuePoint(48, "RM-CO2",       "AV", 400.0, "Room CO2 Level",          "PPM"),
            ValuePoint(49, "RM-CO2-SP",    "AV", 1000.0,"CO2 Setpoint",            "PPM"),
            ValuePoint(50, "RM-CO2-SP-DB", "AV", 100.0, "CO2 Setpoint Deadband",   "PPM"),
        ],

        loops=[],

        programs=[
            ProgramDef(12, "CO2-PRG", "PRG12-CO2.bas", _CO2_CODE, True,
                       "DCV: boost min airflow on CO2 demand",
                       exec_order=12),
        ],

        system_groups=[],

        soo_paragraph="""The SMART-Sensor SS3 shall include an integral CO2 sensor for demand
controlled ventilation. When room CO2 level exceeds the configurable
setpoint, minimum airflow shall increase to maximum cooling airflow
to flush the zone. Airflow shall return to normal minimum when CO2
drops below the setpoint minus deadband.""",

        requires=["vav-stat-comm"],
    )
