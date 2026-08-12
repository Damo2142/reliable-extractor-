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


# ═══════════════════════════════════════════════════════════════════════════
#  UV alarm program
# ═══════════════════════════════════════════════════════════════════════════
# UV alarms are built from an explicit spec instead of point-name pattern
# matching. Two reasons: the description has to name the fault AND what it
# costs the building, which no generic rule can produce; and most real UV
# faults are derived conditions (commanded vs proven, discharge vs limit)
# that no single point carries. Derived conditions latch into a local, and
# the DALARM delay does the debounce.

DALARM_MAX_DESC = 69   # Control-BASIC manual limit on the DALARM string

# Locals used for latched conditions, assigned in order of appearance.
_UV_LOCALS = "ABCDEFGHIJ"


@dataclass
class UVAlarm:
    """One UV alarm — either a point alarm or a latched derived condition."""
    description: str
    delay: int
    alarm_type: str = "Critical"
    priority: str = "Critical"
    point: str = ""      # existing point, alarmed directly
    latch: str = ""      # expression latched into a local first
    local: str = ""      # assigned by the builder when latch is set


def _uv_alarm_specs(config: ControllerConfig) -> List[UVAlarm]:
    """Build the UV alarm list for whatever modules this config actually has."""
    names = {p.name for p in list(config.inputs) + list(config.outputs) + list(config.values)}
    mods = set(getattr(config, "selected_modules", []) or [])
    d = "{device-name}-"
    alarms: List[UVAlarm] = []

    # Fan proof — commanded but no status feedback. CV fan proves off the
    # start/stop output, VFD fan off commanded speed.
    if "SF-STS" in names:
        if "FAN-S/S" in names:
            cmd = f"{d}FAN-S/S"
        elif "FAN-SPD" in names:
            cmd = f"{d}FAN-SPD > 0"
        else:
            cmd = f"{d}FAN-CMD"
        alarms.append(UVAlarm(
            description="Fan Failure - No Status",
            delay=60, alarm_type="Critical", priority="Critical",
            latch=f"{cmd} AND NOT {d}SF-STS"))

    # Freezestat — already latched by FREEZESTAT, so it alarms with no delay.
    if "FREEZE-ALARM" in names:
        alarms.insert(0, UVAlarm(
            description="Freeze Trip - Coil Protection",
            delay=0, alarm_type="Critical", priority="Critical",
            point="FREEZE-ALARM"))

    # Discharge outside its limits while air is actually moving.
    if {"SF-STS", "ACT-DAT", "CFG-DAT-LL"} <= names:
        alarms.append(UVAlarm(
            description="Discharge Air Low Limit - Coil Freeze Risk",
            delay=120, alarm_type="Critical", priority="Critical2",
            latch=f"{d}SF-STS AND {d}ACT-DAT < {d}CFG-DAT-LL"))
    if {"SF-STS", "ACT-DAT", "CFG-DAT-HL"} <= names:
        alarms.append(UVAlarm(
            description="Discharge Air High Limit - Coil Overheat",
            delay=120, alarm_type="Critical", priority="Critical2",
            latch=f"{d}SF-STS AND {d}ACT-DAT > {d}CFG-DAT-HL"))

    # Hot water lost while the arbiter is calling for heat. HW families only —
    # HWS-OK exists on every UV, but it means nothing on a steam or DX unit.
    if mods & {"uv-hw-mod", "uv-hw-flt", "uv-hw-mod-fbp"} and {"HWS-OK", "HVAC-MODE"} <= names:
        alarms.append(UVAlarm(
            description="Hot Water Unavailable - No Heating Capacity",
            delay=300, alarm_type="Warning", priority="Warning1",
            latch=f"{d}HVAC-MODE = 4 AND NOT {d}HWS-OK"))

    # CO2 above setpoint — DCV module sets this.
    if "CO2-ALARM" in names:
        alarms.append(UVAlarm(
            description="High CO2 - Ventilation Below Demand",
            delay=300, alarm_type="Warning", priority="Warning1",
            point="CO2-ALARM"))

    # Return air high — rat-local sensor module sets this.
    if "RAT-HI" in names:
        alarms.append(UVAlarm(
            description="Return Air High Temp - Check Unit",
            delay=300, alarm_type="Warning", priority="Warning1",
            point="RAT-HI"))

    # A single freeze trip stops the fan without latching the lockout, so it
    # would otherwise be silent until the third trip inside the window.
    if mods & {"uv-freezestat"} and "FRZ-SD" in names:
        alarms.append(UVAlarm(
            description="Freeze Trip Active - Fan Stopped",
            delay=0, alarm_type="Warning", priority="Warning1",
            point="FRZ-SD"))

    # Parent OAT reference dead or implausible — unit is on its local sensor.
    if "NET-OAT-OK" in names:
        alarms.append(UVAlarm(
            description="Parent OAT Comms Lost - Local Sensor In Use",
            delay=300, alarm_type="Warning", priority="Warning1",
            latch=f"NOT {d}NET-OAT-OK"))

    # Assign locals to the latched conditions, in order.
    nxt = 0
    for alm in alarms:
        if alm.latch:
            if nxt >= len(_UV_LOCALS):
                raise ValueError("UV alarm program needs more locals than A-J")
            alm.local = _UV_LOCALS[nxt]
            nxt += 1
        if len(alm.description) > DALARM_MAX_DESC:
            raise ValueError(
                f"DALARM description over {DALARM_MAX_DESC} chars: {alm.description!r}")
    return alarms


