"""
SBS Controls — Feature Module: Single Stage DX Cooling

Single stage direct-expansion compressor cooling with minimum on/off timers
to protect the compressor (3 minute minimum).

Add-on code: DX-1
Applicable: RTU, AHU-CV (with DX coil)
"""

from app.modules import register_module

module = {
    "id": "mod_dx_cooling_1stg",
    "name": "DX Cooling - Single Stage",
    "feature": "DX-1",
    "category": "cooling",
    "requires": [],
    "conflicts": ["mod_chw_cooling", "mod_dx_cooling_2stg"],
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
                "name": "{device-name}-CMP-CMD",
                "desc": "Compressor Start/Stop Command",
                "states": {0: "Stop", 1: "Start"},
                "default": 0,
            },
        ],
        "BV": [],
    },

    "io_map": {
        "BI2": "{device-name}-CMP-STS",
        "BI3": "{device-name}-CMP-ALM",
        "BO2": "{device-name}-CMP-CMD",
    },

    "code": """\
REM ── DX COOLING 1-STAGE: Single Stage Compressor Control ──
REM Enable compressor when cooling needed, min on/off timers (3 min)

REM Minimum on/off time in seconds (3 minutes)
CMP_MIN_TIME = 180

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan is running, cooling allowed
  SAT_ERR = SAT - AV1

  IF SAT_ERR > 1 THEN
    REM Temperature above setpoint by 1F — need cooling
    REM Check minimum off-time before enabling
    IF BO2 = 0 THEN
      IF CMP_OFF_TMR = 0 OR (ELAPSED - CMP_OFF_TMR) > CMP_MIN_TIME THEN
        BO2 = 1
        CMP_ON_TMR = ELAPSED
      ENDIF
    ENDIF
  ELSE
    IF SAT_ERR < 0 THEN
      REM Below setpoint — disable compressor
      REM Check minimum on-time before disabling
      IF BO2 = 1 THEN
        IF (ELAPSED - CMP_ON_TMR) > CMP_MIN_TIME THEN
          BO2 = 0
          CMP_OFF_TMR = ELAPSED
        ENDIF
      ENDIF
    ENDIF
  ENDIF

  REM Compressor fault protection
  IF BI3 = 1 THEN
    REM Compressor alarm — immediate shutdown
    BO2 = 0
    CMP_ALARM = 1
  ELSE
    CMP_ALARM = 0
  ENDIF
ELSE
  REM Fan off or not in occupied mode — disable compressor
  IF BO2 = 1 THEN
    BO2 = 0
    CMP_OFF_TMR = ELAPSED
  ENDIF
ENDIF\
""",
}

register_module(module)
