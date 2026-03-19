"""
SBS Controls — Feature Module: HW Valve for FCU (4-Pipe Upgrade)

Modulate hot water valve for heating when zone below setpoint.
Converts a 2-pipe cooling-only FCU to a 4-pipe heating/cooling unit.

Add-on code: HW
Applicable: FCU, terminal units
Note: Uses same feature code "HW" as AHU HW heating but with
      zone-temp-based control logic appropriate for terminals.
"""

from app.modules import register_module

module = {
    "id": "mod_hw_valve_fcu",
    "name": "Hot Water Valve (FCU/Terminal)",
    "feature": "HW-FCU",
    "category": "heating",
    "requires": [],
    "conflicts": [],
    "exec_order": 60,

    "objects": {
        "AI": [],
        "AO": [
            {
                "name": "{device-name}-HW-VLV",
                "desc": "Hot Water Valve Command",
                "units": "percent",
                "min": 0,
                "max": 100,
                "default": 0,
            },
        ],
        "AV": [],
        "BI": [],
        "BO": [],
        "BV": [],
    },

    "io_map": {
        "UO2": "{device-name}-HW-VLV",
    },

    "code": """\
REM ── HW VALVE FCU: Hot Water Valve Control (4-Pipe) ──
REM Modulate HW valve for heating when zone below setpoint

HTG_SP = AV2

IF BO1 = 1 THEN
  REM Fan running
  ZNT_ERR = HTG_SP - ZNT

  IF ZNT_ERR > 0 THEN
    REM Zone below heating setpoint — open HW valve
    HW_OUT = (ZNT_ERR / 3) * 100
    IF HW_OUT > 100 THEN HW_OUT = 100
    IF HW_OUT < 0 THEN HW_OUT = 0
    AO2 = HW_OUT

    REM Heating/cooling interlock: no simultaneous operation
    IF AO1 > 5 THEN
      REM CHW valve is open — force HW closed
      AO2 = 0
    ENDIF
  ELSE
    REM At or above setpoint — close HW valve
    AO2 = 0
  ENDIF
ELSE
  REM Fan off — close valve
  AO2 = 0
ENDIF\
""",
}

register_module(module)
