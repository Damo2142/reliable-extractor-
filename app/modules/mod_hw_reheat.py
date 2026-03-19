"""
SBS Controls — Feature Module: HW Reheat for VAV Terminals

Modulate reheat valve when zone temp below heating setpoint and
damper at minimum. Includes discharge air temperature sensor.

Add-on code: RH-HW
Applicable: VAV terminal units
"""

from app.modules import register_module

module = {
    "id": "mod_hw_reheat",
    "name": "Hot Water Reheat Valve",
    "feature": "RH-HW",
    "category": "heating",
    "requires": [],
    "conflicts": ["mod_elec_reheat"],
    "exec_order": 60,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-DAT",
                "desc": "Discharge Air Temperature",
                "units": "deg-f",
                "min": 40,
                "max": 150,
            },
        ],
        "AO": [
            {
                "name": "{device-name}-RH-VLV",
                "desc": "Reheat Valve Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-DAT-MAX",
                "desc": "Maximum Discharge Air Temperature",
                "units": "deg-f",
                "min": 80,
                "max": 150,
                "default": 110.0,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UI3": "{device-name}-DAT",
        "UO2": "{device-name}-RH-VLV",
    },

    "code": """\
REM ── HW REHEAT: Hot Water Reheat Valve Control ──
REM Modulate reheat valve when zone below heating setpoint and damper at min

DAT = AI3
DAT_MAX_LIM = AV10
HTG_SP = AV2

IF OCC = 1 THEN
  REM Occupied mode
  ZNT_ERR = HTG_SP - ZNT

  IF ZNT_ERR > 0 THEN
    REM Zone below heating setpoint — modulate reheat valve
    RH_OUT = (ZNT_ERR / 3) * 100
    IF RH_OUT > 100 THEN RH_OUT = 100
    IF RH_OUT < 0 THEN RH_OUT = 0

    REM DAT high limit protection
    IF DAT > DAT_MAX_LIM THEN
      RH_OUT = RH_OUT - 20
      IF RH_OUT < 0 THEN RH_OUT = 0
    ENDIF

    AO2 = RH_OUT

    REM In heating, open damper to heating minimum airflow
    IF AO1 < 20 THEN
      AO1 = 20
    ENDIF
  ELSE
    REM At or above heating setpoint — close reheat valve
    AO2 = 0
  ENDIF
ELSE
  REM Unoccupied: reheat for low-limit protection only
  IF ZNT < AV6 THEN
    AO2 = 100
  ELSE
    AO2 = 0
  ENDIF
ENDIF\
""",
}

register_module(module)
