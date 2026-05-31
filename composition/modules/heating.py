"""
Heating Modules — HW, Electric (1/2/3/SCR), Gas (1/2/MOD), Steam

Based on A201: PRG39 (HW-VLV-PRG), PRG5 (FRZ-PRTN-MODE), PRG6 (HTG-CLG-LO)
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, ProgramDef
)


def build_htg_hw():
    """Hot water heating coil — modulating valve"""
    return Module(
        id="htg-hw",
        name="Hot Water Heating",
        category="heating",
        description="HW heating coil with modulating valve, freeze protection, lockout",

        inputs=[
            InputPoint(8,  "HWC-DAT",    "AI", "10K -40 ->250", "HW Coil Discharge Air Temp", "°F"),
            InputPoint(31, "HWC-SUPW-T", "AI", "10K -40 ->250", "HW Coil Supply Water Temp",  "°F"),
            InputPoint(32, "HWC-RETW-T", "AI", "10K -40 ->250", "HW Coil Return Water Temp",  "°F"),
        ],

        outputs=[
            OutputPoint(4, "HW-VLV", "AO", "0.0 ->100%", "Hot Water Valve (reverse)", 10.0, 2.0, True),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",       "AV", 65.0,  "Heating Lockout OAT SP",     "°F"),
            ValuePoint(56, "HTG-LOCKOUT",      "BV", True,  "Heating Lockout Active"),
            ValuePoint(57, "HTG-LO-ICON",      "BV", False, "Heating Lockout Icon"),
            ValuePoint(58, "CLG-LO-SP",        "AV", 55.0,  "Cooling Lockout OAT SP",     "°F"),
            ValuePoint(59, "CLG-LOCKOUT",      "BV", False, "Cooling Lockout Active"),
            ValuePoint(60, "CLG-LO-ICON",      "BV", True,  "Cooling Lockout Icon"),
            ValuePoint(52, "FRZ-PRTC-SP",      "AV", 25.0,  "Freeze Protection OAT SP",   "°F"),
            ValuePoint(53, "FRZ-PRTC-MODE",    "BV", False, "Freeze Protection Mode"),
            ValuePoint(78, "HWC-SAT-SP",       "AV", 52.0,  "HW Coil SAT Setpoint",       "°F"),
            ValuePoint(150,"HTG-RAMP",         "AV", 0.5,   "Heating Valve Ramp Time",    "Min."),
            ValuePoint(151,"HW-AVAIL",         "BV", False, "Hot Water Available"),
            ValuePoint(171,"HTG-VLV-FREEZE-SP","AV", 110.0, "HW Valve Freeze SP",         "°F"),
        ],

        loops=[
            LoopDef(7, "HW-VLV-LOOP", "HWC-DAT", "ACT-SAT-SP", "HW-VLV",
                    p_band=12.0, integral=40.0, action="reverse",
                    description="Hot Water Valve SAT Control"),
            LoopDef(9, "FRZ-LOOP", "HWC-DAT", "HTG-VLV-FREEZE-SP", "HW-VLV",
                    p_band=12.0, integral=40.0, action="reverse",
                    description="Freeze Protection Valve Override"),
        ],

        programs=[
            ProgramDef(39, "HW-VLV-PRG", "PRG39-HW-VLV.bas", "", True,
                       "Hot water valve modulation with freeze and lockout",
                       exec_order=39),
            ProgramDef(5, "FRZ-PRTN-MODE-PRG", "PRG05-FRZ-PRTN-MODE.bas", "", True,
                       "Freeze protection mode determination",
                       exec_order=5),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout determination",
                       exec_order=6),
        ],

        soo_paragraph="""The hot water heating coil shall be controlled by a modulating 2-way valve.
