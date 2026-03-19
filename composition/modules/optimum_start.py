"""
Optimum Start Module

Based on A201: PRG2 (OSH-OSC-MODE), PRG4 (NP-MODE)
"""

from composition.models import Module, ValuePoint, ProgramDef


def build():
    return Module(
        id="opt-start",
        name="Optimum Start Heat/Cool",
        category="optimum-start",
        description="Optimum start heating and cooling with night purge",

        values=[
            # OSH
            ValuePoint(30, "OSH-RAT-SP",        "AV", 68.0,  "OSH RAT Setpoint",          "°F"),
            ValuePoint(31, "OSH-MAX-PRESTART",   "AV", 120.0, "OSH Max Pre-Start Time",    "Min."),
            ValuePoint(32, "OSH-MIN-RUNTIME",    "AV", 30.0,  "OSH Min Runtime",           "Min."),
            ValuePoint(33, "OSH-MODE",           "BV", False, "OSH Mode Active"),

            # OSC
            ValuePoint(34, "OSC-RAT-SP",         "AV", 77.0,  "OSC RAT Setpoint",          "°F"),
            ValuePoint(35, "OSC-MAX-PRESTART",   "AV", 120.0, "OSC Max Pre-Start Time",    "Min."),
            ValuePoint(36, "OSC-MIN-RUNTIME",    "AV", 30.0,  "OSC Min Runtime",           "Min."),
            ValuePoint(37, "OSC-MODE",           "BV", False, "OSC Mode Active"),

            # Night Purge
            ValuePoint(48, "NP-FIRST-START",     "AV", "00:00:00", "Night Purge First Start",  "Time"),
            ValuePoint(49, "NP-MAX-RT",          "AV", 120.0,     "Night Purge Max Runtime",   "Min."),
            ValuePoint(50, "NP-MODE",            "BV", False,     "Night Purge Mode Active"),
        ],

        programs=[
            ProgramDef(2, "OSH-OSC-MODE-PRG", "PRG02-OSH-OSC-MODE.bas", "", True,
                       "Optimum start heat/cool mode determination",
                       exec_order=2),
            ProgramDef(4, "NP-MODE-PRG", "PRG04-NP-MODE.bas", "", True,
                       "Night purge mode determination",
                       exec_order=4),
        ],

        soo_paragraph="""Optimum start heating (OSH) and optimum start cooling (OSC) shall
be provided. Pre-start time shall be calculated based on outdoor conditions
and zone setpoint deviation. OSH shall pre-heat the building before occupancy
when heating is required. OSC shall pre-cool when cooling is required.
Minimum runtime shall be enforced once optimum start is activated.

Night purge mode shall be available to pre-condition the building using
outdoor air when enthalpy conditions are favorable, prior to the optimum
start window. Night purge shall be disabled during snow days.""",

        requires=["core"],
    )
