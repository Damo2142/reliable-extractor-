"""
SBS Controls — Feature Module: Smoke & Fire Safety

Monitors smoke detector and fire alarm contacts.
On activation: stops all fans, closes all dampers.

Contributes lines to the combined {device-name}-ALARM-PRG program.

Add-on code: SMOKE-FIRE
Applicable: AHU-VAV, AHU-CV, RTU, DOAS, MAU
"""

from app.modules import register_module

module = {
    "id": "mod_smoke_fire",
    "name": "Smoke & Fire Safety Shutdown",
    "feature": "SMOKE-FIRE",
    "category": "safety",
    "requires": [],
    "conflicts": [],
    "exec_order": 80,

    "objects": {
        "BI": [
            {
                "name": "{device-name}-SMOKE",
                "desc": "Duct Smoke Detector (N.O.)",
                "states": {0: "Normal", 1: "Smoke Detected"},
            },
            {
                "name": "{device-name}-FIRE-ALM",
                "desc": "Fire Alarm Shutdown Contact",
                "states": {0: "Normal", 1: "Fire Alarm"},
            },
        ],
    },

    "io_map": {
        "BI4": "{device-name}-SMOKE",
        "BI5": "{device-name}-FIRE-ALM",
    },

    "programs": [
        {
            "name": "{device-name}-ALARM-PRG",
            "description": "Safety Alarms — Smoke and Fire",
            "code": (
                "10 REM ***** SAFETY ALARM PROGRAM *****\n"
                "20 REM SBS Controls — Smoke and Fire Safety\n"
                "30 REM\n"
                "40 REM ── Smoke Detection ──\n"
                "50 IF {device-name}-SMOKE THEN STOP {device-name}-SF-CMD , LET {device-name}-OA-DMP = 0 , END\n"
                "60 REM\n"
                "70 REM ── Fire Alarm ──\n"
                "80 IF {device-name}-FIRE-ALM THEN STOP {device-name}-SF-CMD , LET {device-name}-OA-DMP = 0 , END"
            ),
        },
    ],
}

register_module(module)
