"""
CHW-PLANT Core Module — Always present in every CHW plant build.

Provides: system enable, OA reset logic, CHW supply/return temps,
          OAT/OAH monitoring, flow sensor, network valve position feedback,
          runtime tracking, delta-T monitoring, schedule, config program.

I/O Map:
  IN1  = CHWS-T   (AI)  CHW Supply Temp
  IN2  = CHWR-T   (AI)  CHW Return Temp
  IN3  = OAT      (AI)  Outside Air Temperature
  IN4  = OAH      (AI)  Outside Air Humidity
  IN5  = CHW-FLOW (AI)  CHW System Flow
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, TrendDef, SystemGroupDef
)


def build():
    return Module(
        id="chw-core",
        name="CHW Plant Core",
        category="chw-core",
        description="Base CHW plant: system enable, OA reset, supply/return temps, flow, delta-T monitoring",
        is_core=True,

        inputs=[
            InputPoint(1, "CHWS-T",   "AI", "10K -40 ->250", "CHW Supply Temperature",    "°F"),
            InputPoint(2, "CHWR-T",   "AI", "10K -40 ->250", "CHW Return Temperature",    "°F"),
            InputPoint(3, "OAT",      "AI", "10K -40 ->250", "Outside Air Temperature",   "°F"),
            InputPoint(4, "OAH",      "AI", "0 ->100% (0-5V)", "Outside Air Humidity",    "%"),
            InputPoint(5, "CHW-FLOW", "AI", "0 ->100% (0-5V)", "CHW System Flow",         "GPM"),
        ],

        outputs=[],

        values=[
            # Network weather data
            ValuePoint(1,  "NET-OAT",           "AV", 65.0,  "Network OA Temperature",        "°F"),
            ValuePoint(2,  "NET-OAH",           "AV", 50.0,  "Network OA Humidity",            "%"),
            ValuePoint(3,  "NET-OA-ERH",        "AV", 26.1,  "Network OA Enthalpy (calc)",     "BTU/lb"),

            # System enable / status
            ValuePoint(4,  "CHW-SYS-ENAB",      "BV", False, "CHW System Enable"),
            ValuePoint(5,  "CHW-AVAIL",         "BV", False, "CHW Available (to AHUs)"),
            ValuePoint(6,  "ALARM-INHIBIT",     "BV", False, "Alarm Inhibit"),

            # CHW supply temp setpoint and OA reset config
            ValuePoint(7,  "ACT-CHWS-TEMP-SP",  "AV", 44.0,  "Active CHW Supply Temp Setpoint","°F"),
            ValuePoint(8,  "CFG-RESET-OA-MIN",  "AV", 55.0,  "OA Reset Min OAT",              "°F"),
            ValuePoint(9,  "CFG-RESET-OA-MAX",  "AV", 90.0,  "OA Reset Max OAT",              "°F"),
            ValuePoint(10, "CFG-CHWS-MIN",      "AV", 42.0,  "Min CHW Supply Temp",            "°F"),
            ValuePoint(11, "CFG-CHWS-MAX",      "AV", 55.0,  "Max CHW Supply Temp",            "°F"),
            ValuePoint(12, "CFG-OAT-ENBL-SP",   "AV", 55.0,  "OAT Enable Setpoint",           "°F"),
            ValuePoint(13, "CFG-OAT-ENBL-DB",   "AV", 3.0,   "OAT Enable Deadband",           "°F"),

            # Network valve position feedback (from AHU CHW valves)
            ValuePoint(14, "NET-CHV-POS-MIN",   "AV", 0.0,   "Network CHW Valve Position Min", "%"),
            ValuePoint(15, "NET-CHV-POS-MAX",   "AV", 0.0,   "Network CHW Valve Position Max", "%"),
            ValuePoint(16, "NET-CHV-POS-AVG",   "AV", 0.0,   "Network CHW Valve Position Avg", "%"),

            # Valve-position-based system enable thresholds
            ValuePoint(17, "VLV-SYS-ENABLE-SP", "AV", 10.0,  "Valve Pos Enable Threshold",    "%"),
            ValuePoint(18, "VLV-SYS-DISABLE-SP","AV", 2.0,   "Valve Pos Disable Threshold",   "%"),

            # Supply temp reset via valve feedback
            ValuePoint(19, "MAX-CHW-VLV-SP",    "AV", 75.0,  "Target Max Valve Position",     "%"),
            ValuePoint(20, "MAX-CHW-VLV-RST-INT","AV", 10.0, "Valve Reset Eval Interval",     "Min"),

            # Calculated values
            ValuePoint(75, "CHW-OA-RESET",      "AV", 0.0,   "OA Reset Output",               "°F"),
            ValuePoint(76, "CHW-VLV-OFFSET",    "AV", 0.0,   "Valve Position Offset",         "°F"),
            ValuePoint(77, "CHW-DELTA-T",       "AV", 0.0,   "CHW Supply-Return Delta T",     "°F"),
            ValuePoint(78, "RESET-SAFETIES",    "BV", False,  "Reset Safeties Command"),

            # Delta-T alarm
            ValuePoint(79, "LOW-DELTA-T",       "BV", False,  "Low Delta-T Alarm"),
            ValuePoint(80, "LOW-DELTA-T-SP",    "AV", 3.0,    "Low Delta-T Alarm Setpoint",    "°F"),

            # Pump config
            ValuePoint(81, "CHWP-STOP-DELAY",   "AV", 30.0,  "Pump Stop Delay",               "Sec"),
            ValuePoint(82, "CHWP-ROTATION-HOLD","AV", 168.0,  "Min Hours Before Pump Rotation","Hrs"),

            # Flow totalization
            ValuePoint(83, "CHW-FLOW-TTL",      "AV", 0.0,   "CHW Flow Totalization",         "Gal"),

            # System-wide pump status
            ValuePoint(84, "ANY-CHWP-ON",       "BV", False,  "Any CHW Pump Running"),
        ],

        loops=[],
        tables=[],

        programs=[
            ProgramDef(1, "CHW-CONFIG-PRG", "CHW-PRG01-CONFIG.bas", "", True,
                       "Configuration — network reads, enthalpy, flow, runtime tracking", "chw-core", exec_order=1),
            ProgramDef(2, "CHW-SPT-PRG", "CHW-PRG02-SPT.bas", "", True,
                       "CHW supply temp setpoint — OA reset with valve feedback", "chw-core", exec_order=2),
            ProgramDef(5, "CHW-STATUS-PRG", "CHW-PRG05-STATUS.bas", "", True,
                       "System status — CHW available, delta-T monitoring, enable logic", "chw-core", exec_order=5),
        ],

        schedules=[
            ScheduleDef(1, "{device-name}-LOCAL-SCHEDULE", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10,
                        "Local occupancy schedule for CHW plant"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM",     "CHW Plant overview — temps, enables, status, flow"),
            SystemGroupDef("{device-name}-SET-POINTS",  "All setpoints and configuration"),
            SystemGroupDef("{device-name}-SAFETIES",    "Alarms, faults, availability"),
        ],

        soo_paragraph="""The chilled water plant controller shall monitor CHW supply and return
temperatures, system flow, outside air conditions, and network valve position feedback
from served air handling units. The CHW supply temperature setpoint shall be reset
based on outside air temperature between configurable min/max limits. Valve position
feedback from network AHUs provides trim-and-respond offset — when no AHU data is
available (NET-CHV-POS-MAX = 0), the system falls back to OA-reset-only mode.
The system shall enable when outside air temperature rises above the configurable
enable setpoint and max AHU valve position exceeds the valve enable threshold.
CHW availability to served AHUs requires system enabled, pump proven running, and
supply temperature below 55°F. Low delta-T alarm activates when supply-return delta-T
drops below 3°F while pumps are running.""",
    )
