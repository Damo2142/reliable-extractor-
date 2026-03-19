"""
SBS Controls — Feature Module: Chilled Water Cooling

Modulates a chilled water valve to control supply air temperature during
cooling mode using proper Control-BASIC SLIDE() function.

Program:
    {device-name}-CLG-PRG — Cooling sequence with SLIDE() modulation

Add-on code: CHW
Applicable: AHU-VAV, AHU-CV, RTU (with CHW coil), FCU
"""

from app.modules import register_module

module = {
    "id": "mod_chw_cooling",
    "name": "Chilled Water Cooling Valve",
    "feature": "CHW",
    "category": "cooling",
    "requires": [],
    "conflicts": [],
    "exec_order": 50,

    "objects": {
        "AO": [
            {
                "name": "{device-name}-CHW-VLV",
                "desc": "Chilled Water Valve Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
    },

    "io_map": {
        "UO1": "{device-name}-CHW-VLV",
    },

    "programs": [
        {
            "name": "{device-name}-CLG-PRG",
            "description": "Cooling Sequence — CHW Valve Modulation",
            "code": (
                "10 REM ***** COOLING PROGRAM *****\n"
                "20 REM SBS Controls — Chilled Water Valve Control\n"
                "30 REM Modulate CHW-VLV using SLIDE based on SAT vs SAT-SP\n"
                "40 REM\n"
                "50 REM ── Emergency stop: close valve ──\n"
                "60 IF {device-name}-EMER-STOP THEN LET {device-name}-CHW-VLV = 0 , END\n"
                "70 REM\n"
                "80 REM ── Only cool when HVAC-MODE = Cool (2) ──\n"
                "90 IF {device-name}-HVAC-MODE <> 2 THEN LET {device-name}-CHW-VLV = 0 , END\n"
                "100 REM\n"
                "110 REM ── Fan must be running ──\n"
                "120 IF NOT {device-name}-SF-STS THEN LET {device-name}-CHW-VLV = 0 , END\n"
                "130 REM\n"
                "140 REM ── Modulate CHW valve proportionally ──\n"
                "150 REM SLIDE: as SAT rises from SP to SP+5, valve goes 0 to 100\n"
                "160 LET A = {device-name}-SAT-SP\n"
                "170 LET {device-name}-CHW-VLV = SLIDE( {device-name}-SAT , A , A + 5 , 0 , 100 )\n"
                "180 REM\n"
                "190 REM ── Clamp output 0-100 ──\n"
                "200 LET {device-name}-CHW-VLV = LIMIT( {device-name}-CHW-VLV , 0 , 100 )\n"
                "210 END"
            ),
        },
    ],
}

register_module(module)
