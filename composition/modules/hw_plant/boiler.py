"""
HW-PLANT Boiler Modules — Cascade and Full Control

Cascade: Boilers have built-in controllers. SBS enables and sets supply temp.
Full Control: SBS directly controls fire rate modulation per boiler.

Both modules scale per number of boilers (1-4).
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, ScheduleDef, SystemGroupDef
)


# I/O rows for boiler inputs/outputs (fixed per boiler slot)
# Inputs start at row 5 for boiler module
_BLR_INPUT_BASE = 5      # BI: BLR1-ALARM at IN5, BLR2 at IN6, etc.
_BLR_HWST_BASE = 7       # AI: BLR1-HWST at IN7, BLR2 at IN9, etc. (if monitored)
_BLR_HWRT_BASE = 8       # AI: BLR1-HWRT at IN8, BLR2 at IN10, etc. (if monitored)
# Outputs: cascade starts at OUT1, full control at OUT1
_BLR_ENABLE_ROW = 1      # BO: BLRS-ENABLE (cascade only)
_BLR_SPT_AO_ROW = 2      # AO: BLRS-SPT (cascade, analog only)
_BLR_SS_BASE = 1          # BO: BLR1-S/S at OUT1, BLR2 at OUT2 (full control)
_BLR_MOD_BASE = 3         # AO: BLR1-MOD at OUT3, BLR2 at OUT4 (full control)


def build_blr_cascade(num_boilers=2, analog_spt=True, monitor_hwst=False):
    """Cascade boiler control — enable + supply temp setpoint.

    Args:
        num_boilers: 1-4 boilers
        analog_spt: True = AO output for setpoint, False = BACnet AV only
        monitor_hwst: True = add per-boiler supply temp AI
    """
    inputs = []
    outputs = []
    values = []

    # Per-boiler alarm inputs
    for n in range(1, num_boilers + 1):
        inputs.append(InputPoint(
            _BLR_INPUT_BASE + n - 1, f"BLR{n}-ALARM", "BI", "Normal/Alarm",
            f"Boiler {n} Alarm Contact"))

    # Per-boiler supply and return temps (optional)
    if monitor_hwst:
        for n in range(1, num_boilers + 1):
            inputs.append(InputPoint(
                _BLR_HWST_BASE + (n - 1) * 2, f"BLR{n}-HWST", "AI", "10K -40 ->250",
                f"Boiler {n} HW Supply Temperature", "°F"))
            inputs.append(InputPoint(
                _BLR_HWRT_BASE + (n - 1) * 2, f"BLR{n}-HWRT", "AI", "10K -40 ->250",
                f"Boiler {n} HW Return Temperature", "°F"))

    # System enable output
    outputs.append(OutputPoint(
        _BLR_ENABLE_ROW, "BLRS-ENABLE", "BO", "Stop/Start",
        "Boilers Enable Contact"))

    # Setpoint output — always generate AV, optionally AO
    values.append(ValuePoint(21, "BLRS-SPT", "AV", 160.0,
        "Boiler Supply Temp Setpoint (to boiler master)", "°F"))

    if analog_spt:
        outputs.append(OutputPoint(
            _BLR_SPT_AO_ROW, "BLRS-SPT-AO", "AO", "0.0 ->100%",
            "Boiler Setpoint Analog Output (0-10V)", 2.0, 10.0))

    # Boiler availability
    values.append(ValuePoint(22, "BLR-AVAIL", "BV", False, "Boilers Available"))

    # Per-boiler alarm status BVs
    for n in range(1, num_boilers + 1):
        values.append(ValuePoint(
            22 + n, f"BLR{n}-ALARM-STS", "BV", False,
            f"Boiler {n} Alarm Status"))

    # Cascade: NO lead/lag, NO rotation schedule for boilers
    # The boiler master controller handles its own internal staging
    # We just enable and set the supply temp setpoint

    programs = [
        ProgramDef(6, "HW-BLRS-PRG", "HW-PRG06-BLRS.bas", "", True,
                   "Cascade boiler enable and setpoint control", "hw-blr-cascade", exec_order=6),
    ]

    schedules = []

    return Module(
        id="hw-blr-cascade",
        name=f"Cascade Boiler Control ({num_boilers})",
        category="hw-boiler",
        description=f"Cascade control for {num_boilers} boiler(s) — enable + setpoint",

        inputs=inputs, outputs=outputs, values=values,
        programs=programs, schedules=schedules,

        system_groups=[
            SystemGroupDef("{device-name}-BOILER-CTRL", "Boiler status, alarms, setpoint"),
        ],

        soo_paragraph=f"""The hot water plant shall interface with {num_boilers} boiler(s) via
