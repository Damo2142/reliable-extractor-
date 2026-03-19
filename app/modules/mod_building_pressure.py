"""
SBS Controls — Feature Module: Building Pressure Control

Modulates a relief air damper to maintain building positive pressure
setpoint (typically 0.05" WC). Prevents excessive pressurization or
negative pressure.

Add-on code: BLDG-P
Applicable: AHU-VAV, AHU-CV, DOAS, RTU
"""

from app.modules import register_module

module = {
    "id": "mod_building_pressure",
    "name": "Building Pressure Control",
    "feature": "BLDG-P",
    "category": "pressure",
    "requires": [],
    "conflicts": [],
    "exec_order": 72,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-BLDG-P",
                "desc": "Building Static Pressure",
                "units": "inwc",
                "min": -0.5,
                "max": 0.5,
            },
        ],
        "AO": [
            {
                "name": "{device-name}-RLF-DMP",
                "desc": "Relief Air Damper Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-BLDG-P-SP",
                "desc": "Building Pressure Setpoint",
                "units": "inwc",
                "min": 0,
                "max": 0.25,
                "default": 0.05,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UI9": "{device-name}-BLDG-P",
        "UO5": "{device-name}-RLF-DMP",
    },

    "code": """\
REM ── BUILDING PRESSURE: Relief Damper Control ──
REM Modulate relief damper to maintain building pressure setpoint

BLDG_P = AI9
BLDG_P_SP = AV17

IF BO1 = 1 THEN
  REM Fan running — building pressure control active
  BP_ERR = BLDG_P - BLDG_P_SP

  IF BP_ERR > 0 THEN
    REM Building over-pressurized — open relief damper
    RLF_OUT = (BP_ERR / 0.1) * 100
    IF RLF_OUT > 100 THEN RLF_OUT = 100
    IF RLF_OUT < 0 THEN RLF_OUT = 0
    AO5 = RLF_OUT
  ELSE
    REM Building pressure at or below setpoint — close relief
    AO5 = 0
  ENDIF
ELSE
  REM Fan off — close relief damper
  AO5 = 0
ENDIF\
""",
}

register_module(module)
