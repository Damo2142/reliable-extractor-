"""
SBS Controls — Feature Module: Chilled Water Cooling

Modulates a chilled water valve to control supply air temperature during
cooling mode. PID output drives CHW valve 0-100%.

Add-on code: CHW
Applicable: AHU-VAV, AHU-CV, RTU (with CHW coil), FCU
"""

from app.modules import register_module

module = {
    "id": "mod_chw_cooling",
    "name": "Chilled Water Cooling Valve",
    "feature": "CHW",
    "category": "cooling",
    "requires": [],
    "conflicts": [],
    "exec_order": 50,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-CLG-DAT",
                "desc": "Cooling Coil Discharge Air Temperature",
                "units": "deg-f",
                "min": 40,
                "max": 80,
            },
        ],
        "AO": [
            {
                "name": "{device-name}-CHW-VLV",
                "desc": "Chilled Water Valve Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-CHW-P",
                "desc": "CHW PID Proportional Band",
                "units": "deg-f",
                "min": 1,
                "max": 20,
                "default": 4.0,
            },
            {
                "name": "{device-name}-CHW-I",
                "desc": "CHW PID Integral Time",
                "units": "minutes",
                "min": 0,
                "max": 30,
                "default": 5.0,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UI4": "{device-name}-CLG-DAT",
        "UO1": "{device-name}-CHW-VLV",
    },

    "code": """\
REM ── CHW COOLING: Chilled Water Valve Control ──
REM Modulates CHW valve based on SAT error in cooling mode

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan is running, cooling allowed
  SAT_ERR = SAT - AV1
  REM AV1 = active SAT setpoint from base module

  IF SAT_ERR > 0 THEN
    REM Temperature above setpoint — need cooling
    CHW_P_BAND = AV5
    CHW_OUT = (SAT_ERR / CHW_P_BAND) * 100

    REM Clamp output 0-100%
    IF CHW_OUT > 100 THEN CHW_OUT = 100
    IF CHW_OUT < 0 THEN CHW_OUT = 0

    AO1 = CHW_OUT
  ELSE
    REM Below setpoint — close valve
    AO1 = 0
  ENDIF
ELSE
  REM Fan off or not in occupied mode — close valve
  AO1 = 0
ENDIF\
""",
}

register_module(module)
