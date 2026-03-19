"""
SBS Controls — Feature Module: Duct Static Pressure Control

PID control of duct static pressure by modulating supply fan VFD speed.
Requires VFD supply fan module for speed output.

Add-on code: DSP
Applicable: AHU-VAV (required for VAV systems)
Requires: mod_vfd_supply_fan
"""

from app.modules import register_module

module = {
    "id": "mod_static_pressure",
    "name": "Duct Static Pressure Control",
    "feature": "DSP",
    "category": "pressure",
    "requires": ["mod_vfd_supply_fan"],
    "conflicts": [],
    "exec_order": 70,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-DSP",
                "desc": "Duct Static Pressure",
                "units": "inwc",
                "min": 0,
                "max": 5.0,
            },
        ],
        "AO": [],
        "AV": [
            {
                "name": "{device-name}-DSP-SP",
                "desc": "Duct Static Pressure Setpoint",
                "units": "inwc",
                "min": 0.3,
                "max": 3.0,
                "default": 1.5,
            },
            {
                "name": "{device-name}-DSP-P",
                "desc": "DSP PID Proportional Band",
                "units": "inwc",
                "min": 0.1,
                "max": 2.0,
                "default": 0.5,
            },
            {
                "name": "{device-name}-DSP-I",
                "desc": "DSP PID Integral Time",
                "units": "minutes",
                "min": 0,
                "max": 20,
                "default": 3.0,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UI7": "{device-name}-DSP",
    },

    "code": """\
REM ── DUCT STATIC PRESSURE: Fan Speed PID ──
REM Modulates supply fan VFD speed to maintain duct static pressure setpoint

DSP_VAL = AI7
DSP_SETPT = AV13
DSP_P_BAND = AV14

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan running — run DSP PID

  DSP_ERR = DSP_SETPT - DSP_VAL
  REM Error: positive = need more pressure (speed up)

  REM Proportional control
  DSP_OUT = 50 + (DSP_ERR / DSP_P_BAND) * 50

  REM Clamp to min/max fan speed range
  IF DSP_OUT < SF_MIN THEN DSP_OUT = SF_MIN
  IF DSP_OUT > SF_MAX THEN DSP_OUT = SF_MAX

  REM Write fan speed command (overrides VFD module default)
  SF_SPD_CMD = DSP_OUT
  AO4 = DSP_OUT

  REM High static alarm
  IF DSP_VAL > (DSP_SETPT * 1.5) THEN
    DSP_HI_ALARM = 1
  ELSE
    DSP_HI_ALARM = 0
  ENDIF

  REM Low static alarm (fan running but no pressure)
  IF DSP_VAL < 0.1 AND AO4 > 50 THEN
    DSP_LO_ALARM = 1
  ELSE
    DSP_LO_ALARM = 0
  ENDIF
ENDIF\
""",
}

register_module(module)
