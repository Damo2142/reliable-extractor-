"""
Ventilation Modules — Fixed, Airflow Measuring Station, DCV-CO2, DCV-OCC, 100%

Based on A201: PRG14 (OAD-MIN-POS-PRG) with CO2 DCV
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, TableDef, ProgramDef, SystemGroupDef
)


def build_vent_fix():
    """Fixed minimum OA damper position"""
    return Module(
        id="vent-fix",
        name="Ventilation Fixed Minimum",
        category="ventilation",
        description="Fixed minimum OA damper position — no airflow measurement",

        values=[
            ValuePoint(106, "OAD-MIN-POS", "AV", 30.0, "OA Damper Minimum Position", "%"),
            ValuePoint(105, "ACT-OAD-MIN-POS", "AV", 0.0, "Active OA Minimum Position", "%"),
        ],

        programs=[
            ProgramDef(14, "OAD-MIN-POS-PRG", "PRG14-VENT-FIX.bas", "", True,
                       "Fixed minimum OA damper position",
                       exec_order=14),
        ],

        soo_paragraph="""Minimum outside air ventilation shall be maintained by a fixed
minimum outside air damper position setpoint. The damper shall open
to the minimum position after the OA damper delay following supply
fan start.""",

        requires=["core"],
        conflicts=["vent-ams", "dcv-co2", "dcv-occ", "vent-100"],
        mutually_exclusive_group="ventilation",
    )


def build_vent_ams():
    """Airflow measuring station — measured OA flow control"""
    return Module(
        id="vent-ams",
        name="Ventilation Airflow Station",
        category="ventilation",
        description="OA airflow measuring station with flow-based minimum control",

        inputs=[
            InputPoint(21, "OA-CFM", "AI", "Table3", "Outside Airflow", "CFM", "OA-VEL-TBL"),
        ],

        values=[
            ValuePoint(106, "OAD-MIN-POS",     "AV", 30.0, "OA Damper Minimum Position", "%"),
            ValuePoint(105, "ACT-OAD-MIN-POS", "AV", 0.0,  "Active OA Minimum Position", "%"),
            ValuePoint(147, "OA-AREA",         "AV", 6.5,  "OA Duct Cross Section Area", ""),
            ValuePoint(148, "OA-FLOW-ACT",     "AV", 0.0,  "Actual OA Airflow",          "CFM"),
            ValuePoint(149, "OA-K-FACTOR",     "AV", 1.7,  "OA K-Factor Correction",     ""),
        ],

        tables=[
            TableDef(3, "OA-VEL-TBL", "Volts", "FPM",
                     [[2.0, 0.0], [6.0, 1300.0], [10.0, 2600.0]],
                     "OA velocity sensor scaling"),
        ],

        programs=[
            ProgramDef(14, "OAD-MIN-POS-PRG", "PRG14-VENT-AMS.bas", "", True,
                       "OA flow measuring with minimum position",
                       exec_order=14),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-VENTILATION", "OA flow, minimum position", conditional=True),
        ],

        soo_paragraph="""Minimum outside air ventilation shall be maintained using an airflow
measuring station. Actual OA airflow shall be calculated from velocity
sensor reading, duct cross-section area, and K-factor correction. The OA
damper minimum position shall ensure the required minimum ventilation
rate is maintained.""",

        requires=["core"],
        conflicts=["vent-fix", "vent-100"],
        mutually_exclusive_group="ventilation",
    )


def build_dcv_co2():
    """Demand controlled ventilation — CO2 based"""
    return Module(
        id="dcv-co2",
        name="DCV CO2",
        category="ventilation",
        description="Demand controlled ventilation using return air CO2 sensor",

        inputs=[
            InputPoint(9, "RA-CO2", "AI", "Table1", "Return Air CO2", "ppm", "CO2-TBL"),
        ],

        values=[
            ValuePoint(100, "MIN-OAD-DCV-POS", "AV", 10.0,   "Min OA Damper DCV Position",  "%"),
            ValuePoint(101, "MAX-OAD-DCV-POS", "AV", 100.0,  "Max OA Damper DCV Position",  "%"),
            ValuePoint(102, "RM-MAX-CO2",      "AV", 1000.0, "Room Max CO2 Setpoint",       "ppm"),
            ValuePoint(103, "CO2-MIN-SP",      "AV", 1000.0, "CO2 Minimum Setpoint",        "ppm"),
            ValuePoint(104, "CO2-MAX-SP",      "AV", 1200.0, "CO2 Maximum Setpoint",        "ppm"),
            ValuePoint(105, "ACT-OAD-MIN-POS", "AV", 0.0,    "Active OA Minimum Position",  "%"),
            ValuePoint(106, "OAD-MIN-POS",     "AV", 30.0,   "OA Damper Base Minimum",      "%"),
        ],

        tables=[
            TableDef(1, "CO2-TBL", "Volts", "ppm",
                     [[0.0, 0.0], [5.0, 1000.0], [10.0, 2000.0]],
                     "CO2 sensor scaling"),
        ],

        programs=[
            ProgramDef(14, "OAD-MIN-POS-PRG", "PRG14-DCV-CO2.bas", "", True,
                       "DCV CO2-based OA damper minimum position",
                       exec_order=14),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-VENTILATION", "CO2, DCV status, OA flow", conditional=True),
        ],

        soo_paragraph="""Demand controlled ventilation (DCV) shall be provided using a return