def _generate_uv_alarm_bas(config: ControllerConfig) -> str:
    """UV alarm .BAS — ALARM-TYPE, then its latches, then its DALARM lines."""
    alarms = _uv_alarm_specs(config)
    if not alarms:
        return ""

    lines = ["REM --- Alarm Definitions ---", "REM"]
    current = None
    for alm in alarms:
        group = [a for a in alarms
                 if (a.alarm_type, a.priority) == (alm.alarm_type, alm.priority)]
        if (alm.alarm_type, alm.priority) == current:
            continue
        current = (alm.alarm_type, alm.priority)
        lines.append(f"ALARM-TYPE {alm.alarm_type} {alm.priority}")
        for a in group:
            if a.latch:
                lines.append(f"IF {a.latch} THEN START {a.local} ELSE STOP {a.local}")
        for a in group:
            ref = a.local if a.local else "{device-name}-" + a.point
            lines.append(f"DALARM {ref} , {a.delay} ,  {a.description}")
    lines.append("END")

    return "\n".join(f"{(i + 1) * 10} {ln}" for i, ln in enumerate(lines))


def generate_alarm_bas(config: ControllerConfig) -> str:
    """Generate the alarm .BAS program code."""
    if str(getattr(config, "equipment_family", "")).startswith("UV-"):
        return _generate_uv_alarm_bas(config)

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
    if str(getattr(config, "equipment_family", "")).startswith("UV-"):
        rows = []
        for alm in _uv_alarm_specs(config):
            rows.append({
                "Point": alm.local if alm.local else "{device-name}-" + alm.point,
                "Type": "LOCAL" if alm.local else "BV",
                "AlarmType": alm.alarm_type,
                "Priority": alm.priority,
                "Delay": alm.delay,
                "Deadband": "",
                "High": "",
                "Low": "",
                "Condition": alm.latch if alm.latch else "ACTIVE",
                "Message": alm.description,
                "ReverseLogic": "",
            })
        return rows

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

    # Key values — verify setpoints and modes.
    # Always include CFG- configuration setpoints regardless of default value
    # (a zero default like 0 deg F / 0% is still a real setpoint a tech must verify).
    for val in config.values:
        if (val.point_type in ("MV", "BV")
                or val.name.startswith("CFG-")
                or (val.default and val.default != 0)):
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
