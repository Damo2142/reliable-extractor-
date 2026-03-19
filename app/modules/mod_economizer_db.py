"""
SBS Controls — Feature Module: Dry Bulb Economizer

Dry bulb economizer control. Compares outdoor air temperature to a
switchover setpoint and modulates the outdoor air damper to provide
free cooling when conditions allow.

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
                "name": "{device-name}-ECON-SP",
                "desc": "Economizer Switchover Temperature",
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
        "BI": [],
        "BO": [],
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

    "code": """\
REM ── ECONOMIZER: Dry Bulb Free Cooling ──
REM Compare OAT to switchover temp, modulate OA damper

ECON_SP = AV9
MIN_OA_POS = AV10

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan running — economizer logic active

  REM Check economizer enable conditions
  IF OAT < ECON_SP THEN
    REM OAT below switchover — economizer available
    BV3 = 1

    REM Modulate OA damper for free cooling
    REM When OAT is favorable, open damper to cool supply air
    SAT_ERR = SAT - AV1

    IF SAT_ERR > 0 THEN
      REM Need cooling — open OA damper proportionally
      ECON_OUT = MIN_OA_POS + ((SAT_ERR / 3) * (100 - MIN_OA_POS))
      IF ECON_OUT > 100 THEN ECON_OUT = 100
      AO3 = ECON_OUT
    ELSE
      REM At or below setpoint — hold minimum OA
      AO3 = MIN_OA_POS
    ENDIF
  ELSE
    REM OAT above switchover — economizer off, minimum OA only
    BV3 = 0
    AO3 = MIN_OA_POS
  ENDIF
ELSE
  REM Fan off — close damper
  AO3 = 0
  BV3 = 0
ENDIF\
""",
}

register_module(module)
