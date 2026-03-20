"""
SBS Composition Engine v2 — Alarm Generator

Auto-generates alarm definitions and .BAS alarm code from a ControllerConfig.
Based on Dave's Reliable Alarm Builder v10 format.

Alarm BAS format:
  ALARM-TYPE [type] [priority]
  DALARM {device-name}-[point] , [delay] , [condition] ,

Types: System, General, Critical, Warning, Information, Email
Priorities: Critical, Critical2, Warning1, Warning2, Informational1, Informational2
"""

from dataclasses import dataclass, field
from typing import List, Optional
from composition.models import ControllerConfig


@dataclass
class AlarmDef:
    point_name: str
    point_type: str  # AI, AO, AV, BI, BO, BV, MV
    alarm_type: str = "Critical"
    priority: str = "Critical2"
    delay: int = 60
    deadband: float = 1.0
    high: Optional[float] = None
    low: Optional[float] = None
    condition: str = ">"  # > for analog high/low, NORMAL/ALARM for binary
    message: str = ""
    reverse_logic: bool = False


# Default alarm settings per point type (from Dave's Alarm Builder)
ALARM_DEFAULTS = {
    "AI": {"alarm_type": "Critical", "priority": "Critical2", "delay": 60,
           "deadband": 1.0, "condition": ">", "message": "Analog High/Low Alarm"},
    "AO": {"alarm_type": "Warning", "priority": "Warning1", "delay": 60,
           "deadband": 1.0, "condition": ">", "message": "Output Alarm"},
    "BI": {"alarm_type": "General", "priority": "Informational1", "delay": 30,
           "condition": "NORMAL", "message": "Status Alarm"},
    "BO": {"alarm_type": "Warning", "priority": "Warning1", "delay": 30,
           "condition": "NORMAL", "message": "Command Status Alarm"},
    "BV": {"alarm_type": "Critical", "priority": "Critical2", "delay": 0,
           "condition": "NORMAL", "message": "Binary Alarm Active"},
    "AV": {"alarm_type": "Warning", "priority": "Warning1", "delay": 60,
           "deadband": 1.0, "condition": ">", "message": "Value Alarm"},
    "MV": {"alarm_type": "Information", "priority": "Informational1", "delay": 30,
           "condition": "NORMAL", "message": "Mode Change"},
}

