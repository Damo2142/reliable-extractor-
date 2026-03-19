"""
SBS Controls — Feature Module: VFD Supply Fan

Variable frequency drive speed control for supply fan.
Uses proper Control-BASIC START/STOP and DALARM for fan failure.

Program:
    {device-name}-SF-PRG — Supply fan VFD control, start/stop, alarms

Add-on code: SF-VFD
Applicable: AHU-VAV, RTU-VAV
Conflicts with: mod_cs_supply_fan (constant speed fan)
"""

from app.modules import register_module

module = {
    "id": "mod_vfd_supply_fan",
    "name": "VFD Supply Fan Control",
    "feature": "SF-VFD",
    "category": "fan",
    "requires": [],
    "conflicts": ["mod_cs_supply_fan"],
    "exec_order": 30,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-SF-SPD-FB",
                "desc": "Supply Fan VFD Speed Feedback",
                "units": "percent",
                "min": 0,
                "max": 100,
            },
        ],
        "AO": [
            {
                "name": "{device-name}-SF-SPD",
                "desc": "Supply Fan VFD Speed Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-SF-MIN-SPD",
                "desc": "Supply Fan Minimum Speed",
                "units": "percent",
                "min": 10,
                "max": 50,
                "default": 20.0,
            },
            {
                "name": "{device-name}-SF-MAX-SPD",
                "desc": "Supply Fan Maximum Speed",
                "units": "percent",
                "min": 50,
                "max": 100,
                "default": 100.0,
            },
        ],
        "BI": [
            {
                "name": "{device-name}-VFD-FLT",
                "desc": "Supply Fan VFD Fault",
                "states": {0: "Normal", 1: "Fault"},
            },
        ],
    },

    "io_map": {
        "UI6": "{device-name}-SF-SPD-FB",
        "UO4": "{device-name}-SF-SPD",
        "BI2": "{device-name}-VFD-FLT",
    },

    "programs": [
        {
            "name": "{device-name}-SF-PRG",
            "description": "Supply Fan VFD Control",
            "code": (
                "10 REM ***** SUPPLY FAN VFD PROGRAM *****\n"
                "20 REM SBS Controls — VFD Speed Control and Alarms\n"
                "30 REM\n"
                "40 REM ── VFD fault: stop fan immediately ──\n"
                "50 IF {device-name}-VFD-FLT THEN STOP {device-name}-SF-CMD , LET {device-name}-SF-SPD = 0 , END\n"
                "60 REM\n"
                "70 REM ── Emergency stop ──\n"
                "80 IF {device-name}-EMER-STOP THEN STOP {device-name}-SF-CMD , LET {device-name}-SF-SPD = 0 , END\n"
                "90 REM\n"
                "100 REM ── Occupied or Bypass: start fan ──\n"
                "110 IF {device-name}-OCC-MODE = 1 THEN START {device-name}-SF-CMD\n"
                "120 IF {device-name}-OCC-MODE = 2 THEN START {device-name}-SF-CMD\n"
                "130 REM\n"
                "140 REM ── Off, Standby, or Unoccupied: stop fan ──\n"
                "150 IF {device-name}-OCC-MODE = 0 THEN STOP {device-name}-SF-CMD , LET {device-name}-SF-SPD = 0 , END\n"
                "160 IF {device-name}-OCC-MODE = 3 THEN STOP {device-name}-SF-CMD , LET {device-name}-SF-SPD = 0 , END\n"
                "170 IF {device-name}-OCC-MODE = 4 THEN STOP {device-name}-SF-CMD , LET {device-name}-SF-SPD = 0 , END\n"
                "180 REM\n"
                "190 REM ── Set default speed if no pressure module overrides ──\n"
                "200 REM Static pressure module will override SF-SPD via DSP-LOOP\n"
                "210 IF {device-name}-SF-SPD < {device-name}-SF-MIN-SPD THEN LET {device-name}-SF-SPD = {device-name}-SF-MIN-SPD\n"
                "220 REM\n"
                "230 REM ── Clamp speed to min/max ──\n"
                "240 LET {device-name}-SF-SPD = LIMIT( {device-name}-SF-SPD , {device-name}-SF-MIN-SPD , {device-name}-SF-MAX-SPD )\n"
                "250 REM\n"
                "260 REM ── Fan failure alarm: status not following command ──\n"
                "270 DALARM {device-name}-SF-CMD <> {device-name}-SF-STS , 90 , Supply fan failure\n"
                "280 REM\n"
                "290 REM ── VFD fault alarm ──\n"
                "300 ALARM {device-name}-VFD-FLT , 0 , VFD fault\n"
                "310 END"
            ),
        },
    ],
}

register_module(module)
