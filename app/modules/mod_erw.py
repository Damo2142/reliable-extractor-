"""
SBS Controls — Feature Module: Energy Recovery Wheel

Energy recovery wheel (enthalpy wheel) control. Enable when OA/RA
temperature difference exceeds threshold, modulate speed for recovery,
bypass when economizing.

Add-on code: ERW
Applicable: AHU-VAV, AHU-CV, RTU
"""

from app.modules import register_module

module = {
    "id": "mod_erw",
    "name": "Energy Recovery Wheel",
    "feature": "ERW",
    "category": "economizer",
    "requires": [],
    "conflicts": [],
    "exec_order": 38,

    "objects": {
        "AI": [],
        "AO": [
            {
                "name": "{device-name}-ERW-SPD",
                "desc": "Energy Recovery Wheel Speed Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-ERW-DIFF",
                "desc": "ERW Enable Temperature Differential",
                "units": "deg-f",
                "min": 2,
                "max": 20,
                "default": 5.0,
            },
        ],
        "BI": [],
        "BO": [
            {
                "name": "{device-name}-ERW-CMD",
                "desc": "Energy Recovery Wheel Enable Command",
                "states": {0: "Stop", 1: "Start"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "UO6": "{device-name}-ERW-SPD",
        "BO5": "{device-name}-ERW-CMD",
    },

    "code": """\
REM ── ENERGY RECOVERY WHEEL: Heat/Cool Recovery ──
REM Enable when OA/RA temp difference > threshold, modulate speed
REM Bypass when economizing (free cooling available)

ERW_DIFF_SP = AV16

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan running — check ERW enable conditions

  REM Calculate OA/RA temperature difference
  TEMP_DIFF = ABS(OAT - RAT)

  IF TEMP_DIFF > ERW_DIFF_SP THEN
    REM Significant temp difference — enable ERW

    REM Check if economizer is active (bypass ERW during free cooling)
    IF BV3 = 1 THEN
      REM Economizer active — reduce ERW speed or bypass
      BO5 = 1
      AO6 = 25
    ELSE
      REM No economizer — run ERW at full recovery
      BO5 = 1

      REM Modulate speed based on temp difference
      ERW_SPD = (TEMP_DIFF / 30) * 100
      IF ERW_SPD > 100 THEN ERW_SPD = 100
      IF ERW_SPD < 30 THEN ERW_SPD = 30

      AO6 = ERW_SPD
    ENDIF
  ELSE
    REM Small temp difference — ERW not beneficial
    BO5 = 0
    AO6 = 0
  ENDIF
ELSE
  REM Fan off — disable ERW
  BO5 = 0
  AO6 = 0
ENDIF\
""",
}

register_module(module)
