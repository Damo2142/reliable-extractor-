"""
VAV Communicating Stat Occupancy Add-on — vav-stat-comm-occ

Adds PIR occupancy detection from SS3 for bypass/standby logic.
BV90=SS3-OCC. Triggers bypass mode when motion detected while unoccupied.
Requires: vav-stat-comm
"""

from composition.models import Module, ValuePoint, ProgramDef


_OCC_CODE = """\
REM --- OCC-DETECT-PRG ---
REM PIR occupancy from SMART-Sensor SS3
REM Trigger bypass mode when motion detected while unoccupied
REM
IF OCC-MODE <> 4 THEN GOTO 999
REM
REM --- Unoccupied + Motion Detected ---
IF SS3-OCC THEN BYPASS = 1
REM
999 REM End
"""


def build():
    return Module(
        id="vav-stat-comm-occ",
        name="Occupancy Sensor (PIR)",
        category="thermostat-addon",
        description="PIR occupancy detection from SMART-Sensor SS3 — triggers bypass on motion",
        is_core=False,

        inputs=[],
        outputs=[],

        values=[
            ValuePoint(90, "SS3-OCC", "BV", False, "PIR Occupancy (from SS3)"),
        ],

        loops=[],

        programs=[
            ProgramDef(13, "OCC-DETECT-PRG", "PRG13-OCC-DETECT.bas", _OCC_CODE, True,
                       "PIR occupancy: trigger bypass on motion while unoccupied",
                       exec_order=13),
        ],

        system_groups=[],

        soo_paragraph="""The SMART-Sensor SS3 shall include an integral PIR occupancy sensor.
When motion is detected in the zone while the unit is in unoccupied mode,
the controller shall transition to bypass mode to provide temporary
comfort conditioning.""",

        requires=["vav-stat-comm"],
    )
