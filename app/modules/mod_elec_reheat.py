"""
SBS Controls — Feature Module: Electric Reheat for VAV Terminals (Staged)

Staged electric reheat when zone below heating setpoint.
Includes discharge air temperature sensor for high-limit protection.

Add-on code: RH-ELEC
Applicable: VAV terminal units
"""

from app.modules import register_module

module = {
    "id": "mod_elec_reheat",
    "name": "Electric Reheat - Staged",
    "feature": "RH-ELEC",
    "category": "heating",
    "requires": [],
    "conflicts": ["mod_hw_reheat"],
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
        "AO": [],
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
        "BO": [
            {
                "name": "{device-name}-HTG-STG1",
                "desc": "Electric Reheat Stage 1 Command",
                "states": {0: "Off", 1: "On"},
                "default": 0,
            },
            {
                "name": "{device-name}-HTG-STG2",
                "desc": "Electric Reheat Stage 2 Command",
                "states": {0: "Off", 1: "On"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "UI3": "{device-name}-DAT",
        "BO2": "{device-name}-HTG-STG1",
        "BO3": "{device-name}-HTG-STG2",
    },

    "code": """\
REM ── ELEC REHEAT: Staged Electric Reheat Control ──
REM Stage electric heat when zone below heating setpoint

DAT = AI3
DAT_MAX_LIM = AV10
HTG_SP = AV2

IF OCC = 1 THEN
  REM Occupied mode
  ZNT_ERR = HTG_SP - ZNT

  REM DAT high limit protection — override stages off
  IF DAT > DAT_MAX_LIM THEN
    BO2 = 0
    BO3 = 0
    GOTO 960
  ENDIF

  REM Stage 1: enable at 1F below heating setpoint
  IF ZNT_ERR > 1 THEN
    BO2 = 1
  ELSE
    IF ZNT_ERR < 0 THEN
      BO2 = 0
    ENDIF
  ENDIF

  REM Stage 2: enable at 2F below heating setpoint
  IF ZNT_ERR > 2 THEN
    BO3 = 1
  ELSE
    IF ZNT_ERR < 1 THEN
      BO3 = 0
    ENDIF
  ENDIF

  REM In heating, maintain minimum airflow
  IF ZNT_ERR > 0 AND AO1 < 20 THEN
    AO1 = 20
  ENDIF
ELSE
  REM Unoccupied: electric reheat for low-limit only
  IF ZNT < AV6 THEN
    BO2 = 1
    BO3 = 1
  ELSE
    BO2 = 0
    BO3 = 0
  ENDIF
ENDIF

960 REM ── End Electric Reheat ──\
""",
}

register_module(module)
