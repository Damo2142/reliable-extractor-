"""
SBS Controls — Feature Module: CO2 Demand Control Ventilation

CO2-based demand control ventilation. Reset minimum outdoor air damper
position based on CO2 level (800-1000 PPM range).

Add-on code: VENT-CO2
Applicable: AHU-VAV, AHU-CV, RTU
"""

from app.modules import register_module

module = {
    "id": "mod_co2_dcv",
    "name": "CO2 Demand Control Ventilation",
    "feature": "VENT-CO2",
    "category": "damper",
    "requires": [],
    "conflicts": [],
    "exec_order": 42,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-CO2",
                "desc": "Return Air CO2 Level",
                "units": "ppm",
                "min": 0,
                "max": 5000,
            },
        ],
        "AO": [],
        "AV": [
            {
                "name": "{device-name}-CO2-LO-SP",
                "desc": "CO2 Low Setpoint (min OA position)",
                "units": "ppm",
                "min": 400,
                "max": 1000,
                "default": 800.0,
            },
            {
                "name": "{device-name}-CO2-HI-SP",
                "desc": "CO2 High Setpoint (max OA position)",
                "units": "ppm",
                "min": 800,
                "max": 2000,
                "default": 1000.0,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UI9": "{device-name}-CO2",
    },

    "code": """\
REM ── CO2 DCV: Demand Control Ventilation ──
REM Reset minimum OA damper position based on CO2 level (800-1000 PPM)

CO2_VAL = AI9
CO2_LO = AV17
CO2_HI = AV18

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan running — DCV active

  IF CO2_VAL < CO2_LO THEN
    REM CO2 below low limit — reduce to minimum OA
    DCV_OA_POS = MIN_OA_POS
  ELSE
    IF CO2_VAL > CO2_HI THEN
      REM CO2 above high limit — open to maximum OA
      DCV_OA_POS = 100
    ELSE
      REM CO2 in range — proportionally reset OA position
      CO2_RANGE = CO2_HI - CO2_LO
      IF CO2_RANGE > 0 THEN
        CO2_PCT = (CO2_VAL - CO2_LO) / CO2_RANGE
        DCV_OA_POS = MIN_OA_POS + (CO2_PCT * (100 - MIN_OA_POS))
      ELSE
        DCV_OA_POS = MIN_OA_POS
      ENDIF
    ENDIF
  ENDIF

  REM Override minimum OA position (higher of DCV or economizer min)
  IF DCV_OA_POS > AO3 THEN
    AO3 = DCV_OA_POS
  ENDIF
ENDIF\
""",
}

register_module(module)
