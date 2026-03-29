"""
HW-PLANT Core Module — Always present in every HW plant build.

Provides: system enable, OA reset logic, HW supply/return temps,
          OAT/OAH monitoring, network valve position feedback,
          schedule, config program, setpoint program.

I/O Map:
  IN1  = HWS-T   (AI)  Hot Water Supply Temp
  IN2  = HWR-T   (AI)  Hot Water Return Temp
  IN3  = OAT     (AI)  Outside Air Temperature (if hardwired)
  IN4  = OAH     (AI)  Outside Air Humidity (if hardwired)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, TrendDef, SystemGroupDef
)


def build():
    return Module(
        id="hw-core",
        name="HW Plant Core",
        category="hw-core",
        description="Base HW plant: system enable, OA reset, supply/return temps, config, schedule",
        is_core=True,

        inputs=[
            InputPoint(1, "HWS-T",  "AI", "10K -40 ->250", "Hot Water Supply Temperature", "°F"),
            InputPoint(2, "HWR-T",  "AI", "10K -40 ->250", "Hot Water Return Temperature", "°F"),
            InputPoint(3, "OAT",    "AI", "10K -40 ->250", "Outside Air Temperature",      "°F"),
            InputPoint(4, "OAH",    "AI", "0 ->100% (0-5V)", "Outside Air Humidity",        "%"),
        ],

        outputs=[],

        values=[
            # Network weather data (from master or hardwired)
            ValuePoint(1,  "NET-OAT",           "AV", 65.0,  "Network OA Temperature",       "°F"),
            ValuePoint(2,  "NET-OAH",           "AV", 50.0,  "Network OA Humidity",           "%"),
            ValuePoint(3,  "NET-OA-ERH",        "AV", 26.1,  "Network OA Enthalpy (calc)",    "BTU/lb"),

            # System enable / status
            ValuePoint(4,  "HW-SYS-ENAB",       "BV", False, "HW System Enable"),
            ValuePoint(5,  "HW-AVAIL",          "BV", False, "HW Available (to AHUs)"),
            ValuePoint(6,  "ALARM-INHIBIT",     "BV", False, "Alarm Inhibit"),

            # OA Reset setpoints
            ValuePoint(7,  "ACT-HWS-TEMP-SP",   "AV", 160.0, "Active HW Supply Temp Setpoint", "°F"),
            ValuePoint(8,  "CFG-RESET-OA-MIN",  "AV", 0.0,   "OA Reset Min OAT",              "°F"),
            ValuePoint(9,  "CFG-RESET-OA-MAX",  "AV", 60.0,  "OA Reset Max OAT",              "°F"),
            ValuePoint(10, "CFG-RESET-HW-MIN",  "AV", 140.0, "OA Reset Min HW Temp",          "°F"),
            ValuePoint(11, "CFG-RESET-HW-MAX",  "AV", 180.0, "OA Reset Max HW Temp",          "°F"),
            ValuePoint(12, "CFG-HHW-OA-ENAB-SP","AV", 65.0,  "OA Temp Enable Setpoint",       "°F"),

            # Network valve position feedback (from AHU HW valves)
            ValuePoint(13, "NET-HWV-POS-MIN",   "AV", 0.0,   "Network HW Valve Position Min", "%"),
            ValuePoint(14, "NET-HWV-POS-MAX",   "AV", 0.0,   "Network HW Valve Position Max", "%"),
            ValuePoint(15, "NET-HWV-POS-AVG",   "AV", 0.0,   "Network HW Valve Position Avg", "%"),
            ValuePoint(16, "HHW-OA-RESET",      "AV", 0.0,   "OA Reset Output",               "°F"),
            ValuePoint(17, "HHW-HWV-OFFSET",    "AV", 0.0,   "Valve Position Offset",         "°F"),

            # HW system status
            ValuePoint(18, "HWS-HWP-STOP-DELAY","AV", 120.0, "Pump Stop Delay After Disable", "Sec"),
            ValuePoint(19, "HW-DELTA-T",        "AV", 0.0,   "HW Supply-Return Delta T",      "°F"),
            ValuePoint(20, "RESET-SAFETIES",     "BV", False, "Reset Safeties Command"),
        ],

        loops=[],

        tables=[],

        programs=[
            ProgramDef(1, "HW-CONFIG-PRG", "HW-PRG01-CONFIG.bas", "", True,
                       "Configuration — network reads, enthalpy calc, system enable", "hw-core", exec_order=1),
            ProgramDef(2, "HW-SPT-PRG", "HW-PRG02-SPT.bas", "", True,
                       "HW supply temp setpoint — OA reset with valve feedback", "hw-core", exec_order=2),
            ProgramDef(5, "HW-STATUS-PRG", "HW-PRG05-STATUS.bas", "", True,
                       "System status — HW available flag, delta T calc", "hw-core", exec_order=5),
        ],

        schedules=[
            ScheduleDef(1, "{device-name}-LOCAL-SCHEDULE", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10,
                        "Local occupancy schedule for HW plant"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM",     "HW Plant overview — temps, enables, status"),
            SystemGroupDef("{device-name}-SET-POINTS",  "All setpoints and configuration"),
            SystemGroupDef("{device-name}-SAFETIES",    "Alarms, faults, availability"),
        ],

        soo_paragraph="""The hot water plant controller shall monitor hot water supply and return
temperatures, outside air conditions, and network valve position feedback from served
air handling units. The hot water supply temperature setpoint shall be reset based on
outside air temperature between configurable min/max limits. Valve position feedback
from network AHUs shall provide trim-and-respond offset to optimize supply temperature.
The system shall enable when outside air temperature falls below the configurable
enable setpoint and at least one served AHU requires heating.""",
    )
