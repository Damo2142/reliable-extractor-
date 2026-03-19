"""
SBS Controls — Feature Module: Condensate Overflow Detection

Monitors condensate overflow float switch. On alarm: generates alarm
and optionally shuts down unit to prevent water damage.

Add-on code: COND-OVF
Applicable: AHU-VAV, AHU-CV, RTU, FCU, WSHP
"""

from app.modules import register_module

module = {
    "id": "mod_condensate",
    "name": "Condensate Overflow Detection",
    "feature": "COND-OVF",
    "category": "safety",
    "requires": [],
    "conflicts": [],
    "exec_order": 85,

    "objects": {
        "AI": [],
        "AO": [],
        "AV": [],
        "BI": [
            {
                "name": "{device-name}-COND-OVF",
                "desc": "Condensate Overflow Switch (N.C.)",
                "states": {0: "Normal", 1: "Overflow"},
            },
        ],
        "BO": [],
        "BV": [
            {
                "name": "{device-name}-COND-ALM",
                "desc": "Condensate Overflow Alarm",
                "states": {0: "Normal", 1: "Alarm"},
                "default": 0,
            },
        ],
    },

    "io_map": {
        "BI5": "{device-name}-COND-OVF",
    },

    "code": """\
REM ── CONDENSATE OVERFLOW: Safety Detection ──
REM Monitor condensate overflow switch, alarm and optional shutdown

IF BI5 = 1 THEN
  REM *** CONDENSATE OVERFLOW DETECTED ***
  BV5 = 1

  REM Shutdown unit to prevent water damage
  BO1 = 0
  MV1 = 1
ELSE
  BV5 = 0
ENDIF\
""",
}

register_module(module)
