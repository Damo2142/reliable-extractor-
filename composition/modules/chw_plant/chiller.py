"""
CHW-PLANT Chiller Module — BACnet chiller enable/staging/lead-lag

Chillers are always third-party BACnet devices. SBS sends enable,
reads status/alarms, monitors supply/return temps. Staging based on
lag enable setpoint (load %) with min on/off timers.

Scales per number of chillers (1-4).
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)

_CHLR_ALARM_BASE = 6     # BI: CHLR1-ALARM at IN6, CHLR2 at IN7, etc.
_CHLR_CHWS_T_BASE = 8    # AI: CHLR1-CHWS-T at IN8, CHWR-T at IN9, etc.
_CHLR_ENABLE_BASE = 1    # BO: CHLR1-ENABLE at OUT1, CHLR2 at OUT2, etc.


def build_chiller(num_chillers=2):
    """Chiller control — BACnet enable, staging, lead/lag.

    Args:
        num_chillers: 1-4 chillers
    """
    inputs = []
    outputs = []
    values = []
    programs = []
    schedules = []

    # Per-chiller I/O
    for n in range(1, num_chillers + 1):
        # Alarm contact (BI)
        inputs.append(InputPoint(
            _CHLR_ALARM_BASE + n - 1, f"CHLR{n}-ALARM", "BI", "Normal/Alarm",
            f"Chiller {n} Alarm Contact"))

        # Supply and return temps (AI)
        inputs.append(InputPoint(
            _CHLR_CHWS_T_BASE + (n - 1) * 2, f"CHLR{n}-CHWS-T", "AI", "10K -40 ->250",
            f"Chiller {n} Leaving CHW Temperature", "°F"))
        inputs.append(InputPoint(
            _CHLR_CHWS_T_BASE + (n - 1) * 2 + 1, f"CHLR{n}-CHWR-T", "AI", "10K -40 ->250",
            f"Chiller {n} Entering CHW Temperature", "°F"))

        # Enable output (BO) — .bas references CHLR{N}-S/S for START/STOP
        outputs.append(OutputPoint(
            _CHLR_ENABLE_BASE + n - 1, f"CHLR{n}-S/S", "BO", "Stop/Start",
            f"Chiller {n} Start/Stop Enable"))

        # Per-chiller status values (8 per chiller starting at 21)
        base = 21 + (n - 1) * 8
        values.append(ValuePoint(base,     f"CHLR{n}-FAIL", "BV", False,
            f"Chiller {n} Failure"))
        values.append(ValuePoint(base + 1, f"CHLR{n}-IN-SERVICE", "BV", True,
            f"Chiller {n} In Service"))
        values.append(ValuePoint(base + 2, f"CHLR{n}-STS", "BV", False,
            f"Chiller {n} Running Status"))
        values.append(ValuePoint(base + 3, f"CHLR{n}-ALARM-STS", "BV", False,
            f"Chiller {n} Alarm Status"))
        values.append(ValuePoint(base + 4, f"CHLR{n}-MIN-RUN", "AV", 0.0,
            f"Chiller {n} Min Run Timer", "Min"))
        values.append(ValuePoint(base + 5, f"CHLR{n}-OOS", "BV", False,
            f"Chiller {n} Out of Service"))
        values.append(ValuePoint(base + 6, f"CHLR{n}-RUNTIME", "AV", 0.0,
            f"Chiller {n} Runtime", "Hrs"))
        values.append(ValuePoint(base + 7, f"CHLR{n}-SS", "BV", False,
            f"Chiller {n} Start/Stop Command"))
        # Per-chiller setpoint (from .bas: CHLR1-CHWS-SP)
        values.append(ValuePoint(53 + (n - 1), f"CHLR{n}-CHWS-SP", "AV", 44.0,
            f"Chiller {n} CHW Supply Setpoint", "°F"))

    # System-level chiller values (55+)
    values.append(ValuePoint(55, "CHLR-CHWS-SP", "AV", 44.0,
        "System CHW Supply Setpoint", "°F"))
    values.append(ValuePoint(56, "TOTAL-CHLRS-REQUESTED", "AV", 0.0,
        "Total Chillers Requested", "#"))
    values.append(ValuePoint(57, "CHLR-MIN-ON-TIME", "AV", 10.0,
        "Chiller Min On Time", "Min"))
    values.append(ValuePoint(58, "CHLR-MIN-OFF-TIME", "AV", 10.0,
        "Chiller Min Off Time", "Min"))
    values.append(ValuePoint(59, "CHLR-ALARM-DELAY", "AV", 30.0,
        "Chiller Alarm Delay", "Sec"))

    if num_chillers > 1:
        values.append(ValuePoint(60, "LEAD-CHLR", "AV", 1.0,
            "Lead Chiller Number", "#"))
        values.append(ValuePoint(61, "CHLR-LAG-ENABLE", "BV", False,
            "Lag Chiller Enable"))
        values.append(ValuePoint(62, "CHLR-LAG-SP", "AV", 85.0,
            "Lag Chiller Load Threshold", "%"))
        values.append(ValuePoint(63, "CHLR-LAG-DELAY", "AV", 15.0,
            "Lag Chiller Start Delay", "Min"))
        values.append(ValuePoint(64, "CHLR-SWITCH-DELAY", "AV", 5.0,
            "Lead/Lag Switch Delay", "Min"))
        values.append(ValuePoint(65, "CHLR-ROTATION-HOLD", "AV", 168.0,
            "Min Hours Before Chiller Rotation", "Hrs"))
        values.append(ValuePoint(66, "LEAD-CHLR-SS", "BV", False,
            "Lead Chiller Start/Stop"))
        values.append(ValuePoint(67, "LAG-CHLR-SS", "BV", False,
            "Lag Chiller Start/Stop"))
        values.append(ValuePoint(68, "LEAD-CHLR-FAIL", "BV", False,
            "Lead Chiller Failure"))

    # Programs
    programs.append(ProgramDef(6, "CHW-CHLR-CTRL-PRG", "CHW-PRG06-CHLR-CTRL.bas", "", True,
        "Chiller enable, staging, alarm monitoring", "chw-chlr", exec_order=6))

    if num_chillers > 1:
        programs.append(ProgramDef(7, "CHW-CHLR-LEAD-LAG-PRG", "CHW-PRG07-CHLR-LEAD-LAG.bas", "", True,
            "Chiller lead/lag rotation and staging", "chw-chlr", exec_order=7))
        schedules.append(ScheduleDef(2, "{device-name}-CHLR-LEAD-SCHED",
            "Chiller 1", [f"Chiller {n}" for n in range(1, num_chillers + 1)], 10,
            "Chiller lead rotation schedule"))

    return Module(
        id="chw-chlr",
        name=f"Chiller Control ({num_chillers})",
        category="chw-chiller",
        description=f"BACnet chiller enable/staging for {num_chillers} chiller(s)",
        requires=["chw-core"],
        conflicts=[],
        mutually_exclusive_group="chw-chiller",

        inputs=inputs,
        outputs=outputs,
        values=values,
        loops=[],
        tables=[],
        programs=programs,
        schedules=schedules,

        system_groups=[
            SystemGroupDef("{device-name}-CHILLER-CTRL",
                "Chiller status, alarms, staging, setpoint"),
        ],

        soo_paragraph=f"""The controller shall manage {num_chillers} chiller(s) via BACnet enable
contacts. Each chiller enable requires: CHW system enabled, primary pump proven,
chiller in service, no active alarm, and minimum off time satisfied. Chiller failure
is detected via alarm contact with configurable delay. {'Lead/lag rotation is managed via schedule with automatic failover. Lag chiller stages on when load exceeds the lag threshold setpoint for the configured delay period.' if num_chillers > 1 else 'Single chiller operation — no lead/lag required.'}""",
    )
