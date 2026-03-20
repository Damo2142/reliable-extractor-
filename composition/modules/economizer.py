"""
Economizer Modules — Dry Bulb, Enthalpy, Differential, Differential Dry Bulb

Based on A201: PRG10 (ECON-MODE-PRG)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, ProgramDef, SystemGroupDef
)


def build_econ_db():
    """Economizer — dry bulb temperature lockout"""
    return Module(
        id="econ-db",
        name="Economizer Dry Bulb",
        category="economizer",
        description="Economizer with OAT dry bulb high limit lockout",

        outputs=[
            OutputPoint(2, "RAD", "AO", "0.0 ->100%", "Return Air Damper (reverse)", 10.0, 2.0, True),
        ],

        values=[
            ValuePoint(72, "ECON-HI-DB-SP", "AV", 65.0,  "Economizer High DB Lockout SP", "°F"),
            ValuePoint(74, "ECON-MODE",      "BV", False, "Economizer Mode Active"),
        ],

        programs=[
            ProgramDef(10, "ECON-MODE-PRG", "PRG10-ECON-DB.bas", "", True,
                       "Economizer dry bulb enable/disable",
                       exec_order=10),
            ProgramDef(35, "OAD-RAD-PRG", "PRG35-OAD-RAD.bas", "", True,
                       "OA/RA damper modulation with economizer",
                       exec_order=35),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-ECONOMIZER", "Economizer status and lockouts", conditional=True),
        ],

        soo_paragraph="""An airside economizer shall be provided with dry bulb temperature lockout.
The economizer shall be enabled when the outdoor air temperature is below
the high limit setpoint. When enabled, the outside air and return air dampers
shall modulate to provide free cooling. The economizer shall be disabled during
heating mode, optimum start heat, freeze protection, and safety shutdown.""",

        requires=["core"],
        conflicts=["econ-enth", "econ-diff", "econ-diff-db"],
        mutually_exclusive_group="economizer",
    )


def build_econ_enth():
    """Economizer — enthalpy lockout (A201 standard)"""
    return Module(
        id="econ-enth",
        name="Economizer Enthalpy",
        category="economizer",
        description="Economizer with enthalpy-based changeover",

        outputs=[
            OutputPoint(2, "RAD", "AO", "0.0 ->100%", "Return Air Damper (reverse)", 10.0, 2.0, True),
        ],

        values=[
            ValuePoint(72, "ECON-HI-DB-SP",  "AV", 65.0,  "Economizer High DB Lockout SP",  "°F"),
            ValuePoint(73, "ECON-HI-ERH-SP", "AV", 27.0,  "Economizer High Enthalpy SP",    "BTU/lb"),
            ValuePoint(74, "ECON-MODE",       "BV", False, "Economizer Mode Active"),
        ],

        programs=[
            ProgramDef(10, "ECON-MODE-PRG", "PRG10-ECON-ENTH.bas", "", True,
                       "Economizer enthalpy enable/disable",
                       exec_order=10),
            ProgramDef(35, "OAD-RAD-PRG", "PRG35-OAD-RAD.bas", "", True,
                       "OA/RA damper modulation with economizer",
                       exec_order=35),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-ECONOMIZER", "Economizer status and lockouts", conditional=True),
        ],

        soo_paragraph="""An airside economizer shall be provided with enthalpy-based changeover.
The economizer shall be enabled when outdoor air enthalpy is below the
high limit setpoint AND outdoor air dry bulb is below the dry bulb lockout.
When enabled, dampers shall modulate to maintain mixed air temperature
setpoint for free cooling. The economizer additionally compares outdoor
enthalpy to return air enthalpy — if outdoor exceeds return, economizer
shall be disabled.""",

        requires=["core"],
        conflicts=["econ-db", "econ-diff", "econ-diff-db"],
        mutually_exclusive_group="economizer",
    )


def build_econ_diff():
    """Economizer — differential enthalpy"""
    return Module(
        id="econ-diff",
        name="Economizer Differential Enthalpy",
        category="economizer",
        description="Economizer with differential enthalpy (OA vs RA)",

        outputs=[
            OutputPoint(2, "RAD", "AO", "0.0 ->100%", "Return Air Damper (reverse)", 10.0, 2.0, True),
        ],

        values=[
            ValuePoint(74, "ECON-MODE", "BV", False, "Economizer Mode Active"),
        ],

        programs=[
            ProgramDef(10, "ECON-MODE-PRG", "PRG10-ECON-DIFF.bas", "", True,
                       "Economizer differential enthalpy enable/disable",
                       exec_order=10),
            ProgramDef(35, "OAD-RAD-PRG", "PRG35-OAD-RAD.bas", "", True,
                       "OA/RA damper modulation with economizer",
                       exec_order=35),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-ECONOMIZER", "Economizer status and lockouts", conditional=True),
        ],

        soo_paragraph="""An airside economizer shall be provided with differential enthalpy
changeover. The economizer shall be enabled when outdoor air enthalpy is
lower than return air enthalpy. This method compares total heat content
for optimal energy savings.""",

        requires=["core"],
        conflicts=["econ-db", "econ-enth", "econ-diff-db"],
        mutually_exclusive_group="economizer",
    )


def build_econ_diff_db():
    """Economizer — differential dry bulb"""
    return Module(
        id="econ-diff-db",
        name="Economizer Differential Dry Bulb",
        category="economizer",
        description="Economizer with differential dry bulb (OAT vs RAT)",

        outputs=[
            OutputPoint(2, "RAD", "AO", "0.0 ->100%", "Return Air Damper (reverse)", 10.0, 2.0, True),
        ],

        values=[
            ValuePoint(74, "ECON-MODE", "BV", False, "Economizer Mode Active"),
        ],

        programs=[
            ProgramDef(10, "ECON-MODE-PRG", "PRG10-ECON-DIFF-DB.bas", "", True,
                       "Economizer differential dry bulb enable/disable",
                       exec_order=10),
            ProgramDef(35, "OAD-RAD-PRG", "PRG35-OAD-RAD.bas", "", True,
                       "OA/RA damper modulation with economizer",
                       exec_order=35),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-ECONOMIZER", "Economizer status and lockouts", conditional=True),
        ],

        soo_paragraph="""An airside economizer shall be provided with differential dry bulb
changeover. The economizer shall be enabled when outdoor air temperature
is lower than return air temperature. Dampers shall modulate to maintain
mixed air temperature setpoint for free cooling.""",

        requires=["core"],
        conflicts=["econ-db", "econ-enth", "econ-diff"],
        mutually_exclusive_group="economizer",
    )
