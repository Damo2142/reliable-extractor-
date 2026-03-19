"""
SBS Controls — Feature Module: Dry Bulb Economizer

Dry bulb economizer control using proper Control-BASIC SLIDE().
Compares OAT to high limit and RAT to determine free cooling.
Modulates OA damper with SLIDE based on MAT vs SAT-SP.

Program:
    {device-name}-ECON-PRG — Economizer control with SLIDE() modulation

Add-on code: ECON-DB
Applicable: AHU-VAV, AHU-CV, RTU
"""

from app.modules import register_module

module = {
    "id": "mod_economizer_db",
    "name": "Economizer - Dry Bulb",
    "feature": "ECON-DB",
    "category": "economizer",
    "requires": [],
    "conflicts": ["mod_economizer_enth"],
    "exec_order": 40,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-MAT",
                "desc": "Mixed Air Temperature",
                "units": "deg-f",
                "min": -20,
                "max": 150,
            },
        ],
        "AO": [
            {
                "name": "{device-name}-OA-DMP",
                "desc": "Outdoor Air Damper Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-CFG-ECON-HI-LIMIT",
                "desc": "Economizer High Limit Switchover Temp",
                "units": "deg-f",
                "min": 50,
                "max": 75,
                "default": 65.0,
            },
            {
                "name": "{device-name}-MIN-OA",
                "desc": "Minimum Outdoor Air Damper Position",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 15.0,
            },
        ],
        "BV": [
            {
                "name": "{device-name}-ECON-ENA",
                "desc": "Economizer Enabled Status",
                "states": {0: "Disabled", 1: "Enabled"},
                "default": 0,
            },
        ],
    },

    "io_map": {
        "UI5": "{device-name}-MAT",
        "UO3": "{device-name}-OA-DMP",
    },

    "programs": [
        {
            "name": "{device-name}-ECON-PRG",
            "description": "Economizer — Dry Bulb Free Cooling",
            "code": (
                "10 REM ***** ECONOMIZER PROGRAM *****\n"
                "20 REM SBS Controls — Dry Bulb Economizer Control\n"
                "30 REM Compare OAT to high limit and RAT for free cooling\n"
                "40 REM\n"
                "50 REM ── Fan must be running ──\n"
                "60 IF NOT {device-name}-SF-STS THEN LET {device-name}-OA-DMP = 0 , STOP {device-name}-ECON-ENA , END\n"
                "70 REM\n"
                "80 REM ── Check economizer enable: OAT < high limit AND OAT < RAT ──\n"
                "90 LET A = {device-name}-OAT\n"
                "100 LET B = {device-name}-CFG-ECON-HI-LIMIT\n"
                "110 LET C = {device-name}-RAT\n"
                "120 IF A >= B THEN STOP {device-name}-ECON-ENA , LET {device-name}-OA-DMP = {device-name}-MIN-OA , END\n"
                "130 IF A >= C THEN STOP {device-name}-ECON-ENA , LET {device-name}-OA-DMP = {device-name}-MIN-OA , END\n"
                "140 REM\n"
                "150 REM ── Economizer enabled — modulate OA damper ──\n"
                "160 START {device-name}-ECON-ENA\n"
                "170 REM SLIDE: as MAT rises above SAT-SP, open damper more\n"
                "180 LET D = {device-name}-SAT-SP\n"
                "190 LET {device-name}-OA-DMP = SLIDE( {device-name}-MAT , D , D + 3 , {device-name}-MIN-OA , 100 )\n"
                "200 REM\n"
                "210 REM ── Enforce minimum OA position ──\n"
                "220 IF {device-name}-OA-DMP < {device-name}-MIN-OA THEN LET {device-name}-OA-DMP = {device-name}-MIN-OA\n"
                "230 END"
            ),
        },
    ],
}

register_module(module)
