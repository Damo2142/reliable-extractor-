"""
SBS Controls — Feature Module: Humidifier Control

Modulate humidifier to maintain supply air relative humidity setpoint.
Includes high-limit cutoff for duct moisture protection.

Add-on code: HUMID-STM
Applicable: AHU-VAV, AHU-CV, RTU (same logic for steam or electric)
"""

from app.modules import register_module

module = {
    "id": "mod_humidity",
    "name": "Humidifier Control",
    "feature": "HUMID-STM",
    "category": "generic",
    "requires": [],
    "conflicts": [],
    "exec_order": 65,

    "objects": {
        "AI": [
            {
                "name": "{device-name}-SA-RH",
                "desc": "Supply Air Relative Humidity",
                "units": "percent-rh",
                "min": 0,
                "max": 100,
            },
        ],
        "AO": [
            {
                "name": "{device-name}-HUMID-CMD",
                "desc": "Humidifier Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [
            {
                "name": "{device-name}-RH-SP",
                "desc": "Supply Air RH Setpoint",
                "units": "percent-rh",
                "min": 10,
                "max": 70,
                "default": 40.0,
            },
            {
                "name": "{device-name}-RH-HI-LIM",
                "desc": "RH High Limit Cutoff",
                "units": "percent-rh",
                "min": 50,
                "max": 90,
                "default": 80.0,
            },
        ],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UI10": "{device-name}-SA-RH",
        "UO7": "{device-name}-HUMID-CMD",
    },

    "code": """\
REM ── HUMIDIFIER: Supply Air Humidity Control ──
REM Modulate humidifier to maintain SA RH setpoint, high-limit cutoff

SA_RH = AI10
RH_SP = AV19
RH_HI_LIM = AV20

IF MODE >= 3 AND BO1 = 1 THEN
  REM Fan running — humidifier allowed

  REM High-limit cutoff check
  IF SA_RH > RH_HI_LIM THEN
    REM Above high limit — shut down humidifier
    AO7 = 0
    GOTO 950
  ENDIF

  REM Modulate humidifier based on RH error
  RH_ERR = RH_SP - SA_RH

  IF RH_ERR > 0 THEN
    REM Below setpoint — enable humidifier
    HUMID_OUT = (RH_ERR / 20) * 100
    IF HUMID_OUT > 100 THEN HUMID_OUT = 100
    IF HUMID_OUT < 0 THEN HUMID_OUT = 0
    AO7 = HUMID_OUT
  ELSE
    REM At or above setpoint — disable humidifier
    AO7 = 0
  ENDIF
ELSE
  REM Fan off — disable humidifier
  AO7 = 0
ENDIF

950 REM ── End Humidifier ──\
""",
}

register_module(module)