air CO2 sensor. The outside air damper minimum position shall modulate
between configurable minimum and maximum positions based on CO2 level.
As CO2 rises from the minimum setpoint to the maximum setpoint, the OA
damper minimum position shall increase proportionally. This provides
energy-efficient ventilation by reducing outdoor air when the space
is lightly occupied.""",

        requires=["core"],
        conflicts=["vent-fix", "vent-100"],
    )


def build_dcv_occ():
    """Demand controlled ventilation — occupancy sensor based"""
    return Module(
        id="dcv-occ",
        name="DCV Occupancy",
        category="ventilation",
        description="Demand controlled ventilation using occupancy sensor count",

        values=[
            ValuePoint(105, "ACT-OAD-MIN-POS",  "AV", 0.0,   "Active OA Minimum Position",   "%"),
            ValuePoint(106, "OAD-MIN-POS",       "AV", 30.0,  "OA Damper Base Minimum",       "%"),
            ValuePoint(220, "OCC-COUNT",         "AV", 0.0,   "Occupancy Count",              "#"),
            ValuePoint(221, "CFM-PER-PERSON",    "AV", 15.0,  "CFM per Person",               "CFM"),
            ValuePoint(222, "CFM-PER-AREA",      "AV", 0.06,  "CFM per Square Foot",          "CFM"),
            ValuePoint(223, "FLOOR-AREA",        "AV", 5000.0,"Floor Area",                   "ft²"),
            ValuePoint(224, "MIN-OA-CFM",        "AV", 0.0,   "Calculated Min OA CFM",        "CFM"),
        ],

        programs=[
            ProgramDef(14, "OAD-MIN-POS-PRG", "PRG14-DCV-OCC.bas", "", True,
                       "DCV occupancy-based OA damper minimum",
                       exec_order=14),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-VENTILATION", "Occupancy count, DCV status", conditional=True),
        ],

        soo_paragraph="""Demand controlled ventilation shall be provided using occupancy
sensors. Minimum outside air volume shall be calculated per ASHRAE 62.1:
(occupancy count × CFM per person) + (floor area × CFM per square foot).
The OA damper minimum position shall adjust to deliver the required
ventilation rate based on actual occupancy.""",

        requires=["core"],
        conflicts=["vent-fix", "vent-100"],
    )


def build_vent_100():
    """100% outside air — DOAS / MAU"""
    return Module(
        id="vent-100",
        name="100% Outside Air",
        category="ventilation",
        description="100% outside air unit — no return air, no economizer",

        values=[
            ValuePoint(105, "ACT-OAD-MIN-POS", "AV", 100.0, "Active OA Minimum Position", "%"),
        ],

        programs=[
            ProgramDef(14, "OAD-MIN-POS-PRG", "PRG14-VENT-100.bas", "", True,
                       "100% OA — damper always full open",
                       exec_order=14),
        ],

        soo_paragraph="""The unit shall operate as a 100% outside air unit (dedicated outdoor
air system). The outside air damper shall remain fully open at all times
during fan operation. No return air damper or economizer shall be provided.""",

        requires=["core"],
        conflicts=["vent-fix", "vent-ams", "dcv-co2", "dcv-occ",
                   "econ-db", "econ-enth", "econ-diff", "econ-diff-db"],
        mutually_exclusive_group="ventilation",
    )
