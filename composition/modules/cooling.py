"""
Cooling Modules — CHW, DX-1, DX-2, DX-VFD, DX-3+, NONE

Based on A201: PRG42 (CHW-VLV-PRG)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, ProgramDef
)


def build_clg_chw():
    """Chilled water cooling — modulating valve"""
    return Module(
        id="clg-chw",
        name="Chilled Water Cooling",
        category="cooling",
        description="CHW cooling coil with modulating valve",

        inputs=[
            InputPoint(33, "CHWC-SUPW-T", "AI", "10K -40 ->250", "CHW Coil Supply Water Temp", "°F"),
            InputPoint(34, "CHWC-RETW-T", "AI", "10K -40 ->250", "CHW Coil Return Water Temp", "°F"),
        ],

        outputs=[
            OutputPoint(5, "CHW-VLV", "AO", "0.0 ->100%", "Chilled Water Valve", 2.0, 10.0),
        ],

        values=[
            ValuePoint(152, "CHW-AVAIL",  "BV", False, "Chilled Water Available"),
            ValuePoint(153, "CLG-RAMP",   "AV", 0.5,   "Cooling Valve Ramp Time",  "Min."),
            ValuePoint(154, "CHWS-CALL",  "BV", False, "CHW System Call"),
        ],

        loops=[
            LoopDef(8, "CHW-VLV-LOOP", "SAT", "ACT-SAT-SP", "CHW-VLV",
                    p_band=12.0, integral=40.0, action="direct",
                    description="Chilled Water Valve SAT Control"),
        ],

        programs=[
            ProgramDef(42, "CHW-VLV-PRG", "PRG42-CHW-VLV.bas", "", True,
                       "Chilled water valve modulation with lockout",
                       exec_order=42),
        ],

        soo_paragraph="""The chilled water cooling coil shall be controlled by a modulating 2-way valve.
The valve shall modulate to maintain supply air temperature setpoint during
cooling mode. Cooling shall be locked out when outdoor air temperature falls
below the cooling lockout setpoint. Chilled water availability shall be
confirmed from the plant controller before cooling is enabled. A chilled water
system call shall be generated when the valve has been open for more than
10 minutes continuously.""",

        requires=["core"],
        conflicts=["clg-dx", "clg-dx-2", "clg-dx-vfd", "clg-dx-3"],
        mutually_exclusive_group="cooling",
    )


def build_clg_dx():
    """DX cooling — single compressor stage"""
    return Module(
        id="clg-dx",
        name="DX Cooling 1-Stage",
        category="cooling",
        description="Single stage DX compressor cooling",

        inputs=[
            InputPoint(42, "DX-HP", "BI", "Normal/Alarm", "DX High Pressure Switch"),
            InputPoint(43, "DX-LP", "BI", "Normal/Alarm", "DX Low Pressure Switch"),
        ],

        outputs=[
            OutputPoint(20, "DX-COMP-1", "BO", "Stop/Start", "DX Compressor Stage 1"),
        ],

        values=[
            ValuePoint(210, "DX-MIN-ON-TIME",  "AV", 5.0,  "DX Minimum On Time",   "Min."),
            ValuePoint(211, "DX-MIN-OFF-TIME", "AV", 5.0,  "DX Minimum Off Time",  "Min."),
            ValuePoint(212, "DX-FAIL",         "BV", False, "DX Compressor Failure"),
        ],

        programs=[
            ProgramDef(42, "DX-CLG-PRG", "PRG42-DX-CLG.bas", "", True,
                       "DX cooling single stage with min on/off times",
                       exec_order=42),
        ],

        soo_paragraph="""A single-stage DX compressor shall provide cooling. The compressor
