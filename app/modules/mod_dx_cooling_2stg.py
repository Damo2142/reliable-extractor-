"""
SBS Controls — Feature Module: Two Stage DX Cooling

Two stage direct-expansion cooling with interstage delay.
Stage 1 and stage 2 with independent control.

Add-on code: DX-2
Applicable: RTU, AHU-CV (with DX coil)
"""

from app.modules import register_module

module = {
    "id": "mod_dx_cooling_2stg",
    "name": "DX Cooling - Two Stage",
    "feature": "DX-2",
    "category": "cooling",
    "requires": [],
    "conflicts": ["mod_chw_cooling", "mod_dx_cooling_1stg"],
    "exec_order": 50,

    "objects": {
        "AI": [],
        "AO": [],
        "AV": [],
        "BI": [
            {
                "name": "{device-name}-CMP-STS",
                "desc": "Compressor Status",
                "states": {0: "Off", 1: "On"},
            },
            {
                "name": "{device-name}-CMP-ALM",
                "desc": "Compressor Alarm/Fault",
                "states": {0: "Normal", 1: "Fault"},
            },
        ],
        "BO": [
            {
                "name": "{device-name}-DX-STG1",
                "desc": "DX Cooling Stage 1 Command",
                "states": {0: "Off", 1: "On"},
                "default": 0,
            },
            {
                "name": "{device-name}-DX-STG2",
                "desc": "DX Cooling Stage 2 Command",
                "states": {0: "Off", 1: "On"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "BI2": "{device-name}-CMP-STS",
        "BI3": "{device-name}-CMP-ALM",
        "BO2": "{device-name}-DX-STG1",
        "BO3": "{device-name}-DX-STG2",
    },

    "code": """\
REM ── DX COOLING 2-STAGE: Two Stage DX Cooling Control ──
REM Stage 1 and 2 with interstage delay

REM Interstage delay in seconds (2 minutes)
DX_INTER_DELAY = 120
REM Minimum compressor on/off time (3 minutes)
CMP_MIN_TIME = 180

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan is running, cooling allowed
  SAT_ERR = SAT - AV1

  REM Stage 1: enable when 1F above setpoint
  IF SAT_ERR > 1 THEN
    IF BO2 = 0 THEN
      IF DX1_OFF_TMR = 0 OR (ELAPSED - DX1_OFF_TMR) > CMP_MIN_TIME THEN
        BO2 = 1
        DX1_ON_TMR = ELAPSED
      ENDIF
    ENDIF
  ELSE
    IF SAT_ERR < 0 THEN
      IF BO2 = 1 THEN
        IF (ELAPSED - DX1_ON_TMR) > CMP_MIN_TIME THEN
          BO2 = 0
          DX1_OFF_TMR = ELAPSED
        ENDIF
      ENDIF
    ENDIF
  ENDIF

  REM Stage 2: enable when 2F above setpoint (with interstage delay)
  IF SAT_ERR > 2 AND BO2 = 1 THEN
    IF (ELAPSED - DX1_ON_TMR) > DX_INTER_DELAY THEN
      BO3 = 1
    ENDIF
  ELSE
    IF SAT_ERR < 1 THEN
      BO3 = 0
    ENDIF
  ENDIF

  REM Compressor fault protection
  IF BI3 = 1 THEN
    BO2 = 0
    BO3 = 0
    CMP_ALARM = 1
  ELSE
    CMP_ALARM = 0
  ENDIF
ELSE
  REM Fan off — disable all stages
  IF BO2 = 1 THEN
    BO2 = 0
    DX1_OFF_TMR = ELAPSED
  ENDIF
  BO3 = 0
ENDIF\
""",
}

register_module(module)
