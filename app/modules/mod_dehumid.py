"""
SBS Controls — Feature Module: Dehumidification

Monitors zone humidity and enables dehumidification when humidity
exceeds setpoint + deadband. Subcools CHW valve to lower temperature,
then reheats to neutral supply air temperature.

Program:
    {device-name}-DEHUM-PRG — Dehumidification sequence

Add-on code: DEHUM
Applicable: AHU-VAV, AHU-CV, DOAS
"""

from app.modules import register_module

module = {
    "id": "mod_dehumid",
    "name": "Dehumidification Control",
    "feature": "DEHUM",
    "category": "cooling",
    "requires": [],
    "conflicts": [],
    "exec_order": 55,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-ZN-RH",
                "desc": "Zone Relative Humidity",
                "units": "percent-rh",
                "min": 0,
                "max": 100,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-RH-SP",
                "desc": "Zone RH Setpoint",
                "units": "percent-rh",
                "min": 30,
                "max": 70,
                "default": 55.0,
            },
            {
                "name": "{device-name}-RH-DB",
                "desc": "RH Deadband",
                "units": "percent-rh",
                "min": 2,
                "max": 10,
                "default": 5.0,
            },
            {
                "name": "{device-name}-DEHUM-SAT-SP",
                "desc": "Dehum Subcool SAT Setpoint",
                "units": "deg-f",
                "min": 45,
                "max": 55,
                "default": 48.0,
            },
        ],
        "BV": [
            {
                "name": "{device-name}-DEHUM-ACT",
                "desc": "Dehumidification Active",
                "states": {0: "Inactive", 1: "Active"},
                "default": 0,
            },
        ],
    },

    "io_map": {
        "UI8": "{device-name}-ZN-RH",
    },

    "programs": [
        {
            "name": "{device-name}-DEHUM-PRG",
            "description": "Dehumidification Sequence",
            "code": (
                "10 REM ***** DEHUMIDIFICATION PROGRAM *****\n"
                "20 REM SBS Controls — Zone Humidity Control\n"
                "30 REM When RH > SP + DB, subcool CHW to remove moisture\n"
                "40 REM then reheat HW to neutral supply temp\n"
                "50 REM\n"
                "60 REM ── Fan must be running ──\n"
                "70 IF NOT {device-name}-SF-STS THEN STOP {device-name}-DEHUM-ACT , END\n"
                "80 REM\n"
                "90 REM ── Check humidity with SWITCH hysteresis ──\n"
                "100 LET A = {device-name}-RH-SP\n"
                "110 LET B = {device-name}-RH-DB\n"
                "120 REM SWITCH turns on at SP+DB, off at SP (hysteresis)\n"
                "130 SWITCH( {device-name}-DEHUM-ACT , {device-name}-ZN-RH , A , A + B )\n"
                "140 REM\n"
                "150 REM ── When dehum active: subcool CHW valve ──\n"
                "160 IF NOT {device-name}-DEHUM-ACT THEN END\n"
                "170 REM Subcool: drive CHW valve to lower SAT to dehum setpoint\n"
                "180 LET C = {device-name}-DEHUM-SAT-SP\n"
                "190 LET {device-name}-CHW-VLV = SLIDE( {device-name}-SAT , C , C + 3 , 0 , 100 )\n"
                "200 LET {device-name}-CHW-VLV = LIMIT( {device-name}-CHW-VLV , 0 , 100 )\n"
                "210 REM\n"
                "220 REM ── Reheat to neutral: drive HW valve ──\n"
                "230 LET D = {device-name}-SAT-SP\n"
                "240 LET {device-name}-HW-VLV = SLIDE( {device-name}-SAT , D - 5 , D , 100 , 0 )\n"
                "250 LET {device-name}-HW-VLV = LIMIT( {device-name}-HW-VLV , 0 , 100 )\n"
                "260 END"
            ),
        },
    ],
}

register_module(module)