The valve shall modulate to maintain supply air temperature setpoint during
heating mode. The valve actuator shall be reverse-acting (fail-open) for
freeze protection. Upon low temperature cutout, the valve shall drive to
100% open. Freeze protection mode shall activate when outdoor air temperature
falls below the freeze protection setpoint. Heating lockout shall be based
on outdoor air temperature. Hot water availability shall be confirmed from
the plant controller before heating is enabled.""",

        requires=["core"],
        conflicts=["htg-elec", "htg-elec-2", "htg-elec-3", "htg-elec-scr",
                   "htg-gas", "htg-gas-2", "htg-gas-3", "htg-gas-4",
                   "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_elec():
    """Electric heat — 1 stage"""
    return Module(
        id="htg-elec",
        name="Electric Heat 1-Stage",
        category="heating",
        description="Single stage electric heat with lockout",

        outputs=[
            OutputPoint(22, "ELEC-HTR-1", "BO", "Stop/Start", "Electric Heater Stage 1"),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",    "AV", 65.0,  "Heating Lockout OAT SP",  "°F"),
            ValuePoint(56, "HTG-LOCKOUT",   "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",     "AV", 55.0,  "Cooling Lockout OAT SP",  "°F"),
            ValuePoint(59, "CLG-LOCKOUT",   "BV", False, "Cooling Lockout Active"),
        ],

        programs=[
            ProgramDef(39, "ELEC-HTR-PRG", "PRG39-ELEC-HTR.bas", "", True,
                       "Electric heat staging with lockout",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout determination",
                       exec_order=6),
        ],

        soo_paragraph="""A single-stage electric heater shall be energized when the unit is in
