"""
SBS Controls — Feature Module: Hot Water Heating

Modulates a hot water valve to control supply air temperature during
heating mode using proper Control-BASIC SLIDE() function.
REVERSE action — valve opens as temperature drops below setpoint.

Program:
    {device-name}-HTG-PRG — Heating sequence with SLIDE() modulation

Add-on code: HW
Applicable: AHU-VAV, AHU-CV, RTU (with HW coil), FCU, VAV (reheat)
"""

from app.modules import register_module

module = {
    "id": "mod_hw_heating",
    "name": "Hot Water Heating Valve",
    "feature": "HW",
    "category": "heating",
    "requires": [],
    "conflicts": [],
    "exec_order": 60,

    "objects": {
        "AO": [
            {
                "name": "{device-name}-HW-VLV",
                "desc": "Hot Water Valve Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
    },

    "io_map": {
        "UO2": "{device-name}-HW-VLV",
    },

    "programs": [
        {
            "name": "{device-name}-HTG-PRG",
            "description": "Heating Sequence — HW Valve Modulation",
            "code": (
                "10 REM ***** HEATING PROGRAM *****\n"
                "20 REM SBS Controls — Hot Water Valve Control\n"
                "30 REM Modulate HW-VLV using SLIDE (reverse action)\n"
                "40 REM As SAT drops below SP, valve opens toward 100%\n"
                "50 REM\n"
                "60 REM ── Emergency stop: close valve ──\n"
                "70 IF {device-name}-EMER-STOP THEN LET {device-name}-HW-VLV = 0 , END\n"
                "80 REM\n"
                "90 REM ── Only heat when HVAC-MODE = Heat (1) ──\n"
                "100 IF {device-name}-HVAC-MODE <> 1 THEN LET {device-name}-HW-VLV = 0 , END\n"
                "110 REM\n"
                "120 REM ── Fan must be running ──\n"
                "130 IF NOT {device-name}-SF-STS THEN LET {device-name}-HW-VLV = 0 , END\n"
                "140 REM\n"
                "150 REM ── Modulate HW valve proportionally (reverse) ──\n"
                "160 REM SLIDE: as SAT drops from SP to SP-5, valve goes 0 to 100\n"
                "170 LET A = {device-name}-SAT-SP\n"
                "180 LET {device-name}-HW-VLV = SLIDE( {device-name}-SAT , A - 5 , A , 100 , 0 )\n"
                "190 REM\n"
                "200 REM ── Clamp output 0-100 ──\n"
                "210 LET {device-name}-HW-VLV = LIMIT( {device-name}-HW-VLV , 0 , 100 )\n"
                "220 REM\n"
                "230 REM ── Freeze override: open valve 100% on freeze ──\n"
                "240 IF {device-name}-SAT < 38 THEN LET {device-name}-HW-VLV = 100\n"
                "250 END"
            ),
        },
    ],
}

register_module(module)