shall be energized in cooling mode with minimum on and off time protection.
High pressure and low pressure safety switches shall be monitored — any
trip shall de-energize the compressor and generate an alarm.""",

        requires=["core"],
        conflicts=["clg-chw", "clg-dx-2", "clg-dx-vfd"],
        mutually_exclusive_group="cooling",
    )


def build_clg_dx_2():
    """DX cooling — two compressor stages"""
    return Module(
        id="clg-dx-2",
        name="DX Cooling 2-Stage",
        category="cooling",
        description="Two stage DX compressor cooling",

        inputs=[
            InputPoint(42, "DX-HP", "BI", "Normal/Alarm", "DX High Pressure Switch"),
            InputPoint(43, "DX-LP", "BI", "Normal/Alarm", "DX Low Pressure Switch"),
        ],

        outputs=[
            OutputPoint(20, "DX-COMP-1", "BO", "Stop/Start", "DX Compressor Stage 1"),
            OutputPoint(21, "DX-COMP-2", "BO", "Stop/Start", "DX Compressor Stage 2"),
        ],

        values=[
            ValuePoint(210, "DX-MIN-ON-TIME",  "AV", 5.0,  "DX Minimum On Time",      "Min."),
            ValuePoint(211, "DX-MIN-OFF-TIME", "AV", 5.0,  "DX Minimum Off Time",     "Min."),
            ValuePoint(212, "DX-FAIL",         "BV", False, "DX Compressor Failure"),
            ValuePoint(213, "DX-STG2-SP",      "AV", 3.0,  "Stage 2 Enable Offset",   "°F"),
        ],

        programs=[
            ProgramDef(42, "DX-CLG-PRG", "PRG42-DX-CLG-2STG.bas", "", True,
                       "DX cooling 2-stage with staging logic",
                       exec_order=42),
        ],

        soo_paragraph="""Two-stage DX cooling shall be provided. Stage 1 shall energize in
cooling mode. Stage 2 shall energize when SAT exceeds setpoint by the
stage 2 offset. Both stages have minimum on/off time protection and
high/low pressure safety monitoring.""",

        requires=["core"],
        conflicts=["clg-chw", "clg-dx", "clg-dx-vfd"],
        mutually_exclusive_group="cooling",
    )


def build_clg_dx_vfd():
    """DX cooling — VFD compressor (variable speed)"""
    return Module(
        id="clg-dx-vfd",
        name="DX Cooling VFD",
        category="cooling",
        description="Variable speed DX compressor cooling",

        inputs=[
            InputPoint(42, "DX-HP", "BI", "Normal/Alarm", "DX High Pressure Switch"),
            InputPoint(43, "DX-LP", "BI", "Normal/Alarm", "DX Low Pressure Switch"),
        ],

        outputs=[
            OutputPoint(20, "DX-COMP-1",   "BO", "Stop/Start", "DX Compressor Enable"),
            OutputPoint(27, "DX-VFD-SPD",  "AO", "0.0 ->100%",   "DX VFD Compressor Speed", 0.0, 10.0),
        ],

        values=[
            ValuePoint(210, "DX-MIN-ON-TIME",  "AV", 5.0,   "DX Minimum On Time",    "Min."),
            ValuePoint(211, "DX-MIN-OFF-TIME", "AV", 5.0,   "DX Minimum Off Time",   "Min."),
            ValuePoint(212, "DX-FAIL",         "BV", False,  "DX Compressor Failure"),
            ValuePoint(214, "DX-MIN-SPEED",    "AV", 30.0,  "DX Min Compressor Speed","%"),
            ValuePoint(215, "DX-MAX-SPEED",    "AV", 100.0, "DX Max Compressor Speed","%"),
            ValuePoint(153, "CLG-RAMP",        "AV", 0.5,   "Cooling VFD Ramp Time",  "Min."),
        ],

        programs=[
            ProgramDef(42, "DX-VFD-PRG", "PRG42-DX-VFD.bas", "", True,
                       "DX cooling VFD modulating control",
                       exec_order=42),
        ],

        soo_paragraph="""A variable-speed DX compressor shall provide cooling. Compressor speed
shall modulate to maintain supply air temperature setpoint. Minimum on/off
time protection and high/low pressure safety monitoring shall be provided.""",

        requires=["core"],
        conflicts=["clg-chw", "clg-dx", "clg-dx-2"],
        mutually_exclusive_group="cooling",
    )
