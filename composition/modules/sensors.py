"""
Generic Shared Sensor Modules — vendor-neutral, family-neutral.

These modules are referenced by multiple equipment families (UV, VAV,
CV-AHU, RTU, ...). Build once, reference everywhere — any change here
applies to every family that uses them.

  stat-remote — Remote Space Temp (Network Read). Room temp comes from
                another controller via BACnet instead of a wired AI.
                Category: thermostat (mutually exclusive with the other
                thermostat sensor options).

High instance band (150+) is used to stay clear of family core points
and the locked VAV zone-data / AHU-publish ranges.
"""

from composition.models import Module, ValuePoint, ProgramDef


# ═══════════════════════════════════════════════════════════════════════════
#  stat-remote — Remote Space Temp (Network Read)
# ═══════════════════════════════════════════════════════════════════════════

_STAT_REMOTE = """\
REM --- STAT-REMOTE ---
REM Remote space temp via BACnet network read.
REM One unit (a VAV or another UV) owns the wired sensor and shares it;
REM this unit reads it instead of having its own hardwired RMT sensor.
REM Source = {parent} controller, AV instance per NET-RMT-SRC-INST.
REM Default AV9 (VAV ACT-RMT convention). Tech sets {parent} and the
REM source instance to match the owning unit at commissioning.
REM
NET-RMT = {parent}AV9
ACT-RMT = NET-RMT
REM Comms health: OK while the network value is plausible
IF NET-RMT > -40 AND NET-RMT < 200 THEN NET-RMT-OK = 1 ELSE NET-RMT-OK = 0
"""


def build_stat_remote():
    """Remote space temp via BACnet — no hardwired RMT input."""
    return Module(
        id="stat-remote",
        name="Remote Space Temp (Network Read)",
        category="thermostat",
        description="Room temp read from another controller via BACnet — no hardwired RMT sensor",
        is_core=False,

        inputs=[],
        outputs=[],
        values=[
            ValuePoint(150, "NET-RMT",          "AV", 72.0, "Network Room Temp",            "°F"),
            ValuePoint(151, "NET-RMT-SRC-INST", "AV", 9.0,  "Network RMT Source AV Instance"),
            ValuePoint(150, "NET-RMT-OK",       "BV", True, "Network RMT Comms OK"),
        ],
        loops=[],

        programs=[
            ProgramDef(11, "STAT-REMOTE", "PRG11-STAT-REMOTE.bas", _STAT_REMOTE, True,
                       "Remote space temp via BACnet network read", exec_order=0),
        ],

        system_groups=[],

        soo_paragraph="""Room temperature shall be read from an associated controller (a VAV
terminal or another unit ventilator) over the BACnet network. The unit
shall not require its own hard-wired room temperature sensor. The source
controller and object instance shall be configured at commissioning. Loss
of the network value shall be annunciated.""",

        mutually_exclusive_group="thermostat",
    )
