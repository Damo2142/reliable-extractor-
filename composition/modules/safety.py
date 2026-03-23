"""
Safety Modules — Freeze, Smoke/Fire, High Static, Filter, Condensate Overflow

Based on A201: PRG20 (LTC), PRG23 (SA-HPS), PRG26 (SAFETY-SD)
"""

from composition.models import Module, InputPoint, ValuePoint, ProgramDef


def build_safe_freeze():
    """Low temperature cutout / freeze stat — always present"""
    return Module(
        id="safe-freeze",
        name="Freeze Protection (LTC)",
        category="safety",
        description="Low temperature cutout freeze stat",
        is_core=True,

        inputs=[
            InputPoint(3, "LTC", "BI", "Normal/Alarm", "Low Temperature Cutout"),
        ],

        programs=[
            ProgramDef(20, "LTC-PRG", "PRG20-LTC.bas", "", True,
                       "Low temperature cutout shutdown",
                       exec_order=20),
        ],

        soo_paragraph="""A low temperature cutout (freeze stat) shall be provided in the
mixed air section. Upon activation, the supply fan shall be stopped,
outside air damper closed, and heating valve driven to 100% open.
A manual reset shall be required to restore normal operation.""",

        requires=["core"],
    )


def build_safe_smoke():
    """Duct smoke detector — always present"""
    return Module(
        id="safe-smoke",
        name="Smoke Detector",
        category="safety",
        description="Duct smoke detector monitoring",
        is_core=True,

        inputs=[
            InputPoint(4, "SMOKE", "BI", "Normal/Alarm", "Duct Smoke Detector"),
        ],

        soo_paragraph="""A duct smoke detector shall be provided in the supply air duct.
Upon smoke detection, the supply fan shall be stopped, all dampers
shall close, and a safety shutdown alarm shall be generated.
Manual reset at the detector shall be required.""",

        requires=["core"],
    )


def build_safe_hi_static():
    """Supply air high static pressure switch"""
    return Module(
        id="safe-hi-static",
        name="SA High Static Pressure",
        category="safety",
        description="Supply air high static pressure cutout",

        inputs=[
            InputPoint(13, "SA-HPS", "BI", "Normal/Alarm", "Supply Air High Static Switch"),
        ],

        programs=[
            ProgramDef(23, "SA-HPS-PRG", "PRG23-SA-HPS.bas", "", False,
                       "Supply air high static pressure cutout",
                       exec_order=23),
        ],

        soo_paragraph="""A high static pressure switch shall be provided in the supply duct.
Upon activation, the supply fan shall be stopped and a safety shutdown
alarm generated. A 20-second time delay on return to normal shall prevent
nuisance trips.""",

        requires=["core"],
    )


def build_safe_ea_static():
    """Exhaust air high static pressure switch"""
    return Module(
        id="safe-ea-static",
        name="EA High Static Pressure",
        category="safety",
        description="Exhaust air high static pressure cutout — shuts down unit on trip",

        inputs=[
            InputPoint(15, "EA-HPS", "BI", "Normal/Alarm", "Exhaust Air High Static Switch"),
        ],

        programs=[
            ProgramDef(30, "EA-HPS-PRG", "PRG30-EA-HPS.bas", "", False,
                       "Exhaust air high static pressure cutout",
                       exec_order=30),
        ],

        soo_paragraph="""A high static pressure switch shall be provided in the exhaust duct.
Upon activation, the unit shall be shut down and a safety shutdown
alarm generated. A 20-second time delay on return to normal shall prevent
nuisance trips.""",

        requires=["core"],
    )


def build_safe_ra_static():
    """Return air high static pressure switch"""
    return Module(
        id="safe-ra-static",
        name="RA High Static Pressure",
        category="safety",
        description="Return air high static pressure cutout — shuts down unit on trip",

        inputs=[
            InputPoint(47, "RA-HPS", "BI", "Normal/Alarm", "Return Air High Static Switch"),
        ],

        programs=[
            ProgramDef(31, "RA-HPS-PRG", "PRG31-RA-HPS.bas", "", False,
                       "Return air high static pressure cutout",
                       exec_order=31),
        ],

        soo_paragraph="""A high static pressure switch shall be provided in the return duct.
Upon activation, the unit shall be shut down and a safety shutdown
alarm generated. A 20-second time delay on return to normal shall prevent
nuisance trips.""",

        requires=["core"],
    )


