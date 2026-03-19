"""
SBS Controls — Feature Module: Electric Preheat

Enable electric preheat element when OAT below threshold and unit running.
Monitors preheat leaving air temperature for safety.

Add-on code: PH-ELEC
Applicable: AHU-VAV, AHU-CV, DOAS, RTU
"""

from app.modules import register_module

module = {
    "id": "mod_preheat_elec",
    "name": "Preheat - Electric",
    "feature": "PH-ELEC",
    "category": "heating",
    "requires": [],
    "conflicts": ["mod_preheat_hw"],
    "exec_order": 25,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-PH-LAT",
                "desc": "Preheat Leaving Air Temperature",
                "units": "deg-f",
                "min": -20,
                "max": 150,
            },
        ],
        "AO": [],
        "AV": [
            {
                "name": "{device-name}-PH-ENA-SP",
                "desc": "Preheat Enable OAT Threshold",
                "units": "deg-f",
                "min": 20,
                "max": 60,
                "default": 40.0,
            },
        ],
        "BI": [],
        "BO": [
            {
                "name": "{device-name}-PH-CMD",
                "desc": "Electric Preheat Enable Command",
                "states": {0: "Off", 1: "On"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "UI6": "{device-name}-PH-LAT",
        "BO4": "{device-name}-PH-CMD",
    },

    "code": """\
REM ── PREHEAT ELEC: Electric Preheat Control ──
REM Enable electric preheat when OAT below threshold and unit running

PH_ENA_SP = AV11
PH_LAT = AI6

IF BO1 = 1 THEN
  REM Fan running — check if preheat needed
  IF OAT < PH_ENA_SP THEN
    REM OAT below threshold — enable preheat
    BO4 = 1
  ELSE
    REM OAT above threshold — disable preheat
    BO4 = 0
  ENDIF

  REM High limit safety — disable if LAT too high
  IF PH_LAT > 120 THEN
    BO4 = 0
  ENDIF
ELSE
  REM Fan off — disable preheat
  BO4 = 0
ENDIF\
""",
}

register_module(module)
