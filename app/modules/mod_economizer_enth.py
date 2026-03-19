"""
SBS Controls — Feature Module: Enthalpy Economizer

Enthalpy-based economizer control. Compares outdoor air enthalpy to
return air enthalpy. Economizes when OA enthalpy is lower than RA
enthalpy and below the high-limit setpoint.

Add-on code: ECON-ENT
Applicable: AHU-VAV, AHU-CV, RTU
"""

from app.modules import register_module

module = {
    "id": "mod_economizer_enth",
    "name": "Economizer - Enthalpy",
    "feature": "ECON-ENT",
    "category": "economizer",
    "requires": [],
    "conflicts": ["mod_economizer_db"],
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
            {
                "name": "{device-name}-OA-RH",
                "desc": "Outdoor Air Relative Humidity",
                "units": "percent-rh",
                "min": 0,
                "max": 100,
            },
            {
                "name": "{device-name}-RA-RH",
                "desc": "Return Air Relative Humidity",
                "units": "percent-rh",
                "min": 0,
                "max": 100,
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
                "name": "{device-name}-ECON-HL",
                "desc": "Economizer Enthalpy High Limit (BTU/lb)",
                "units": "btu-per-pound",
                "min": 20,
                "max": 35,
                "default": 28.0,
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
        "UI7": "{device-name}-OA-RH",
        "UI8": "{device-name}-RA-RH",
        "UO3": "{device-name}-OA-DMP",
    },

    "code": """\
REM ── ECONOMIZER ENTHALPY: Enthalpy-Based Free Cooling ──
REM Compare OA enthalpy to RA enthalpy, modulate OA damper

ECON_HL = AV9
MIN_OA_POS = AV10

REM ── Calculate Approximate Enthalpy ──
REM Simplified enthalpy: h = 0.24*T + W*(1061 + 0.444*T)
REM Using approximate humidity ratio from RH and temp
REM W ~ 0.0000205 * RH * EXP(0.06 * T)
OA_W = 0.0000205 * AI7 * EXP(0.06 * OAT)
OA_ENTH = 0.24 * OAT + OA_W * (1061 + 0.444 * OAT)

RA_W = 0.0000205 * AI8 * EXP(0.06 * RAT)
RA_ENTH = 0.24 * RAT + RA_W * (1061 + 0.444 * RAT)

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan running — economizer logic active

  IF OA_ENTH < RA_ENTH AND OA_ENTH < ECON_HL THEN
    REM OA enthalpy favorable — economizer available
    BV3 = 1

    REM Modulate OA damper for free cooling
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
    REM OA enthalpy too high — economizer off, minimum OA only
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
