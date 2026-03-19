"""
SBS Controls — Feature Module: Constant Speed Supply Fan

Constant speed supply fan code. Base modules already include SF-CMD/SF-STS
hardware points, so this module adds the constant-speed operational code
without VFD speed control.

Add-on code: SF-CS
Applicable: AHU-CV, RTU (constant speed applications)
Conflicts with: mod_vfd_supply_fan (VFD fan control)
"""

from app.modules import register_module

module = {
    "id": "mod_cs_supply_fan",
    "name": "Constant Speed Supply Fan",
    "feature": "SF-CS",
    "category": "fan",
    "requires": [],
    "conflicts": ["mod_vfd_supply_fan"],
    "exec_order": 30,

    "objects": {
        "AI": [],
        "AO": [],
        "AV": [
            {
                "name": "{device-name}-SF-ON-DLY",
                "desc": "Supply Fan Start Delay (seconds)",
                "units": "seconds",
                "min": 0,
                "max": 300,
                "default": 0,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {},

    "code": """\
REM ── CONSTANT SPEED SUPPLY FAN: On/Off Control ──
REM Simple constant-speed fan control (no VFD)
REM Fan start/stop commanded by base module mode logic

REM Fan proof-of-flow verification
IF BO1 = 1 AND FAN_STS = 0 THEN
  REM Fan commanded on but no status — check delay
  IF CS_FAN_TMR = 0 THEN
    CS_FAN_TMR = ELAPSED
  ENDIF
  IF (ELAPSED - CS_FAN_TMR) > 60 THEN
    REM Fan failure after 60 seconds
    CS_FAN_ALARM = 1
  ENDIF
ELSE
  CS_FAN_TMR = 0
  CS_FAN_ALARM = 0
ENDIF\
""",
}

register_module(module)
