"""
SBS Controls — Feature Module: Hot Water Preheat Coil

Modulates a hot water preheat valve to maintain minimum preheat leaving
air temperature (typically 45F). Prevents coil freeze conditions on
100% outdoor air units.

Add-on code: PH-HW
Applicable: AHU-VAV, AHU-CV, DOAS, RTU
"""

from app.modules import register_module

module = {
    "id": "mod_preheat_hw",
    "name": "Preheat Coil - Hot Water",
    "feature": "PH-HW",
    "category": "heating",
    "requires": [],
    "conflicts": ["mod_preheat_elec"],
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
        "AO": [
            {
                "name": "{device-name}-PH-VLV",
                "desc": "Preheat Hot Water Valve Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-PH-SP",
                "desc": "Preheat Leaving Air Temp Setpoint",
                "units": "deg-f",
                "min": 35,
                "max": 65,
                "default": 45.0,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UI6": "{device-name}-PH-LAT",
        "UO4": "{device-name}-PH-VLV",
    },

    "code": """\
REM ── PREHEAT HW: Hot Water Preheat Coil Control ──
REM Modulate preheat valve to maintain minimum leaving air temp
REM Prevents coil freeze on 100% OA units

PH_SP = AV11
PH_LAT = AI6

IF BO1 = 1 THEN
  REM Fan running — preheat active
  PH_ERR = PH_SP - PH_LAT

  IF PH_ERR > 0 THEN
    REM Below preheat setpoint — open valve
    PH_OUT = (PH_ERR / 5) * 100
    IF PH_OUT > 100 THEN PH_OUT = 100
    IF PH_OUT < 0 THEN PH_OUT = 0
    AO4 = PH_OUT
  ELSE
    REM Above preheat setpoint — close valve
    AO4 = 0
  ENDIF

  REM Freeze protection override — full open below 38F
  IF PH_LAT < 38 THEN
    AO4 = 100
  ENDIF
ELSE
  REM Fan off — close preheat valve
  REM Exception: open if OAT below freezing (coil protection)
  IF OAT < 32 THEN
    AO4 = 50
  ELSE
    AO4 = 0
  ENDIF
ENDIF\
""",
}

register_module(module)
