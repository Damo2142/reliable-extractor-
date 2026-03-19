"""
SBS Controls — Feature Module: Freeze Protection

Monitors freeze stat contact using DALARM. On trip: closes OA damper,
opens HW valve to 100%, stops fan. Critical safety override.

Contributes lines to the combined {device-name}-ALARM-PRG program.

Add-on code: FREEZE
Applicable: AHU-VAV, AHU-CV, RTU, DOAS
"""

from app.modules import register_module

module = {
    "id": "mod_freeze_protect",
    "name": "Freeze Protection",
    "feature": "FREEZE",
    "category": "safety",
    "requires": [],
    "conflicts": [],
    "exec_order": 80,

    "objects": {
        "BI": [
            {
                "name": "{device-name}-FREEZE",
                "desc": "Freeze Stat Contact (N.C.)",
                "states": {0: "Normal", 1: "Freeze"},
            },
        ],
    },

    "io_map": {
        "BI3": "{device-name}-FREEZE",
    },

    "programs": [
        {
            "name": "{device-name}-ALARM-PRG",
            "description": "Safety Alarms — Freeze Protection",
            "code": (
                "10 REM ***** SAFETY ALARM PROGRAM *****\n"
                "20 REM SBS Controls — Freeze / Smoke / Fire / Filter Alarms\n"
                "30 REM\n"
                "40 REM ── Freeze Protection ──\n"
                "50 DALARM {device-name}-FREEZE , 10 , Freeze stat tripped\n"
                "60 IF {device-name}-FREEZE THEN STOP {device-name}-SF-CMD , LET {device-name}-SF-SPD = 0\n"
                "70 IF {device-name}-FREEZE THEN LET {device-name}-OA-DMP = 0 , LET {device-name}-HW-VLV = 100 , END"
            ),
        },
    ],
}

register_module(module)