# Points that should have alarms (by name pattern)
ALARM_POINTS = {
    # Safety points — Critical
    "FRZ-STS": {"alarm_type": "Critical", "priority": "Critical", "condition": "ALARM",
                 "message": "Freeze stat alarm", "delay": 0},
    "SMOKE-STS": {"alarm_type": "Critical", "priority": "Critical", "condition": "ALARM",
                   "message": "Smoke detector alarm", "delay": 0},
    "HI-STATIC-STS": {"alarm_type": "Critical", "priority": "Critical", "condition": "ALARM",
                       "message": "High static pressure alarm", "delay": 0},
    "FIRE-SD-STS": {"alarm_type": "Critical", "priority": "Critical", "condition": "ALARM",
                     "message": "Fire shutdown alarm", "delay": 0},
    "LTC-STS": {"alarm_type": "Critical", "priority": "Critical", "condition": "ALARM",
                 "message": "Low temp cutout alarm", "delay": 0},
    "COND-OVF-STS": {"alarm_type": "Critical", "priority": "Critical2", "condition": "ALARM",
                      "message": "Condensate overflow alarm", "delay": 30},

    # Fan status — Critical (fan failure)
    "SF-STS": {"alarm_type": "Critical", "priority": "Critical", "condition": "NORMAL",
                "message": "Supply fan failure", "delay": 60, "reverse_logic": True},
    "RF-STS": {"alarm_type": "Critical", "priority": "Critical", "condition": "NORMAL",
                "message": "Return fan failure", "delay": 60, "reverse_logic": True},
    "EF-STS": {"alarm_type": "Critical", "priority": "Critical", "condition": "NORMAL",
                "message": "Exhaust fan failure", "delay": 60, "reverse_logic": True},

    # Filter status — Warning
    "FLTR-STS": {"alarm_type": "Warning", "priority": "Warning1", "condition": "ALARM",
                  "message": "Filter dirty alarm", "delay": 0},
    "OA-FLTR-STS": {"alarm_type": "Warning", "priority": "Warning1", "condition": "ALARM",
                     "message": "OA filter dirty alarm", "delay": 0},
    "FINAL-FLTR-STS": {"alarm_type": "Warning", "priority": "Warning1", "condition": "ALARM",
                        "message": "Final filter dirty alarm", "delay": 0},

    # Pump status
    "HW-PMP-STS": {"alarm_type": "Critical", "priority": "Critical2", "condition": "NORMAL",
                    "message": "HW pump failure", "delay": 60, "reverse_logic": True},
    "CHW-PMP-STS": {"alarm_type": "Critical", "priority": "Critical2", "condition": "NORMAL",
                     "message": "CHW pump failure", "delay": 60, "reverse_logic": True},

    # Temperature alarms
    "SAT": {"alarm_type": "Warning", "priority": "Warning1", "delay": 300,
            "high": 120.0, "low": 35.0, "message": "Supply air temp alarm"},
    "MAT": {"alarm_type": "Warning", "priority": "Warning1", "delay": 300,
            "high": 130.0, "low": 30.0, "message": "Mixed air temp alarm"},
    "RAT": {"alarm_type": "Information", "priority": "Informational1", "delay": 300,
            "high": 90.0, "low": 55.0, "message": "Return air temp alarm"},

    # Safety shutdown BV
    "SAFETY-SD": {"alarm_type": "Critical", "priority": "Critical", "condition": "ALARM",
                   "message": "Safety shutdown active", "delay": 0},
}


def generate_alarms(config: ControllerConfig) -> List[AlarmDef]:
    """Generate alarm definitions for all points in the config."""
    alarms = []

    # Check inputs (AI/BI)
    for pt in config.inputs:
        alarm_override = None
        for pattern, settings in ALARM_POINTS.items():
            if pt.name.endswith(pattern) or pt.name == pattern:
                alarm_override = settings
                break

        if alarm_override:
            alm = AlarmDef(
                point_name=pt.name,
                point_type=pt.point_type,
                **alarm_override
            )
            alarms.append(alm)
        elif pt.point_type == "BI":
            # All BI status points get default alarm
            defaults = ALARM_DEFAULTS["BI"]
            alarms.append(AlarmDef(
                point_name=pt.name, point_type=pt.point_type,
                alarm_type=defaults["alarm_type"], priority=defaults["priority"],
                delay=defaults["delay"], condition=defaults["condition"],
                message=f"{pt.description or pt.name} alarm"
            ))

    # Check outputs (AO/BO) — alarm on status feedback
    for pt in config.outputs:
        if pt.point_type == "BO":
            for pattern, settings in ALARM_POINTS.items():
                if pt.name.endswith(pattern):
                    alarms.append(AlarmDef(point_name=pt.name, point_type=pt.point_type, **settings))
                    break

    # Check values (BV safety/status points)
    for val in config.values:
        for pattern, settings in ALARM_POINTS.items():
            if val.name.endswith(pattern) or val.name == pattern:
                alarms.append(AlarmDef(
                    point_name=val.name, point_type=val.point_type, **settings
                ))
                break

    return alarms


