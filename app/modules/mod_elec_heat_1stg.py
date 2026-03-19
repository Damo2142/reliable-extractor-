"""
SBS Controls — Feature Module: Single Stage Electric Heat

Single stage electric heating element. Enable stage 1 when heating needed
(zone/supply air below setpoint in heating mode).

Add-on code: ELEC-1
Applicable: AHU-CV, RTU, FCU, Unit Heater
"""

from app.modules import register_module

module = {
    "id": "mod_elec_heat_1stg",
    "name": "Electric Heat - Single Stage",
    "feature": "ELEC-1",
    "category": "heating",
    "requires": [],
    "conflicts": ["mod_elec_heat_2stg", "mod_elec_heat_3stg",
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
        ],
        "BV": [],
    },

    "io_map": {
        "BO2": "{device-name}-HTG-STG1",
    },

    "code": """\
REM ── ELEC HEAT 1-STAGE: Single Stage Electric Heat ──
REM Enable stage 1 when heating needed (below setpoint in heating mode)

IF BO1 = 1 THEN
  REM Fan/unit is running
  SAT_ERR = AV1 - SAT

  IF SAT_ERR > 1 THEN
    REM More than 1 deg below setpoint — enable heat stage 1
    BO2 = 1
  ELSE
    IF SAT_ERR < 0 THEN
      REM At or above setpoint — disable heat
      BO2 = 0
    ENDIF
  ENDIF
ELSE
  REM Fan/unit off — disable heat
  BO2 = 0
ENDIF\
""",
}

register_module(module)