def build_safe_filter():
    """Main filter DP switch — always present"""
    return Module(
        id="safe-filter",
        name="Filter DP Switch",
        category="safety",
        description="Main air filter differential pressure monitoring",
        is_core=True,

        inputs=[
            InputPoint(19, "MA-FILT", "BI", "Clean/Dirty", "Mixed Air Filter DP Switch"),
        ],

        soo_paragraph="""A differential pressure switch shall monitor the air filter.
A dirty filter alarm shall be generated when the filter DP exceeds
the switch setpoint.""",

        requires=["core"],
    )


def build_safe_filter_oa():
    """OA pre-filter DP switch"""
    return Module(
        id="safe-filter-oa",
        name="OA Pre-Filter DP",
        category="safety",
        description="Outside air pre-filter monitoring",

        inputs=[
            InputPoint(25, "OA-FILT", "BI", "Clean/Dirty", "OA Pre-Filter DP Switch"),
        ],

        soo_paragraph="""A differential pressure switch shall monitor the outside air
pre-filter section. A dirty filter alarm shall be generated when
the filter DP exceeds the switch setpoint.""",

        requires=["core"],
    )


def build_safe_filter_final():
    """Final filter DP switch"""
    return Module(
        id="safe-filter-final",
        name="Final Filter DP",
        category="safety",
        description="Final filter monitoring",

        inputs=[
            InputPoint(26, "FINAL-FILT", "BI", "Clean/Dirty", "Final Filter DP Switch"),
        ],

        soo_paragraph="""A differential pressure switch shall monitor the final filter
section. A dirty filter alarm shall be generated when the filter
DP exceeds the switch setpoint.""",

        requires=["core"],
    )


def build_safe_filter_ea():
    """Exhaust filter DP switch"""
    return Module(
        id="safe-filter-ea",
        name="Exhaust Filter DP",
        category="safety",
        description="Exhaust filter monitoring",

        inputs=[
            InputPoint(27, "EA-FILT", "BI", "Clean/Dirty", "Exhaust Filter DP Switch"),
        ],

        soo_paragraph="""A differential pressure switch shall monitor the exhaust air
filter section.""",

        requires=["core"],
    )


def build_safe_fire_sd():
    """Fire shutdown contact"""
    return Module(
        id="safe-fire-sd",
        name="Fire Shutdown",
        category="safety",
        description="Fire alarm shutdown contact",

        inputs=[
            InputPoint(38, "FIRE-SD", "BI", "Normal/Alarm", "Fire Shutdown Contact"),
        ],

        soo_paragraph="""A fire shutdown contact shall be monitored. Upon fire alarm,
the unit shall immediately shut down — supply fan stopped, all
dampers closed. The fire alarm system provides the contact.""",

        requires=["core"],
    )


def build_safe_cond_ovf():
    """Condensate overflow switch"""
    return Module(
        id="safe-cond-ovf",
        name="Condensate Overflow",
        category="safety",
        description="Condensate drain pan overflow switch",

        inputs=[
            InputPoint(36, "COND-OVF", "BI", "Normal/Alarm", "Condensate Overflow Switch"),
        ],

        soo_paragraph="""A condensate overflow switch shall be provided in the drain pan.
Upon overflow detection, cooling shall be disabled and an alarm generated.
The unit may continue to operate in ventilation/heating modes.""",

        requires=["core"],
    )


def build_safe_freeze_dp():
    """Freeze stat DP (across coil face)"""
    return Module(
        id="safe-freeze-dp",
        name="Freeze Stat DP",
        category="safety",
        description="Freeze protection differential pressure across coil face",

        inputs=[
            InputPoint(41, "FREEZE-DP", "BI", "Normal/Alarm", "Freeze Stat DP"),
        ],

        soo_paragraph="""A freeze protection differential pressure switch shall be provided
across the coil face. This provides a secondary layer of freeze protection
independent of the low temperature cutout thermostat.""",

        requires=["core"],
    )
