"""
SBS Controls — Feature Module: Filter Differential Pressure

Monitors filter differential pressure switch for dirty filter alarm
using DALARM with 300-second delay.

Contributes lines to the combined {device-name}-ALARM-PRG program.

Add-on code: FLTR-DP
Applicable: AHU-VAV, AHU-CV, RTU, DOAS, MAU
"""

from app.modules import register_module

module = {
    "id": "mod_filter_dp",
    "name": "Filter Differential Pressure Monitor",
    "feature": "FLTR-DP",
    "category": "alarm",
    "requires": [],
    "conflicts": [],
    "exec_order": 90,

    "objects": {
        "BI": [
            {
                "name": "{device-name}-FLTR-STS",
                "desc": "Filter Dirty Status (DP Switch)",
                "states": {0: "Clean", 1: "Dirty"},
            },
        ],
    },

    "io_map": {
        "BI6": "{device-name}-FLTR-STS",
    },

    "programs": [
        {
            "name": "{device-name}-ALARM-PRG",
            "description": "Safety Alarms — Filter DP",
            "code": (
                "10 REM ***** SAFETY ALARM PROGRAM *****\n"
                "20 REM SBS Controls — Filter Dirty Alarm\n"
                "30 REM\n"
                "40 REM ── Filter Dirty Alarm (5 min delay) ──\n"
                "50 DALARM {device-name}-FLTR-STS , 300 , Filter dirty"
            ),
        },
    ],
}

register_module(module)
