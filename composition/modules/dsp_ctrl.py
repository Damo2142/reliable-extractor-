"""
DSP Control Module — Duct Static Pressure control for multi-zone AHUs.

Only included for VAV-AHU (always), DD-AHU, MZ-AHU (when VFD fan selected).
NOT included for CV-AHU, SZ-CV, SZ-VAV, RTU, DOAS.

Provides: DSP sensor, DSP setpoint reset, DSP PID loop, DSP scaling table.
"""

from composition.models import (
    Module, InputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, SystemGroupDef
)


def build():
    return Module(
        id="dsp-ctrl",
        name="Duct Static Pressure Control",
        category="dsp",
        description="DSP sensor, PID loop, setpoint reset — for multi-zone VAV ductwork",

        inputs=[
            InputPoint(12, "SA-DSP", "AI", "Table2", "Duct Static Pressure", "WC", "SA-DSP-TBL"),
        ],

        values=[
            ValuePoint(89, "INITIAL-DSP-SP",  "AV", 1.5,   "Initial DSP Setpoint",          "WC"),
            ValuePoint(90, "DSP-SP-INCR",     "AV", 0.1,   "DSP Reset Increment",           "WC"),
            ValuePoint(91, "DSP-RESET-INTRVL","AV", 10.0,  "DSP Reset Interval",            "Min."),
            ValuePoint(92, "ZONE-DMP-POS",    "AV", 100.0, "Zone Damper Position (highest)", "%"),
            ValuePoint(93, "ZONE-DMP-INC-SP", "AV", 95.0,  "Zone Damper Increase SP",       "%"),
            ValuePoint(94, "ZONE-DMP-DEC-SP", "AV", 90.0,  "Zone Damper Decrease SP",       "%"),
            ValuePoint(95, "DSP-MIN-SP",      "AV", 1.3,   "DSP Minimum Setpoint",          "WC"),
            ValuePoint(96, "DSP-MAX-SP",      "AV", 1.8,   "DSP Maximum Setpoint",          "WC"),
            ValuePoint(97, "ACT-DSP-SP",      "AV", 0.0,   "Active DSP Setpoint",           "WC"),
            ValuePoint(98, "ACT-DSP",         "AV", 0.0,   "Active DSP Reading",            "WC"),
        ],

        loops=[
            LoopDef(1, "ACT-DSP-LOOP", "ACT-DSP", "ACT-DSP-SP", "SF-VFD-SPD",
                    p_band=2.0, integral=50.0, action="reverse",
                    description="Duct Static Pressure"),
        ],

        tables=[
            TableDef(2, "SA-DSP-TBL", "Volts", "WC",
                     [[-1.0, 0.0], [0.0, 0.0], [5.0, 2.5], [10.0, 5.0], [11.0, 5.0]],
                     "Duct static pressure sensor scaling"),
        ],

        programs=[
            ProgramDef(13, "DSP-SP-PRG", "PRG13-DSP-SP.bas", "", True,
                       "Duct static pressure setpoint reset", exec_order=13),
        ],

        requires=["core", "fan-sf-vfd"],
    )
