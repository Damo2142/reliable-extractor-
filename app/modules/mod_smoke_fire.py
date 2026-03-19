"""
SBS Controls — Feature Module: Smoke & Fire Safety

Monitors smoke detector and fire alarm contacts. On activation:
stops all fans, closes all dampers, generates alarm.

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
        "AI": [],
        "AO": [],
        "AV": [],
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
        "BO": [],
        "BV": [
            {
                "name": "{device-name}-SMOKE-ALM",
                "desc": "Smoke Alarm Active",
                "states": {0: "Normal", 1: "Alarm"},
                "default": 0,
            },
            {
                "name": "{device-name}-FIRE-SHTDN",
                "desc": "Fire Shutdown Active",
                "states": {0: "Normal", 1: "Shutdown"},
                "default": 0,
            },
        ],
    },

    "io_map": {
        "BI4": "{device-name}-SMOKE",
        "BI5": "{device-name}-FIRE-ALM",
    },

    "code": """\
REM ── SMOKE & FIRE SAFETY: Emergency Shutdown ──
REM On smoke or fire — stop all fans, close all dampers

IF BI4 = 1 OR BI5 = 1 THEN
  REM *** FIRE/SMOKE SHUTDOWN ***

  REM Stop supply fan
  BO1 = 0
  AO4 = 0

  REM Close all dampers
  AO3 = 0

  REM Close all valves
  AO1 = 0
  AO2 = 0

  REM Set mode to Off
  MV1 = 1

  IF BI4 = 1 THEN
    BV5 = 1
    SMOKE_ALARM = 1
  ENDIF
  IF BI5 = 1 THEN
    BV6 = 1
    FIRE_ALARM = 1
  ENDIF
ELSE
  BV5 = 0
  BV6 = 0
ENDIF\
""",
}

register_module(module)
