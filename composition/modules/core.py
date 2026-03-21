"""
Core AHU Module — Always present in every AHU build.

Provides: occupancy modes, HVAC modes, SAT/DSP setpoint reset, config program,
          AHU-OK status, safety shutdown aggregation, schedule, base I/O.

Based on A201 reference: PRG1 (CONFIG), PRG3 (OCC-MODES), PRG9 (HVAC-MODE),
PRG12 (SAT-SP), PRG13 (DSP-SP), PRG26 (SAFETY-SD), PRG50 (AHU-OK)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, TrendDef, SystemGroupDef
)


def build():
    return Module(
        id="core",
        name="AHU Core",
        category="core",
        description="Base AHU: occupancy, HVAC modes, SAT/DSP reset, config, status, safety aggregation",
        is_core=True,

        inputs=[
            InputPoint(1, "SF-S",    "BI", "Off/On",        "Supply Fan Status"),
            InputPoint(5, "MAT",     "AI", "10K -40 ->250",  "Mixed Air Temperature",     "°F"),
            InputPoint(6, "SAT",     "AI", "10K -40 ->250",  "Supply Air Temperature",    "°F"),
            InputPoint(7, "RAT",     "AI", "10K -40 ->250",  "Return Air Temperature",    "°F"),
            InputPoint(12,"SA-DSP",  "AI", "Table2",  "Duct Static Pressure",      "WC", "SA-DSP-TBL"),
        ],

        outputs=[
            OutputPoint(1, "OAD", "AO", "0.0 ->100%", "Outside Air Damper", 2.0, 10.0),
        ],

        values=[
            # Network / calculated
            ValuePoint(1,  "NET-OAT",         "AV", 65.0,  "Network OAT from master",            "°F"),
            ValuePoint(2,  "NET-OAH",         "AV", 73.0,  "Network OA humidity",                "%"),
            ValuePoint(3,  "NET-OA-ERH",      "AV", 26.1,  "Network OA enthalpy (calc)",         "BTU/lb"),
            ValuePoint(5,  "RA-ERH",          "AV", 23.4,  "Return air enthalpy (calc)",         "BTU/lb"),
            ValuePoint(6,  "AVG-RM-ERH",      "AV", 22.7,  "Avg room enthalpy (calc)",           "BTU/lb"),
            ValuePoint(7,  "HIGH-RMT",        "AV", 70.4,  "Highest zone temp",                  "°F"),
            ValuePoint(8,  "AVG-RMT",         "AV", 69.1,  "Average zone temp",                  "°F"),
            ValuePoint(9,  "LOW-RMT",         "AV", 68.4,  "Lowest zone temp",                   "°F"),
            ValuePoint(10, "HIGH-SP-DEV",     "AV", 0.6,   "Highest setpoint deviation",         "°F"),
            ValuePoint(11, "LOW-SP-DEV",      "AV", -2.4,  "Lowest setpoint deviation",          "°F"),
            ValuePoint(14, "RMT-SP-LO",       "AV", 68.0,  "Room temp setpoint low",             "°F"),
            ValuePoint(15, "RMT-SP-HI",       "AV", 76.0,  "Room temp setpoint high",            "°F"),
            ValuePoint(16, "MSTR-FIRST-ON",   "AV", "00:00:00", "Master first on time",          "Time"),
            ValuePoint(17, "LOCAL-FIRST-ON",  "AV", "00:00:00", "Local first on time",           "Time"),

            # Modes
            ValuePoint(19, "OCC-MODE",  "MV", 4, "Occupancy Mode", states={1:"Occupied", 2:"Bypass", 3:"Standby", 4:"Unoccupied", 5:"NSB", 6:"NSF", 7:"OSH", 8:"OSC"}),
            ValuePoint(20, "HVAC-MODE", "MV", 2, "HVAC Mode",      states={1:"Vent", 2:"Cool", 3:"Reheat", 4:"Heat", 5:"Init"}),

            # Occupancy control
            ValuePoint(4,  "RESET-SAFETIES",  "BV", False,  "Reset Safeties Command"),
            ValuePoint(22, "NET-OCC-CMD",     "BV", True,   "Network Occupied Command"),
            ValuePoint(23, "USE-LOC-SCHD",    "BV", False,  "Use Local Schedule"),
            ValuePoint(25, "SNOW-DAY",        "BV", False,  "Snow Day Override"),
            ValuePoint(26, "OCC-CMD",         "BV", False,  "Occupancy Command"),
            ValuePoint(27, "BYPASS-REQS",     "AV", 0.0,    "Bypass Requests",                   "#"),
            ValuePoint(28, "BYPASS-REQS-SP",  "AV", 5.0,    "Bypass Request Setpoint",           "#"),
            ValuePoint(29, "BYPASS-MODE",     "BV", False,  "Bypass Mode Active"),

            # Standby
            ValuePoint(38, "STNDBY-MODE",     "BV", False,  "Standby Mode Active"),

            # Night setback
            ValuePoint(39, "NSB-REQS",        "AV", 0.0,    "Night Setback Requests",            "#"),
            ValuePoint(40, "NSB-SP",          "AV", 5.0,    "Night Setback Request SP",          "#"),
            ValuePoint(41, "NSB-MODE",        "BV", False,  "Night Setback Mode Active"),

            # Night set-forward
            ValuePoint(42, "NSF-REQS",        "AV", 0.0,    "Night Set-Forward Requests",        "#"),
            ValuePoint(43, "NSF-SP",          "AV", 5.0,    "Night Set-Forward Request SP",      "#"),
            ValuePoint(44, "NSF-MODE",        "BV", False,  "Night Set-Forward Mode Active"),

            # Zone data
            ValuePoint(45, "AHU-TOT-ZONES",   "AV", 15.0,   "Total Zones Served",                "#"),
            ValuePoint(47, "OCC-MODE-FIRST-ON","AV","00:00:00","Occupancy First On Time",         "Time"),

            # SAT setpoints
            ValuePoint(76, "OSH-SAT-SP",      "AV", 85.0,   "Optimum Start Heat SAT SP",         "°F"),
            ValuePoint(77, "OSC-SAT-SP",      "AV", 55.0,   "Optimum Start Cool SAT SP",         "°F"),
            ValuePoint(79, "HEAT-INITIAL-SAT-SP","AV",60.0,  "Heating Initial SAT SP",            "°F"),
            ValuePoint(80, "COOL-INITIAL-SAT-SP","AV",58.3,  "Cooling Initial SAT SP",            "°F"),
            ValuePoint(81, "INITIAL-SAT-SP",  "AV", 58.3,   "Current Initial SAT SP",            "°F"),
            ValuePoint(82, "SAT-SP-INCR",     "AV", 1.0,    "SAT Reset Increment",               "°F"),
            ValuePoint(83, "SAT-RESET-INTRVL","AV", 5.0,    "SAT Reset Interval",                "Min."),
            ValuePoint(84, "CLG-DMD",         "AV", 0.1,    "Cooling Demand from Zones",         "%"),
            ValuePoint(85, "CLG-DMD-INC-SP",  "AV", 80.0,   "Cooling Demand Increase SP",        "%"),
            ValuePoint(86, "CLG-DMD-DEC-SP",  "AV", 90.0,   "Cooling Demand Decrease SP",        "%"),
            ValuePoint(87, "ACT-SAT-SP",      "AV", 55.0,   "Active SAT Setpoint",               "°F"),

            # DSP setpoints
            ValuePoint(89, "INITIAL-DSP-SP",  "AV", 1.5,    "Initial DSP Setpoint",              "WC"),
            ValuePoint(90, "DSP-SP-INCR",     "AV", 0.1,    "DSP Reset Increment",               "WC"),
            ValuePoint(91, "DSP-RESET-INTRVL","AV", 10.0,   "DSP Reset Interval",                "Min."),
            ValuePoint(92, "ZONE-DMP-POS",    "AV", 100.0,  "Zone Damper Position (highest)",    "%"),
            ValuePoint(93, "ZONE-DMP-INC-SP", "AV", 95.0,   "Zone Damper Increase SP",           "%"),
            ValuePoint(94, "ZONE-DMP-DEC-SP", "AV", 90.0,   "Zone Damper Decrease SP",           "%"),
            ValuePoint(95, "DSP-MIN-SP",      "AV", 1.3,    "DSP Minimum Setpoint",              "WC"),
            ValuePoint(96, "DSP-MAX-SP",      "AV", 1.8,    "DSP Maximum Setpoint",              "WC"),
            ValuePoint(97, "ACT-DSP-SP",      "AV", 0.0,    "Active DSP Setpoint",               "WC"),
            ValuePoint(98, "ACT-DSP",         "AV", 0.0,    "Active DSP Reading",                "WC"),

            # MAT / damper control
            ValuePoint(142,"MAT-SP-OFFSET",   "AV", 3.0,    "MAT SP Offset from SAT SP",         "°F"),
            ValuePoint(143,"ACT-MAT-SP",      "AV", 52.0,   "Active MAT Setpoint",               "°F"),
            ValuePoint(144,"MAT-LL-SP",       "AV", 45.0,   "MAT Low Limit Setpoint",            "°F"),
            ValuePoint(145,"OAD-DELAY",       "AV", 5.0,    "OA Damper Delay After Fan Start",   "Min."),
            ValuePoint(146,"DAMP-RAMP",       "AV", 1.0,    "Damper Ramp Time",                  "Min."),

            # OA flow
            ValuePoint(147,"OA-AREA",         "AV", 6.5,    "OA Duct Cross Section Area",        ""),
            ValuePoint(148,"OA-FLOW-ACT",     "AV", 0.0,    "Actual OA Airflow",                 "CFM"),
            ValuePoint(149,"OA-K-FACTOR",     "AV", 1.7,    "OA K-Factor Correction",            ""),

            # Heating requests from zones
            ValuePoint(108,"HTG-REQS",        "AV", 0.0,    "Heating Requests from Zones",       "#"),

            # Safety shutdown
            ValuePoint(114,"EA-HPS-SD-CMD",   "BV", True,   "EA HPS Shutdown Command"),
            ValuePoint(125,"LTC-SD-CMD",      "BV", True,   "LTC Shutdown Command"),
            ValuePoint(132,"SA-HPS-SD-CMD",   "BV", True,   "SA HPS Shutdown Command"),
            ValuePoint(135,"SAFETY-SD-ALARM", "BV", False,  "Safety Shutdown Alarm Active"),

            # AHU status
            ValuePoint(178,"AHU-OK",          "BV", False,  "AHU Running OK Status"),

            # SAT OAT reset
            ValuePoint(181,"MIN-HTG-OAT-RST", "AV", 0.0,    "Min OAT for Heating Reset",         "°F"),
            ValuePoint(182,"MAX-HTG-OAT-RST", "AV", 60.0,   "Max OAT for Heating Reset",         "°F"),
            ValuePoint(183,"MIN-CLG-OAT-RST", "AV", 60.0,   "Min OAT for Cooling Reset",         "°F"),
            ValuePoint(184,"MAX-CLG-OAT-RST", "AV", 75.0,   "Max OAT for Cooling Reset",         "°F"),
            ValuePoint(185,"MIN-HTG-SAT-RST", "AV", 60.0,   "Min SAT for Heating Reset",         "°F"),
            ValuePoint(186,"MAX-HTG-SAT-RST", "AV", 65.0,   "Max SAT for Heating Reset",         "°F"),
            ValuePoint(187,"MIN-CLG-SAT-RST", "AV", 55.0,   "Min SAT for Cooling Reset",         "°F"),
            ValuePoint(188,"MAX-CLG-SAT-RST", "AV", 60.0,   "Max SAT for Cooling Reset",         "°F"),
        ],

        loops=[
            LoopDef(1, "ACT-DSP-LOOP", "ACT-DSP", "ACT-DSP-SP", "SF-VFD-SPD",
                    p_band=2.0, integral=50.0, action="reverse", description="Duct Static Pressure"),
            LoopDef(2, "MAT-LL-LOOP", "MAT", "MAT-LL-SP", "OAD",
                    p_band=12.0, integral=40.0, action="direct", description="Mixed Air Low Limit"),
            LoopDef(3, "MAT-LOOP", "MAT", "ACT-MAT-SP", "OAD",
                    p_band=12.0, integral=60.0, action="direct", description="Mixed Air Temperature"),
        ],

        tables=[
            TableDef(2, "SA-DSP-TBL", "Volts", "WC",
                     [[0.0, 0.0], [5.0, 2.5], [10.0, 5.0]],
                     "Duct static pressure sensor scaling"),
        ],

        programs=[
            ProgramDef(1, "CONFIG-PRG", "PRG01-CONFIG.bas", "", True,
                       "Configuration — network reads, enthalpy calcs, zone data", exec_order=1),
            ProgramDef(3, "OCC-MODES-PRG", "PRG03-OCC-MODES.bas", "", True,
                       "Occupancy mode determination", exec_order=3),
            ProgramDef(9, "HVAC-MODE-PRG", "PRG09-HVAC-MODE.bas", "", True,
                       "HVAC mode determination (Vent/Cool/Reheat/Heat/Init)", exec_order=9),
            ProgramDef(12, "SAT-SP-PRG", "PRG12-SAT-SP.bas", "", True,
                        "Supply air temperature setpoint reset", exec_order=12),
            ProgramDef(13, "DSP-SP-PRG", "PRG13-DSP-SP.bas", "", True,
                        "Duct static pressure setpoint reset", exec_order=13),
            ProgramDef(26, "SAFETY-SD-PRG", "PRG26-SAFETY-SD.bas", "", True,
                        "Safety shutdown aggregation and reset", exec_order=26),
            ProgramDef(50, "AHU-OK-PRG", "PRG50-AHU-OK.bas", "", True,
                        "AHU running OK status", exec_order=50),
        ],

        schedules=[
            ScheduleDef(1, "LOCAL-SCHEDULE", "Unoccupied",
                        ["Unoccupied", "Occupied"], 10,
                        "Local occupancy schedule"),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-SYSTEM",      "Full AHU schematic with all data points"),
            SystemGroupDef("{device-name}-OCC-MODES",   "Occupancy schedule, modes, bypass, optimum start"),
            SystemGroupDef("{device-name}-HVAC-MODES",  "Heating/cooling/vent mode, lockouts"),
            SystemGroupDef("{device-name}-SET-POINTS",  "All active setpoints"),
            SystemGroupDef("{device-name}-SAFETIES",    "Freeze, smoke, fire, high static, filter"),
            SystemGroupDef("{device-name}-ZONE-DATA",   "Network zone temps, demands, damper positions"),
        ],

        soo_paragraph="""The air handling unit shall be equipped with a direct digital control (DDC) system
providing fully automatic operation. The DDC controller shall monitor all associated
input devices and modulate all output devices to maintain space comfort conditions.

Occupancy modes shall include Occupied, Bypass, Standby, Unoccupied, Night Setback,
Night Set-Forward, Optimum Start Heat, and Optimum Start Cool. Mode transitions
shall be based on schedule, zone requests, and outdoor conditions.

HVAC modes shall include Ventilation, Cooling, Reheat, Heating, and Initialization.
The controller shall automatically select the appropriate mode based on outdoor
conditions, zone demands, and lockout setpoints.

Supply air temperature setpoint shall be reset based on zone cooling demand.
Duct static pressure setpoint shall be reset based on zone damper positions.
Both resets shall use configurable intervals and increments.

The controller shall aggregate all safety conditions (freeze stat, smoke detector,
high static pressure) and initiate a safety shutdown upon any alarm condition.
A manual reset shall be required to restore normal operation after safety shutdown.""",
    )
