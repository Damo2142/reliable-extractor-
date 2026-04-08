"""
VAV Hard-Wired Sensor Module — vav-stat-hardwired (default)

AI3 = RMT (room temp, 10K thermistor).
CFG-PRG copies AI3 reading into AV9 (ACT-RMT).
Standard SST3 wall-mount thermistor sensor.
"""

from composition.models import Module, InputPoint, ProgramDef


_STAT_CODE = """\
REM --- STAT-PRG ---
REM Hard-wired room temp sensor: copy AI reading to AV
ACT-RMT = RMT
"""


def build():
    return Module(
        id="vav-stat-hardwired",
        name="Hard-Wired Sensor (SST3)",
        category="thermostat",
        description="Standard 10K thermistor room temp sensor on AI3",
        is_core=False,

        inputs=[
            InputPoint(3, "RMT", "AI", "10K -40 ->250",
                       "Room Temperature (hard-wired)", "deg.F"),
        ],

        outputs=[],
        values=[],
        loops=[],

        programs=[
            ProgramDef(11, "STAT-PRG", "PRG11-STAT.bas", _STAT_CODE, True,
                       "Hard-wired sensor: copy AI3 to ACT-RMT",
                       exec_order=0),
        ],

        system_groups=[],

        soo_paragraph="""Room temperature shall be sensed by a wall-mounted 10K thermistor
sensor (SST3) hard-wired to the controller analog input.""",

        mutually_exclusive_group="thermostat",
    )
