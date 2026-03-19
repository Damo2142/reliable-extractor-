"""
SBS Controls — Feature Module: Filter Differential Pressure

Monitors filter differential pressure switch for dirty filter alarm.
Digital input from DP switch across filter bank.

Add-on code: FLTR-DP
Applicable: AHU-VAV, AHU-CV, RTU, DOAS, MAU
"""

from app.modules import register_module

module = {
    "id": "mod_filter_dp",
    "name": "Filter Differential Pressure Monitor",
    "feature": "FLTR-DP",
    "category": "alarm",
    "requires": [],
    "conflicts": [],
    "exec_order": 90,

    "objects": {
        "AI": [],
        "AO": [],
        "AV": [],
        "BI": [
            {
                "name": "{device-name}-FLTR-STS",
                "desc": "Filter Dirty Status (DP Switch)",
                "states": {0: "Clean", 1: "Dirty"},
            },
        ],
        "BO": [],
        "BV": [
            {
                "name": "{device-name}-FLTR-ALM",
                "desc": "Filter Dirty Alarm",
                "states": {0: "Normal", 1: "Dirty Filter"},
                "default": 0,
            },
        ],
    },

    "io_map": {
        "BI6": "{device-name}-FLTR-STS",
    },

    "code": """\
REM ── FILTER DP: Dirty Filter Alarm ──
REM Monitor filter differential pressure switch

IF BI6 = 1 AND BO1 = 1 THEN
  REM Filter dirty AND fan running — valid alarm condition
  IF FLTR_TMR = 0 THEN
    FLTR_TMR = ELAPSED
  ENDIF
  IF (ELAPSED - FLTR_TMR) > 60 THEN
    REM Confirmed dirty filter (60 second delay to debounce)
    BV7 = 1
  ENDIF
ELSE
  FLTR_TMR = 0
  IF BI6 = 0 THEN
    BV7 = 0
  ENDIF
ENDIF\
""",
}

register_module(module)
