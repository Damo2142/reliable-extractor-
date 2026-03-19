"""
SBS Controls — Feature Module: Freeze Protection

Monitors freeze stat contact. On trip: closes OA damper, opens HW valve
to 100%, and generates alarm. Critical safety override.

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
        "AI": [],
        "AO": [],
        "AV": [],
        "BI": [
            {
                "name": "{device-name}-FREEZE",
                "desc": "Freeze Stat Contact (N.C.)",
                "states": {0: "Normal", 1: "Freeze"},
            },
        ],
        "BO": [],
        "BV": [
            {
                "name": "{device-name}-FREEZE-ALM",
                "desc": "Freeze Protection Alarm",
                "states": {0: "Normal", 1: "Alarm"},
                "default": 0,
            },
        ],
    },

    "io_map": {
        "BI3": "{device-name}-FREEZE",
    },

    "code": """\
REM ── FREEZE PROTECTION: Safety Override ──
REM On freeze stat trip: close OA, open HW, stop fan, alarm

IF BI3 = 1 THEN
  REM *** FREEZE STAT TRIPPED ***
  BV4 = 1

  REM Close outdoor air damper (if economizer module present)
  AO3 = 0

  REM Open hot water valve 100% (if HW module present)
  AO2 = 100

  REM Stop supply fan
  BO1 = 0
  AO4 = 0

  REM Set mode to Off
  MV1 = 1

  REM Freeze alarm — requires manual reset
  FREEZE_ALARM = 1
ELSE
  BV4 = 0
ENDIF\
""",
}

register_module(module)