cascade control. A common enable contact shall energize the boiler master controller.
{"An analog 0-10V output shall communicate the supply temperature setpoint." if analog_spt else "The supply temperature setpoint shall be communicated via BACnet."}
Each boiler alarm contact shall be monitored. Lead boiler rotation {"shall be scheduled automatically." if num_boilers > 1 else "is not applicable for single boiler."}""",

        requires=["hw-core"],
        conflicts=["hw-blr-full"],
        mutually_exclusive_group="hw-boiler",
    )


def build_blr_full(num_boilers=2, monitor_hwst=True):
    """Full boiler control — direct fire rate modulation per boiler.

    Args:
        num_boilers: 1-4 boilers
        monitor_hwst: True = add per-boiler supply temp AI
    """
    inputs = []
    outputs = []
    values = []

    for n in range(1, num_boilers + 1):
        # Alarm input per boiler
        inputs.append(InputPoint(
            _BLR_INPUT_BASE + n - 1, f"BLR{n}-ALARM", "BI", "Normal/Alarm",
            f"Boiler {n} Alarm Contact"))

        # Supply and return temp per boiler
        if monitor_hwst:
            inputs.append(InputPoint(
                _BLR_HWST_BASE + (n - 1) * 2, f"BLR{n}-HWST", "AI", "10K -40 ->250",
                f"Boiler {n} HW Supply Temperature", "°F"))
            inputs.append(InputPoint(
                _BLR_HWRT_BASE + (n - 1) * 2, f"BLR{n}-HWRT", "AI", "10K -40 ->250",
                f"Boiler {n} HW Return Temperature", "°F"))

        # Start/stop per boiler
        outputs.append(OutputPoint(
            _BLR_SS_BASE + n - 1, f"BLR{n}-S/S", "BO", "Stop/Start",
            f"Boiler {n} Start/Stop"))

        # Fire rate modulation per boiler
        outputs.append(OutputPoint(
            _BLR_MOD_BASE + (n - 1) * 2, f"BLR{n}-MOD", "AO", "0.0 ->100%",
            f"Boiler {n} Fire Rate (0-10V)", 2.0, 10.0))

        # Per-boiler status BVs
        values.append(ValuePoint(21 + (n-1)*4, f"BLR{n}-SS", "BV", False,
            f"Boiler {n} Start/Stop Status"))
        values.append(ValuePoint(22 + (n-1)*4, f"BLR{n}-FAIL", "BV", False,
            f"Boiler {n} Failure"))
        values.append(ValuePoint(23 + (n-1)*4, f"BLR{n}-ALARM-STS", "BV", False,
            f"Boiler {n} Alarm Status"))
        values.append(ValuePoint(24 + (n-1)*4, f"BLR{n}-OOS", "BV", False,
            f"Boiler {n} Out of Service"))

        # Per-boiler fire rate config
        base_av = 35 + (n-1) * 6
        values.append(ValuePoint(base_av,   f"B{n}-LOW-FIRE",        "AV", 20.0,
            f"Boiler {n} Low Fire Rate", "%"))
        values.append(ValuePoint(base_av+1, f"B{n}-HI-FIRE",         "AV", 100.0,
            f"Boiler {n} High Fire Rate", "%"))
        values.append(ValuePoint(base_av+2, f"B{n}-START",           "AV", 20.0,
            f"Boiler {n} Start Fire Rate", "%"))
        values.append(ValuePoint(base_av+3, f"B{n}-STOP",            "AV", 0.0,
            f"Boiler {n} Stop Fire Rate", "%"))
        values.append(ValuePoint(base_av+4, f"B{n}-VOLT-BURN%-CNV",  "AV", 1.0,
            f"Boiler {n} Voltage to Burn % Conversion", ""))
        values.append(ValuePoint(base_av+5, f"B{n}-DEV",             "AV", 0.0,
            f"Boiler {n} Deviation from Setpoint", "°F"))

    # Per-boiler calculated fire rate value (from .bas: B1-VOLT-BURN, B2-VOLT-BURN)
    for n in range(1, num_boilers + 1):
        values.append(ValuePoint(80 + n, f"B{n}-VOLT-BURN", "AV", 0.0,
            f"Boiler {n} Voltage to Burn Rate (calculated)", "%"))

    # System-level values
    values.append(ValuePoint(29, "BLR-PURGE-DELAY", "AV", 30.0,
        "Boiler Purge Delay Before Ignition", "Sec"))
    values.append(ValuePoint(30, "BLR-SUPPLY-STPNT", "AV", 160.0,
        "Boiler Supply Temperature Setpoint", "°F"))
    values.append(ValuePoint(31, "TOTAL-BLRS-REQUESTED", "AV", 0.0,
        "Total Boilers Requested", "#"))

    if num_boilers > 1:
        values.append(ValuePoint(32, "LEAD-BLR", "AV", 1.0,
            "Lead Boiler Number", "#"))
        values.append(ValuePoint(33, "LEAD-BLR-DEV", "AV", 0.0,
            "Lead Boiler Deviation", "°F"))
        values.append(ValuePoint(34, "LEAD-BLR-SS",   "BV", False, "Lead Boiler Start/Stop"))
        values.extend([
            ValuePoint(70, "LAG-BLR-SS",   "BV", False, "Lag Boiler Start/Stop"),
            ValuePoint(71, "LEAD-BLR-FAIL","BV", False, "Lead Boiler Failure"),
        ])

    programs = [
        ProgramDef(6, "HW-BOILER-CTRL-PRG", "HW-PRG06-BOILER-CTRL.bas", "", True,
                   "Direct boiler staging and control", "hw-blr-full", exec_order=6),
        ProgramDef(7, "HW-BLR-STPT-FIRE-PRG", "HW-PRG07-BLR-STPT-FIRE.bas", "", True,
                   "Boiler setpoint and fire rate modulation", "hw-blr-full", exec_order=7),
    ]

    if num_boilers > 1:
        programs.append(ProgramDef(8, "HW-BLR-LEAD-LAG-PRG", "HW-PRG08-BLR-LEAD-LAG.bas", "", True,
                   "Boiler lead/lag rotation and staging", "hw-blr-full", exec_order=8))

    schedules = []
    if num_boilers > 1:
        schedules.append(ScheduleDef(2, "{device-name}-BLR-LEAD-SCHED", "Boiler 1",
            [f"Boiler {n}" for n in range(1, num_boilers + 1)], 10,
            "Boiler lead rotation schedule"))

    return Module(
        id="hw-blr-full",
        name=f"Full Boiler Control ({num_boilers})",
        category="hw-boiler",
        description=f"Direct fire rate control for {num_boilers} boiler(s)",

        inputs=inputs, outputs=outputs, values=values,
        programs=programs, schedules=schedules,

        system_groups=[
            SystemGroupDef("{device-name}-BOILER-CTRL", "Boiler staging, fire rate, alarms"),
        ],

        soo_paragraph=f"""The hot water plant shall provide direct modulating control of
{num_boilers} boiler(s). Each boiler shall have an individual start/stop contact and
0-10V fire rate modulation output. Boiler staging shall be based on supply temperature
deviation from setpoint. {"Lead/lag rotation shall alternate the lead boiler on a configurable schedule." if num_boilers > 1 else ""}
Each boiler fire rate shall ramp from low fire to high fire proportionally.
Voltage-to-burn-percentage conversion factors shall be configurable per boiler.""",

        requires=["hw-core"],
        conflicts=["hw-blr-cascade"],
        mutually_exclusive_group="hw-boiler",
    )
