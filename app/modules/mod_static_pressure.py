"""
SBS Controls — Feature Module: Duct Static Pressure Control

PID control of duct static pressure using a LOOP object.
LOOP output drives supply fan VFD speed.

Program:
    {device-name}-DSP-PRG — Static pressure control via LOOP + LIMIT

Add-on code: DSP
Applicable: AHU-VAV (required for VAV systems)
Requires: mod_vfd_supply_fan
"""

from app.modules import register_module

module = {
    "id": "mod_static_pressure",
    "name": "Duct Static Pressure Control",
    "feature": "DSP",
    "category": "pressure",
    "requires": ["mod_vfd_supply_fan"],
    "conflicts": [],
    "exec_order": 70,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-DSP",
                "desc": "Duct Static Pressure",
                "units": "inwc",
                "min": 0,
                "max": 5.0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-DSP-SP",
                "desc": "Duct Static Pressure Setpoint",
                "units": "inwc",
                "min": 0.3,
                "max": 3.0,
                "default": 1.5,
            },
        ],
        "LOOP": [
            {
                "name": "{device-name}-DSP-LOOP",
                "desc": "Duct Static Pressure PID Loop",
                "units": "percent",
            },
        ],
    },

    "io_map": {
        "UI7": "{device-name}-DSP",
    },

    "programs": [
        {
            "name": "{device-name}-DSP-PRG",
            "description": "Duct Static Pressure — Fan Speed PID via LOOP",
            "code": (
                "10 REM ***** DUCT STATIC PRESSURE PROGRAM *****\n"
                "20 REM SBS Controls — PID control via LOOP object\n"
                "30 REM LOOP input = DSP sensor, setpoint = DSP-SP\n"
                "40 REM LOOP output drives SF-SPD through LIMIT\n"
                "50 REM\n"
                "60 REM ── Only run when fan is commanded on ──\n"
                "70 IF NOT {device-name}-SF-CMD THEN LET {device-name}-SF-SPD = 0 , END\n"
                "80 REM\n"
                "90 REM ── Drive fan speed from LOOP output ──\n"
                "100 REM LOOP object handles PID internally\n"
                "110 REM Clamp output between min and max fan speed\n"
                "120 LET {device-name}-SF-SPD = LIMIT( {device-name}-DSP-LOOP , {device-name}-SF-MIN-SPD , {device-name}-SF-MAX-SPD )\n"
                "130 REM\n"
                "140 REM ── High static pressure alarm ──\n"
                "150 LET A = {device-name}-DSP-SP * 1.5\n"
                "160 DALARM {device-name}-DSP > A , 30 , High duct static pressure\n"
                "170 REM\n"
                "180 REM ── Low static alarm (fan running but no pressure) ──\n"
                "190 LET B = {device-name}-SF-SPD > 50\n"
                "200 DALARM ( {device-name}-DSP < 0.1 ) AND B , 60 , Low duct static pressure\n"
                "210 END"
            ),
        },
    ],
}

register_module(module)
