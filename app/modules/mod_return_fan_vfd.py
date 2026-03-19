"""
SBS Controls — Feature Module: Return Fan with VFD

Return fan with variable frequency drive speed control.
Tracks supply fan speed at an offset (typically 90%) for building
pressure control.

Add-on code: RF-VFD
Applicable: AHU-VAV, AHU-CV, RTU
"""

from app.modules import register_module

module = {
    "id": "mod_return_fan_vfd",
    "name": "Return Fan - VFD",
    "feature": "RF-VFD",
    "category": "fan",
    "requires": [],
    "conflicts": [],
    "exec_order": 35,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-RF-SPD-FB",
                "desc": "Return Fan VFD Speed Feedback",
                "units": "percent",
                "min": 0,
                "max": 100,
            },
        ],
        "AO": [
            {
                "name": "{device-name}-RF-SPD",
                "desc": "Return Fan VFD Speed Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-RF-OFFSET",
                "desc": "Return Fan Speed Offset from Supply (%)",
                "units": "percent",
                "min": 50,
                "max": 100,
                "default": 90.0,
            },
        ],
        "BI": [
            {
                "name": "{device-name}-RF-STS",
                "desc": "Return Fan Status (current switch)",
                "states": {0: "Off", 1: "On"},
            },
        ],
        "BO": [
            {
                "name": "{device-name}-RF-CMD",
                "desc": "Return Fan Start/Stop Command",
                "states": {0: "Stop", 1: "Start"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "UI8": "{device-name}-RF-SPD-FB",
        "UO5": "{device-name}-RF-SPD",
        "BI3": "{device-name}-RF-STS",
        "BO4": "{device-name}-RF-CMD",
    },

    "code": """\
REM ── RETURN FAN VFD: Speed Tracking & Building Pressure Control ──
REM Track supply fan at offset (typ 90%), building pressure control

RF_OFFSET = AV15

IF MODE >= 3 AND BO1 = 1 THEN
  REM Supply fan is running — start return fan
  BO4 = 1

  REM Track supply fan speed at offset
  RF_SPD_CMD = SF_SPD_CMD * (RF_OFFSET / 100)

  REM Clamp to 0-100%
  IF RF_SPD_CMD > 100 THEN RF_SPD_CMD = 100
  IF RF_SPD_CMD < 15 THEN RF_SPD_CMD = 15

  AO5 = RF_SPD_CMD
ELSE
  REM Supply fan off — stop return fan
  BO4 = 0
  AO5 = 0
ENDIF

REM ── Return Fan Status Alarm ──
IF BO4 = 1 AND BI3 = 0 THEN
  IF RF_FAIL_TMR = 0 THEN
    RF_FAIL_TMR = ELAPSED
  ENDIF
  IF (ELAPSED - RF_FAIL_TMR) > 30 THEN
    RF_ALARM = 1
  ENDIF
ELSE
  RF_FAIL_TMR = 0
  RF_ALARM = 0
ENDIF\
""",
}

register_module(module)
