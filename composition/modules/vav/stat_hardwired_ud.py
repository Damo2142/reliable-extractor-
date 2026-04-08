"""
VAV Hard-Wired Sensor with Setpoint Adjust — vav-stat-hardwired-ud

AI3 = RMT (room temp, 10K thermistor with setpoint dial).
Uses SENSOR-ON / SENSOR-OFF to read both temp and setpoint from SST-UD.
CFG-SST-UD-LO and CFG-SST-UD-HI define the dial range mapping.
"""

from composition.models import Module, InputPoint, ValuePoint, ProgramDef


_STAT_CODE = """\
REM --- STAT-PRG ---
REM SST-UD sensor: read room temp and setpoint dial
REM SENSOR-ON activates reading mode on the 10K input
REM SENSOR-OFF reads the setpoint dial position
REM Dial maps between CFG-SST-UD-LO and CFG-SST-UD-HI
REM
REM --- Read Room Temp ---
SENSOR-ON( RMT )
ACT-RMT = RMT
REM
REM --- Read Setpoint Dial ---
OCC-RMT-SP = SENSOR-OFF( RMT )
OCC-RMT-SP = SLIDE( OCC-RMT-SP, 0.0, 100.0, CFG-SST-UD-LO, CFG-SST-UD-HI )
RMT-SP = OCC-RMT-SP
"""


def build():
    return Module(
        id="vav-stat-hardwired-ud",
        name="Hard-Wired with Setpoint Adjust (SST-UD)",
        category="thermostat",
        description="10K thermistor with setpoint dial — SENSOR-ON/SENSOR-OFF for temp + setpoint",
        is_core=False,

        inputs=[
            InputPoint(3, "RMT", "AI", "10K -40 ->250",
                       "Room Temperature (SST-UD with dial)", "deg.F"),
        ],

        outputs=[],

        values=[
            ValuePoint(101, "CFG-SST-UD-LO", "AV", 65.0, "SST-UD Dial Low Limit",  "deg.F"),
            ValuePoint(102, "CFG-SST-UD-HI", "AV", 80.0, "SST-UD Dial High Limit", "deg.F"),
        ],

        loops=[],

        programs=[
            ProgramDef(11, "STAT-PRG", "PRG11-STAT.bas", _STAT_CODE, True,
                       "SST-UD sensor: SENSOR-ON/SENSOR-OFF for temp + setpoint dial",
                       exec_order=0),
        ],

        system_groups=[],

        soo_paragraph="""Room temperature shall be sensed by a wall-mounted SST-UD sensor
with integral setpoint adjustment dial. The controller shall read both
temperature and setpoint position using SENSOR-ON and SENSOR-OFF
functions. The dial range shall be configurable between low and high
limits.""",

        mutually_exclusive_group="thermostat",
    )
