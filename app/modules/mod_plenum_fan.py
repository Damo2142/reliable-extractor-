"""
SBS Controls — Feature Module: Parallel Plenum Fan (for FPB)

Parallel plenum fan for fan-powered box (FPB) applications.
Enable plenum fan in heating mode when primary damper at minimum.

Add-on code: FAN-PARALLEL
Applicable: VAV terminal units (fan-powered box)
"""

from app.modules import register_module

module = {
    "id": "mod_plenum_fan",
    "name": "Parallel Plenum Fan",
    "feature": "FAN-PARALLEL",
    "category": "fan",
    "requires": [],
    "conflicts": [],
    "exec_order": 35,

    "objects": {
        "AI": [],
        "AO": [],
        "AV": [],
        "BI": [
            {
                "name": "{device-name}-PLN-FAN-STS",
                "desc": "Plenum Fan Status",
                "states": {0: "Off", 1: "On"},
            },
        ],
        "BO": [
            {
                "name": "{device-name}-PLN-FAN-CMD",
                "desc": "Plenum Fan Start/Stop Command",
                "states": {0: "Stop", 1: "Start"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "BI2": "{device-name}-PLN-FAN-STS",
        "BO2": "{device-name}-PLN-FAN-CMD",
    },

    "code": """\
REM ── PLENUM FAN: Parallel Fan-Powered Box Control ──
REM Enable plenum fan in heating mode when primary damper at minimum

HTG_SP = AV2

IF OCC = 1 THEN
  REM Occupied mode
  ZNT_ERR = HTG_SP - ZNT

  IF ZNT_ERR > 0 AND AO1 < 25 THEN
    REM Zone below heating setpoint and damper near minimum
    REM Enable plenum fan to pull warm plenum air
    BO2 = 1
  ELSE
    REM No heating needed or damper not at minimum
    BO2 = 0
  ENDIF
ELSE
  REM Unoccupied: enable plenum fan for low-limit protection
  IF ZNT < AV6 THEN
    BO2 = 1
  ELSE
    BO2 = 0
  ENDIF
ENDIF

REM ── Plenum Fan Status Alarm ──
IF BO2 = 1 AND BI2 = 0 THEN
  IF PLN_FAIL_TMR = 0 THEN
    PLN_FAIL_TMR = ELAPSED
  ENDIF
  IF (ELAPSED - PLN_FAIL_TMR) > 30 THEN
    PLN_FAN_ALARM = 1
  ENDIF
ELSE
  PLN_FAIL_TMR = 0
  PLN_FAN_ALARM = 0
ENDIF\
""",
}

register_module(module)
