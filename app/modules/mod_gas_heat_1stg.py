"""
SBS Controls — Feature Module: Single Stage Gas Heat

Single stage gas furnace with gas valve enable and heating status feedback.

Add-on code: GAS-1
Applicable: RTU, AHU-CV
"""

from app.modules import register_module

module = {
    "id": "mod_gas_heat_1stg",
    "name": "Gas Heat - Single Stage",
    "feature": "GAS-1",
    "category": "heating",
    "requires": [],
    "conflicts": ["mod_hw_heating", "mod_elec_heat_1stg", "mod_elec_heat_2stg",
                   "mod_elec_heat_3stg", "mod_gas_heat_2stg"],
    "exec_order": 60,

    "objects": {
        "AI": [],
        "AO": [],
        "AV": [],
        "BI": [
            {
                "name": "{device-name}-HTG-STS",
                "desc": "Gas Heat Status",
                "states": {0: "Off", 1: "On"},
            },
        ],
        "BO": [
            {
                "name": "{device-name}-GAS-VLV",
                "desc": "Gas Valve Command",
                "states": {0: "Closed", 1: "Open"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "BI4": "{device-name}-HTG-STS",
        "BO3": "{device-name}-GAS-VLV",
    },

    "code": """\
REM ── GAS HEAT 1-STAGE: Single Stage Gas Heat ──
REM Gas valve enable in heating mode

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan is running, heating allowed
  SAT_ERR = AV1 - SAT

  IF MODE = 4 THEN
    REM Warmup mode — use heating setpoint, more aggressive
    SAT_ERR = AV4 - SAT
  ENDIF

  IF SAT_ERR > 1 THEN
    REM More than 1F below setpoint — open gas valve
    BO3 = 1
  ELSE
    IF SAT_ERR < 0 THEN
      REM At or above setpoint — close gas valve
      BO3 = 0
    ENDIF
  ENDIF
ELSE
  REM Fan off — close gas valve
  BO3 = 0
ENDIF

REM ── Unoccupied Low Limit Override ──
IF MODE = 2 THEN
  IF RAT < UNOCC_LOW_LIMIT THEN
    BO3 = 1
  ENDIF
ENDIF\
""",
}

register_module(module)
