"""
SBS Controls — Feature Module: VFD Supply Fan

Variable frequency drive speed control for supply fan.
Outputs analog speed command, reads speed feedback and VFD fault.

Add-on code: SF-VFD
Applicable: AHU-VAV, RTU-VAV
Conflicts with: mod_cs_supply_fan (constant speed fan)
"""

from app.modules import register_module

module = {
    "id": "mod_vfd_supply_fan",
    "name": "VFD Supply Fan Control",
    "feature": "SF-VFD",
    "category": "fan",
    "requires": [],
    "conflicts": ["mod_cs_supply_fan"],
    "exec_order": 30,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-SF-SPD-FB",
                "desc": "Supply Fan VFD Speed Feedback",
                "units": "percent",
                "min": 0,
                "max": 100,
            },
        ],
        "AO": [
            {
                "name": "{device-name}-SF-SPD",
                "desc": "Supply Fan VFD Speed Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-SF-MIN-SPD",
                "desc": "Supply Fan Minimum Speed",
                "units": "percent",
                "min": 10,
                "max": 50,
                "default": 20.0,
            },
            {
                "name": "{device-name}-SF-MAX-SPD",
                "desc": "Supply Fan Maximum Speed",
                "units": "percent",
                "min": 50,
                "max": 100,
                "default": 100.0,
            },
        ],
        "BI": [
            {
                "name": "{device-name}-VFD-FLT",
                "desc": "Supply Fan VFD Fault",
                "states": {0: "Normal", 1: "Fault"},
            },
        ],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UI6": "{device-name}-SF-SPD-FB",
        "UO4": "{device-name}-SF-SPD",
        "BI2": "{device-name}-VFD-FLT",
    },

    "code": """\
REM ── VFD SUPPLY FAN: Speed Control ──
REM Manages supply fan VFD speed command based on operating mode

SF_MIN = AV11
SF_MAX = AV12

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan is commanded on

  IF MODE = 4 THEN
    REM Warmup: run at fixed 50% or min speed, whichever is greater
    SF_SPD_CMD = MAX(SF_MIN, 50)
  ELSE
    IF MODE = 5 THEN
      REM Cooldown: run at minimum speed
      SF_SPD_CMD = SF_MIN
    ELSE
      REM Normal occupied: speed set by pressure control module
      REM If no pressure module, default to 70%
      IF SF_SPD_CMD = 0 THEN SF_SPD_CMD = 70
    ENDIF
  ENDIF

  REM Clamp to min/max range
  IF SF_SPD_CMD < SF_MIN THEN SF_SPD_CMD = SF_MIN
  IF SF_SPD_CMD > SF_MAX THEN SF_SPD_CMD = SF_MAX

  AO4 = SF_SPD_CMD
ELSE
  REM Fan off
  AO4 = 0
ENDIF

REM ── VFD Fault Monitoring ──
IF BI2 = 1 THEN
  REM VFD has faulted
  VFD_ALARM = 1
  REM Stop fan on VFD fault
  BO1 = 0
  AO4 = 0
ELSE
  VFD_ALARM = 0
ENDIF\
""",
}

register_module(module)