def generate_alarm_bas(config: ControllerConfig) -> str:
    """Generate the alarm .BAS program code."""
    alarms = generate_alarms(config)
    if not alarms:
        return ""

    lines = []
    line_num = 10
    lines.append(f"{line_num} REM {'='*50}")
    line_num += 10
    lines.append(f"{line_num} REM  Generated by SBS Composition Engine v2")
    line_num += 10
    lines.append(f"{line_num} REM  Alarm Definitions")
    line_num += 10
    lines.append(f"{line_num} REM {'='*50}")
    line_num += 10

    current_type = None
    current_priority = None

    for alm in alarms:
        # Set alarm type/priority when it changes
        if alm.alarm_type != current_type or alm.priority != current_priority:
            current_type = alm.alarm_type
            current_priority = alm.priority
            lines.append(f"{line_num} ALARM-TYPE {current_type} {current_priority}")
            line_num += 10

        # Build DALARM statement
        point_ref = f"{{device-name}}-{alm.point_name}"
        condition = alm.condition

        if alm.reverse_logic:
            if condition == "NORMAL":
                condition = "NOT NORMAL"
            elif condition == "ALARM":
                condition = "NOT ALARM"

        if alm.point_type == "AI" and alm.high is not None:
            # Analog alarm with high/low
            lines.append(f"{line_num} DALARM {point_ref} , {alm.delay} , {condition} ,")
            line_num += 10
        else:
            # Binary/status alarm
            lines.append(f"{line_num} DALARM {point_ref} , {alm.delay} , {condition} ,")
            line_num += 10

    lines.append(f"{line_num} END")
    return "\n".join(lines)


def generate_alarm_excel_data(config: ControllerConfig) -> List[dict]:
    """Generate alarm data for Excel tab."""
    alarms = generate_alarms(config)
    rows = []
    for alm in alarms:
        rows.append({
            "Point": f"{{device-name}}-{alm.point_name}",
            "Type": alm.point_type,
            "AlarmType": alm.alarm_type,
            "Priority": alm.priority,
            "Delay": alm.delay,
            "Deadband": alm.deadband if alm.point_type == "AI" else "",
            "High": alm.high or "",
            "Low": alm.low or "",
            "Condition": alm.condition,
            "Message": alm.message,
            "ReverseLogic": "Yes" if alm.reverse_logic else "",
        })
    return rows


def generate_commissioning_checklist(config: ControllerConfig) -> List[dict]:
    """
    Generate commissioning point checklist (from Dave's Report Generator concept).
    Creates Device+Point mnemonic for field checkout.
    """
    rows = []

    # Inputs — verify sensor readings
    for pt in config.inputs:
        rows.append({
            "Point": f"{{device-name}}-{pt.name}",
            "Object": f"{pt.point_type}{pt.row}",
            "Type": pt.point_type,
            "Range": pt.range_code,
            "Description": pt.description or "",
            "Check": "Verify sensor reading",
            "Expected": "Within range" if pt.point_type == "AI" else "Normal state",
            "Actual": "",
            "Pass": "",
            "Notes": "",
        })

    # Outputs — verify actuator response
    for pt in config.outputs:
        rows.append({
            "Point": f"{{device-name}}-{pt.name}",
            "Object": f"{pt.point_type}{pt.row}",
            "Type": pt.point_type,
            "Range": pt.range_code,
            "Description": pt.description or "",
            "Check": "Command and verify response",
            "Expected": "Follows command",
            "Actual": "",
            "Pass": "",
            "Notes": "",
        })

    # Key values — verify setpoints and modes
    for val in config.values:
        if val.point_type in ("MV", "BV") or (val.default and val.default != 0):
            rows.append({
                "Point": f"{{device-name}}-{val.name}",
                "Object": f"{val.point_type}{val.instance}",
                "Type": val.point_type,
                "Range": "",
                "Description": val.description or "",
                "Check": "Verify default value",
                "Expected": str(val.default),
                "Actual": "",
                "Pass": "",
                "Notes": "",
            })

    # Loops — verify PID operation
    for lp in config.loops:
        rows.append({
            "Point": f"{{device-name}}-{lp.name}",
            "Object": f"LOOP{lp.instance}",
            "Type": "LOOP",
            "Range": "",
            "Description": lp.description or "",
            "Check": f"Verify PID: P={lp.p_band}, I={lp.integral}, {lp.action}",
            "Expected": "Stable control",
            "Actual": "",
            "Pass": "",
            "Notes": "",
        })

    return rows
