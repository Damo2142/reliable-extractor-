"""
SBS Controls — Feature Module: Two Stage Electric Heat

Two stage electric heating elements with staggered staging.
Stage 1 on at setpoint - 1 deg F, stage 2 on at setpoint - 2 deg F.

Add-on code: ELEC-2
Applicable: AHU-CV, RTU, FCU
"""

from app.modules import register_module

module = {
    "id": "mod_elec_heat_2stg",
    "name": "Electric Heat - Two Stage",
    "feature": "ELEC-2",
    "category": "heating",
    "requires": [],
    "conflicts": ["mod_elec_heat_1stg", "mod_elec_heat_3stg",
                   "mod_hw_heating", "mod_gas_heat_1stg", "mod_gas_heat_2stg"],
    "exec_order": 60,

    "objects": {
        "AI": [],
        "AO": [],
        "AV": [],
        "BI": [],
        "BO": [
            {
                "name": "{device-name}-HTG-STG1",
                "desc": "Electric Heat Stage 1 Command",
                "states": {0: "Off", 1: "On"},
                "default": 0,
            },
            {
                "name": "{device-name}-HTG-STG2",
                "desc": "Electric Heat Stage 2 Command",
                "states": {0: "Off", 1: "On"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "BO2": "{device-name}-HTG-STG1",
        "BO3": "{device-name}-HTG-STG2",
    },

    "code": """\
REM ── ELEC HEAT 2-STAGE: Two Stage Electric Heat ──
REM Stage 1 on at setpoint-1F, stage 2 on at setpoint-2F

IF BO1 = 1 THEN
  REM Fan/unit is running
  SAT_ERR = AV1 - SAT

  REM Stage 1: enable at 1 deg below setpoint
  IF SAT_ERR > 1 THEN
    BO2 = 1
  ELSE
    IF SAT_ERR < 0 THEN
      BO2 = 0
    ENDIF
  ENDIF

  REM Stage 2: enable at 2 deg below setpoint
  IF SAT_ERR > 2 THEN
    BO3 = 1
  ELSE
    IF SAT_ERR < 1 THEN
      BO3 = 0
    ENDIF
  ENDIF
ELSE
  REM Fan/unit off — disable all stages
  BO2 = 0
  BO3 = 0
ENDIF\
""",
}

register_module(module)