heating mode and outdoor air temperature is below the heating lockout
setpoint. The heater shall be de-energized during cooling lockout and
upon any safety shutdown condition.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-gas", "htg-gas-2", "htg-gas-3", "htg-gas-4",
                   "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_elec_2():
    """Electric heat — 2 stages"""
    return Module(
        id="htg-elec-2",
        name="Electric Heat 2-Stage",
        category="heating",
        description="Two stage electric heat with lockout and staging",

        outputs=[
            OutputPoint(22, "ELEC-HTR-1", "BO", "Stop/Start", "Electric Heater Stage 1"),
            OutputPoint(23, "ELEC-HTR-2", "BO", "Stop/Start", "Electric Heater Stage 2"),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",    "AV", 65.0,  "Heating Lockout OAT SP",   "°F"),
            ValuePoint(56, "HTG-LOCKOUT",   "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",     "AV", 55.0,  "Cooling Lockout OAT SP",   "°F"),
            ValuePoint(59, "CLG-LOCKOUT",   "BV", False, "Cooling Lockout Active"),
            ValuePoint(200,"ELEC-STG2-SP",  "AV", 5.0,   "Stage 2 Enable Offset",    "°F"),
        ],

        programs=[
            ProgramDef(39, "ELEC-HTR-PRG", "PRG39-ELEC-HTR-2STG.bas", "", True,
                       "Electric heat 2-stage control",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout determination",
                       exec_order=6),
        ],

        soo_paragraph="""Two-stage electric heating shall be provided. Stage 1 shall energize
when the unit is in heating mode. Stage 2 shall energize when supply air
temperature drops more than the stage 2 offset below setpoint. Stages
shall de-energize during cooling lockout and upon any safety shutdown.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-gas", "htg-gas-2", "htg-gas-3",
                   "htg-gas-4", "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_elec_3():
    """Electric heat — 3 stages"""
    return Module(
        id="htg-elec-3",
        name="Electric Heat 3-Stage",
        category="heating",
        description="Three stage electric heat",

        outputs=[
            OutputPoint(22, "ELEC-HTR-1", "BO", "Stop/Start", "Electric Heater Stage 1"),
            OutputPoint(23, "ELEC-HTR-2", "BO", "Stop/Start", "Electric Heater Stage 2"),
            OutputPoint(24, "ELEC-HTR-3", "BO", "Stop/Start", "Electric Heater Stage 3"),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",    "AV", 65.0,  "Heating Lockout OAT SP",   "°F"),
            ValuePoint(56, "HTG-LOCKOUT",   "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",     "AV", 55.0,  "Cooling Lockout OAT SP",   "°F"),
            ValuePoint(59, "CLG-LOCKOUT",   "BV", False, "Cooling Lockout Active"),
            ValuePoint(200,"ELEC-STG2-SP",  "AV", 5.0,   "Stage 2 Enable Offset",    "°F"),
            ValuePoint(201,"ELEC-STG3-SP",  "AV", 10.0,  "Stage 3 Enable Offset",    "°F"),
        ],

        programs=[
            ProgramDef(39, "ELEC-HTR-PRG", "PRG39-ELEC-HTR-3STG.bas", "", True,
                       "Electric heat 3-stage control",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout determination",
                       exec_order=6),
        ],

        soo_paragraph="""Three-stage electric heating shall be provided. Stages shall be
sequenced based on supply air temperature deviation from setpoint.
Each stage adds when the previous stage cannot satisfy the load.
All stages de-energize during cooling lockout and safety shutdown.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-elec-2", "htg-gas", "htg-gas-2",
                   "htg-gas-3", "htg-gas-4", "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_elec_scr():
    """Electric heat — SCR modulating"""
    return Module(
        id="htg-elec-scr",
        name="Electric Heat SCR (Modulating)",
        category="heating",
        description="Modulating electric heat via SCR controller",

        outputs=[
            OutputPoint(28, "ELEC-SCR", "AO", "0.0 ->100%", "Electric Heat SCR Output", 0.0, 10.0),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",    "AV", 65.0,  "Heating Lockout OAT SP",  "°F"),
            ValuePoint(56, "HTG-LOCKOUT",   "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",     "AV", 55.0,  "Cooling Lockout OAT SP",  "°F"),
            ValuePoint(59, "CLG-LOCKOUT",   "BV", False, "Cooling Lockout Active"),
            ValuePoint(150,"HTG-RAMP",      "AV", 0.5,   "Heating Ramp Time",       "Min."),
        ],

        programs=[
            ProgramDef(39, "ELEC-SCR-PRG", "PRG39-ELEC-SCR.bas", "", True,
                       "Electric heat SCR modulating control",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout",
                       exec_order=6),
        ],

        soo_paragraph="""Modulating electric heat shall be provided via SCR controller.
The heating output shall modulate 0-100% to maintain supply air
temperature setpoint during heating mode.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-gas", "htg-gas-2", "htg-gas-3",
                   "htg-gas-4", "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_gas():
    """Gas heat — single stage"""
    return Module(
        id="htg-gas",
        name="Gas Heat 1-Stage",
        category="heating",
        description="Single stage gas-fired heat",

        inputs=[
            InputPoint(44, "GAS-PRSR", "BI", "Normal/Alarm", "Gas Pressure Switch"),
        ],

        outputs=[
            OutputPoint(25, "GAS-VLV-1", "BO", "Stop/Start", "Gas Valve Stage 1"),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",    "AV", 65.0,  "Heating Lockout OAT SP",  "°F"),
            ValuePoint(56, "HTG-LOCKOUT",   "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",     "AV", 55.0,  "Cooling Lockout OAT SP",  "°F"),
            ValuePoint(59, "CLG-LOCKOUT",   "BV", False, "Cooling Lockout Active"),
            ValuePoint(61, "GAS-FAIL",      "BV", False, "Gas Heat Failure Alarm"),
        ],

        programs=[
            ProgramDef(39, "GAS-HTR-PRG", "PRG39-GAS-HTR.bas", "", True,
                       "Gas heat single stage",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout",
                       exec_order=6),
        ],

        soo_paragraph="""A single-stage gas-fired heater shall be energized when the unit is
in heating mode and outdoor temperature is below heating lockout. A gas
pressure switch shall be monitored — loss of gas pressure shall prevent
heater operation and generate an alarm.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-elec-2", "htg-elec-3", "htg-elec-scr",
                   "htg-gas-2", "htg-gas-3", "htg-gas-4", "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_gas_mod():
    """Gas heat — modulating"""
    return Module(
        id="htg-gas-mod",
        name="Gas Heat Modulating",
        category="heating",
        description="Modulating gas-fired heat",

        inputs=[
            InputPoint(44, "GAS-PRSR", "BI", "Normal/Alarm", "Gas Pressure Switch"),
        ],

        outputs=[
            OutputPoint(25, "GAS-VLV-1", "BO", "Stop/Start", "Gas Valve Enable"),
            OutputPoint(29, "GAS-MOD",   "AO", "0.0 ->100%",  "Gas Modulating Output", 2.0, 10.0),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",    "AV", 65.0,  "Heating Lockout OAT SP",  "°F"),
            ValuePoint(56, "HTG-LOCKOUT",   "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",     "AV", 55.0,  "Cooling Lockout OAT SP",  "°F"),
            ValuePoint(59, "CLG-LOCKOUT",   "BV", False, "Cooling Lockout Active"),
            ValuePoint(61, "GAS-FAIL",      "BV", False, "Gas Heat Failure Alarm"),
            ValuePoint(150,"HTG-RAMP",      "AV", 0.5,   "Heating Ramp Time",       "Min."),
        ],

        programs=[
            ProgramDef(39, "GAS-MOD-PRG", "PRG39-GAS-MOD.bas", "", True,
                       "Gas heat modulating control",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout",
                       exec_order=6),
        ],

        soo_paragraph="""A modulating gas-fired heater shall be provided. The gas valve shall
enable in heating mode and the modulating output shall control firing rate
to maintain supply air temperature setpoint.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-elec-2", "htg-elec-3", "htg-elec-scr",
                   "htg-gas", "htg-gas-2", "htg-gas-3", "htg-gas-4", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_gas_2():
    """Gas heat — 2 stages"""
    return Module(
        id="htg-gas-2",
        name="Gas Heat 2-Stage",
        category="heating",
        description="Two stage gas-fired heat with loop-output staging",

        inputs=[
            InputPoint(44, "GAS-PRSR", "BI", "Normal/Alarm", "Gas Pressure Switch"),
        ],

        outputs=[
            OutputPoint(25, "GAS-VLV-1", "BO", "Stop/Start", "Gas Valve Stage 1"),
            OutputPoint(26, "GAS-VLV-2", "BO", "Stop/Start", "Gas Valve Stage 2"),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",     "AV", 65.0,  "Heating Lockout OAT SP",   "°F"),
            ValuePoint(56, "HTG-LOCKOUT",    "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",      "AV", 55.0,  "Cooling Lockout OAT SP",   "°F"),
            ValuePoint(59, "CLG-LOCKOUT",    "BV", False, "Cooling Lockout Active"),
            ValuePoint(61, "GAS-FAIL",       "BV", False, "Gas Heat Failure Alarm"),
            ValuePoint(202,"GAS-STG2-SP",    "AV", 50.0,  "Stage 2 Loop Enable %",    "%"),
        ],

        programs=[
            ProgramDef(39, "GAS-HTR-PRG", "PRG39-GAS-HTR-2STG.bas", "", True,
                       "Gas heat 2-stage loop-threshold control",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout",
                       exec_order=6),
        ],

        soo_paragraph="""Two-stage gas-fired heating shall be provided. Stage 1 shall energize
when the heating loop output exceeds 25% in heating mode. Stage 2 shall
energize when the heating loop output exceeds the Stage 2 enable setpoint
(default 50%). A shared gas pressure switch shall be monitored — loss of
gas pressure shall disable both stages and generate a single gas failure
alarm. Both stages shall de-energize during cooling lockout, fan off, or
any safety shutdown.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-elec-2", "htg-elec-3", "htg-elec-scr",
                   "htg-gas", "htg-gas-3", "htg-gas-4", "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_gas_3():
    """Gas heat — 3 stages"""
    return Module(
        id="htg-gas-3",
        name="Gas Heat 3-Stage",
        category="heating",
        description="Three stage gas-fired heat with loop-output staging",

        inputs=[
            InputPoint(44, "GAS-PRSR", "BI", "Normal/Alarm", "Gas Pressure Switch"),
        ],

        outputs=[
            OutputPoint(25, "GAS-VLV-1", "BO", "Stop/Start", "Gas Valve Stage 1"),
            OutputPoint(26, "GAS-VLV-2", "BO", "Stop/Start", "Gas Valve Stage 2"),
            OutputPoint(27, "GAS-VLV-3", "BO", "Stop/Start", "Gas Valve Stage 3"),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",     "AV", 65.0,  "Heating Lockout OAT SP",   "°F"),
            ValuePoint(56, "HTG-LOCKOUT",    "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",      "AV", 55.0,  "Cooling Lockout OAT SP",   "°F"),
            ValuePoint(59, "CLG-LOCKOUT",    "BV", False, "Cooling Lockout Active"),
            ValuePoint(61, "GAS-FAIL",       "BV", False, "Gas Heat Failure Alarm"),
            ValuePoint(202,"GAS-STG2-SP",    "AV", 50.0,  "Stage 2 Loop Enable %",    "%"),
            ValuePoint(203,"GAS-STG3-SP",    "AV", 75.0,  "Stage 3 Loop Enable %",    "%"),
        ],

        programs=[
            ProgramDef(39, "GAS-HTR-PRG", "PRG39-GAS-HTR-3STG.bas", "", True,
                       "Gas heat 3-stage loop-threshold control",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout",
                       exec_order=6),
        ],

        soo_paragraph="""Three-stage gas-fired heating shall be provided. Stages shall be
sequenced based on heating loop output: Stage 1 at 25%, Stage 2 at the
Stage 2 setpoint (default 50%), Stage 3 at the Stage 3 setpoint (default
75%). Each stage drops out with hysteresis to prevent short-cycling. A
shared gas pressure switch shall be monitored — loss of pressure shall
disable all stages and generate a single gas failure alarm. All stages
shall de-energize during cooling lockout, fan off, or any safety
shutdown.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-elec-2", "htg-elec-3", "htg-elec-scr",
                   "htg-gas", "htg-gas-2", "htg-gas-4", "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_gas_4():
    """Gas heat — 4 stages"""
    return Module(
        id="htg-gas-4",
        name="Gas Heat 4-Stage",
        category="heating",
        description="Four stage gas-fired heat with loop-output staging",

        inputs=[
            InputPoint(44, "GAS-PRSR", "BI", "Normal/Alarm", "Gas Pressure Switch"),
        ],

        outputs=[
            OutputPoint(25, "GAS-VLV-1", "BO", "Stop/Start", "Gas Valve Stage 1"),
            OutputPoint(26, "GAS-VLV-2", "BO", "Stop/Start", "Gas Valve Stage 2"),
            OutputPoint(27, "GAS-VLV-3", "BO", "Stop/Start", "Gas Valve Stage 3"),
            OutputPoint(28, "GAS-VLV-4", "BO", "Stop/Start", "Gas Valve Stage 4"),
        ],

        values=[
            ValuePoint(55, "HTG-LO-SP",     "AV", 65.0,  "Heating Lockout OAT SP",   "°F"),
            ValuePoint(56, "HTG-LOCKOUT",    "BV", True,  "Heating Lockout Active"),
            ValuePoint(58, "CLG-LO-SP",      "AV", 55.0,  "Cooling Lockout OAT SP",   "°F"),
            ValuePoint(59, "CLG-LOCKOUT",    "BV", False, "Cooling Lockout Active"),
            ValuePoint(61, "GAS-FAIL",       "BV", False, "Gas Heat Failure Alarm"),
            ValuePoint(202,"GAS-STG2-SP",    "AV", 50.0,  "Stage 2 Loop Enable %",    "%"),
            ValuePoint(203,"GAS-STG3-SP",    "AV", 75.0,  "Stage 3 Loop Enable %",    "%"),
            ValuePoint(204,"GAS-STG4-SP",    "AV", 87.0,  "Stage 4 Loop Enable %",    "%"),
        ],

        programs=[
            ProgramDef(39, "GAS-HTR-PRG", "PRG39-GAS-HTR-4STG.bas", "", True,
                       "Gas heat 4-stage loop-threshold control",
                       exec_order=39),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout",
                       exec_order=6),
        ],

        soo_paragraph="""Four-stage gas-fired heating shall be provided. Stages shall be
sequenced based on heating loop output: Stage 1 at 25%, Stage 2 at the
Stage 2 setpoint (default 50%), Stage 3 at the Stage 3 setpoint (default
75%), Stage 4 at the Stage 4 setpoint (default 87%). Each stage drops
out with hysteresis to prevent short-cycling. A shared gas pressure
switch shall be monitored — loss of pressure shall disable all stages
and generate a single gas failure alarm. All stages shall de-energize
during cooling lockout, fan off, or any safety shutdown.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-elec-2", "htg-elec-3", "htg-elec-scr",
                   "htg-gas", "htg-gas-2", "htg-gas-3", "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )


def build_htg_hw_fbp():
    """Hot water heating coil with face/bypass damper.

    Face/bypass damper modulates air around the coil:
      - Heating mode → 100% face (all air through coil for heat transfer)
      - Cooling mode → modulate F/B from HW coil LAT vs SAT setpoint
      - Economizer → minimum face (allow OA to bypass coil)
      - Freeze safety → 100% face (force warm air through coil)
      - Fan off / safety SD → 100% face (stagnation freeze protection)
    Includes the full HW coil hardware and program set as htg-hw, plus AO
    and program for the face/bypass damper.
    """
    return Module(
        id="htg-hw-fbp",
        name="Hot Water Heating with Face/Bypass",
        category="heating",
        description="HW heating coil + face/bypass damper, freeze protection, lockout",

        inputs=[
            InputPoint(8,  "HWC-DAT",    "AI", "10K -40 ->250", "HW Coil Discharge Air Temp", "°F"),
            InputPoint(31, "HWC-SUPW-T", "AI", "10K -40 ->250", "HW Coil Supply Water Temp",  "°F"),
            InputPoint(32, "HWC-RETW-T", "AI", "10K -40 ->250", "HW Coil Return Water Temp",  "°F"),
        ],

        outputs=[
            OutputPoint(4, "HW-VLV",      "AO", "0.0 ->100%", "Hot Water Valve (reverse)",            10.0, 2.0, True),
            OutputPoint(5, "HTG-FBP-DMP", "AO", "0.0 ->100%", "Face/Bypass Damper (0=bypass,100=face)", 10.0, 2.0, False),
        ],

        values=[
            # HW coil base set (mirrors htg-hw)
            ValuePoint(55,  "HTG-LO-SP",        "AV", 65.0,  "Heating Lockout OAT SP",     "°F"),
            ValuePoint(56,  "HTG-LOCKOUT",      "BV", True,  "Heating Lockout Active"),
            ValuePoint(57,  "HTG-LO-ICON",      "BV", False, "Heating Lockout Icon"),
            ValuePoint(58,  "CLG-LO-SP",        "AV", 55.0,  "Cooling Lockout OAT SP",     "°F"),
            ValuePoint(59,  "CLG-LOCKOUT",      "BV", False, "Cooling Lockout Active"),
            ValuePoint(60,  "CLG-LO-ICON",      "BV", True,  "Cooling Lockout Icon"),
            ValuePoint(52,  "FRZ-PRTC-SP",      "AV", 25.0,  "Freeze Protection OAT SP",   "°F"),
            ValuePoint(53,  "FRZ-PRTC-MODE",    "BV", False, "Freeze Protection Mode"),
            ValuePoint(78,  "HWC-SAT-SP",       "AV", 52.0,  "HW Coil SAT Setpoint",       "°F"),
            ValuePoint(150, "HTG-RAMP",         "AV", 0.5,   "Heating Valve Ramp Time",    "Min."),
            ValuePoint(151, "HW-AVAIL",         "BV", False, "Hot Water Available"),
            ValuePoint(171, "HTG-VLV-FREEZE-SP","AV", 110.0, "HW Valve Freeze SP",         "°F"),
            # Face/bypass specific
            ValuePoint(172, "HTG-FBP-MIN-FACE", "AV", 20.0,  "Face/Bypass Minimum Face Position",  "%"),
            ValuePoint(173, "HTG-FBP-FREEZE-SP","AV", 40.0,  "DAT Freeze Threshold for Full Face", "°F"),
            ValuePoint(174, "HTG-FBP-CMD",      "AV", 100.0, "Face/Bypass Damper Command",         "%"),
        ],

        loops=[
            LoopDef(7, "HW-VLV-LOOP", "HWC-DAT", "ACT-SAT-SP", "HW-VLV",
                    p_band=12.0, integral=40.0, action="reverse",
                    description="Hot Water Valve SAT Control"),
            LoopDef(9, "FRZ-LOOP", "HWC-DAT", "HTG-VLV-FREEZE-SP", "HW-VLV",
                    p_band=12.0, integral=40.0, action="reverse",
                    description="Freeze Protection Valve Override"),
        ],

        programs=[
            ProgramDef(39, "HW-VLV-PRG", "PRG39-HW-VLV.bas", "", True,
                       "Hot water valve modulation with freeze and lockout",
                       exec_order=39),
            ProgramDef(5, "FRZ-PRTN-MODE-PRG", "PRG05-FRZ-PRTN-MODE.bas", "", True,
                       "Freeze protection mode determination",
                       exec_order=5),
            ProgramDef(6, "HTG-CLG-LO-PRG", "PRG06-HTG-CLG-LO.bas", "", True,
                       "Heating/cooling lockout determination",
                       exec_order=6),
            ProgramDef(45, "HTG-FBP-PRG", "PRG45-HTG-FBP.bas", "", True,
                       "Heating coil face/bypass damper modulation",
                       exec_order=45),
        ],

        soo_paragraph="""The hot water heating coil shall be controlled by a modulating 2-way valve.
The valve shall modulate to maintain supply air temperature setpoint during
heating mode. The valve actuator shall be reverse-acting (fail-open) for
freeze protection.

In addition, a face/bypass damper shall be provided across the heating coil.
During heating mode the damper shall be commanded to full face position so all
supply air passes through the heated coil. During cooling mode the damper shall
modulate based on the heating coil leaving air temperature relative to the
supply air temperature setpoint, biasing toward bypass when the coil is not
adding heat. During economizer operation the damper shall hold at the
configured minimum face position to coordinate with the outdoor air damper.

Safety: when discharge air temperature falls below the configured freeze
threshold (default 40°F), or the supply fan is not running, or a safety
shutdown alarm is active, the face/bypass damper shall be driven to 100%
face position to force air through the heated coil and prevent stagnation
freezing.""",

        requires=["core"],
        conflicts=["htg-hw", "htg-elec", "htg-elec-2", "htg-elec-3", "htg-elec-scr",
                   "htg-gas", "htg-gas-2", "htg-gas-3", "htg-gas-4",
                   "htg-gas-mod", "htg-stm"],
        mutually_exclusive_group="heating",
    )
