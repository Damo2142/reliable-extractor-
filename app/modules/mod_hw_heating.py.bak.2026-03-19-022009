"""
SBS Controls — Feature Module: Hot Water Heating

Modulates a hot water valve to control supply air temperature during
heating mode. PID output drives HW valve 0-100%.

Add-on code: HW
Applicable: AHU-VAV, AHU-CV, RTU (with HW coil), FCU, VAV (reheat)
"""

from app.modules import register_module

module = {
    "id": "mod_hw_heating",
    "name": "Hot Water Heating Valve",
    "feature": "HW",
    "category": "heating",
    "requires": [],
    "conflicts": [],
    "exec_order": 60,

    "objects": {
        "AI": [],
        "AO": [
            {
                "name": "{device-name}-HW-VLV",
                "desc": "Hot Water Valve Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-HW-P",
                "desc": "HW PID Proportional Band",
                "units": "deg-f",
                "min": 1,
                "max": 20,
                "default": 5.0,
            },
            {
                "name": "{device-name}-HW-I",
                "desc": "HW PID Integral Time",
                "units": "minutes",
                "min": 0,
                "max": 30,
                "default": 8.0,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UO2": "{device-name}-HW-VLV",
    },

    "code": """\
REM ── HW HEATING: Hot Water Valve Control ──
REM Modulates HW valve based on SAT error in heating mode

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan is running, heating allowed
  SAT_ERR = AV1 - SAT
  REM AV1 = active SAT setpoint from base module

  IF MODE = 4 THEN
    REM Warmup mode — use heating setpoint, more aggressive
    SAT_ERR = AV4 - SAT
  ENDIF

  IF SAT_ERR > 0 THEN
    REM Temperature below setpoint — need heating
    HW_P_BAND = AV7
    HW_OUT = (SAT_ERR / HW_P_BAND) * 100

    REM Clamp output 0-100%
    IF HW_OUT > 100 THEN HW_OUT = 100
    IF HW_OUT < 0 THEN HW_OUT = 0

    AO2 = HW_OUT
  ELSE
    REM Above setpoint — close valve
    AO2 = 0
  ENDIF

  REM Heating/cooling interlock: no simultaneous operation
  IF AO1 > 5 THEN
    REM CHW valve is open — force HW closed
    AO2 = 0
  ENDIF
ELSE
  REM Fan off — close valve
  AO2 = 0
ENDIF

REM ── Unoccupied Low Limit Override ──
IF MODE = 2 THEN
  IF RAT < UNOCC_LOW_LIMIT THEN
    REM Below low limit — open HW valve to protect space
    AO2 = 100
  ENDIF
ENDIF\
""",
}

register_module(module)
