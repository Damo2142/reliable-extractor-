"""
Preheat Modules — HW, Electric, Steam, Glycol

Preheat coil sits upstream of the mixing section.
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, ProgramDef
)


def build_ph_hw():
    """Preheat — hot water coil with modulating valve + pump"""
    return Module(
        id="ph-hw",
        name="Preheat Hot Water",
        category="preheat",
        description="HW preheat coil with modulating valve, pump, and entering/leaving temps",

        inputs=[
            InputPoint(8,  "PH-LAT",    "AI", "10K -40 ->250", "Preheat Leaving Air Temp",       "°F"),
            InputPoint(35, "PH-EAT",    "AI", "10K -40 ->250", "Preheat Entering Air Temp",      "°F"),
            InputPoint(39, "PH-SUPW-T", "AI", "10K -40 ->250", "Preheat Coil Supply Water Temp", "°F"),
            InputPoint(40, "PH-RETW-T", "AI", "10K -40 ->250", "Preheat Coil Return Water Temp", "°F"),
        ],

        outputs=[
            OutputPoint(8,  "PH-VLV", "AO", "0.0 ->100%", "Preheat Valve (reverse)", 10.0, 2.0, True),
            OutputPoint(17, "PH-PMP", "BO", "Stop/Start", "Preheat Pump Command"),
        ],

        values=[
            ValuePoint(230, "PH-SAT-SP",      "AV", 55.0,  "Preheat LAT Setpoint",           "°F"),
            ValuePoint(231, "PH-PMP-FAIL",     "BV", False, "Preheat Pump Failure Alarm"),
            ValuePoint(232, "PH-PMP-DELAY",    "AV", 30.0,  "Preheat Pump Fail Delay",        "Sec"),
        ],

        loops=[
            LoopDef(13, "PH-VLV-LOOP", "PH-LAT", "PH-SAT-SP", "PH-VLV",
                    p_band=12.0, integral=40.0, action="reverse",
                    description="Preheat Valve LAT Control"),
        ],

        programs=[
            ProgramDef(40, "PH-PRG", "PRG40-PH-HW.bas", "", True,
                       "Preheat HW valve + pump control",
                       exec_order=40),
        ],

        soo_paragraph="""A hot water preheat coil shall be provided upstream of the mixing section.
The preheat valve shall modulate to maintain preheat leaving air temperature
setpoint. The valve actuator shall be reverse-acting (fail-open) for freeze
protection. A dedicated preheat pump shall run when the preheat valve output
is greater than 0% or when outdoor air temperature is below the freeze
protection setpoint. Pump failure shall be alarmed if commanded on with no
status after 30 seconds.""",

        requires=["core"],
        conflicts=["ph-elec", "ph-stm", "ph-glycol"],
        mutually_exclusive_group="preheat",
    )


def build_ph_elec():
    """Preheat — electric"""
    return Module(
        id="ph-elec",
        name="Preheat Electric",
        category="preheat",
        description="Electric preheat coil",

        inputs=[
            InputPoint(8, "PH-LAT", "AI", "10K -40 ->250", "Preheat Leaving Air Temp", "°F"),
        ],

        outputs=[
            OutputPoint(8, "PH-HTR", "BO", "Stop/Start", "Preheat Electric Heater"),
        ],

        values=[
            ValuePoint(230, "PH-SAT-SP", "AV", 55.0, "Preheat LAT Setpoint", "°F"),
        ],

        programs=[
            ProgramDef(40, "PH-PRG", "PRG40-PH-ELEC.bas", "", True,
                       "Preheat electric heater control",
                       exec_order=40),
        ],

        soo_paragraph="""An electric preheat coil shall be provided upstream of the mixing section.
The heater shall energize to maintain preheat leaving air temperature setpoint
when the supply fan is running and outdoor air temperature is below the
preheat enable setpoint.""",

        requires=["core"],
        conflicts=["ph-hw", "ph-stm", "ph-glycol"],
        mutually_exclusive_group="preheat",
    )


def build_ph_glycol():
    """Preheat — glycol coil with pump"""
    return Module(
        id="ph-glycol",
        name="Preheat Glycol",
        category="preheat",
        description="Glycol preheat coil with pump and valve",

        inputs=[
            InputPoint(8,  "PH-LAT",    "AI", "10K -40 ->250", "Preheat Leaving Air Temp",       "°F"),
            InputPoint(35, "PH-EAT",    "AI", "10K -40 ->250", "Preheat Entering Air Temp",      "°F"),
        ],

        outputs=[
            OutputPoint(8,  "PH-VLV", "AO", "0.0 ->100%",   "Preheat Glycol Valve (reverse)", 10.0, 2.0, True),
            OutputPoint(17, "PH-PMP", "BO", "Stop/Start", "Preheat Glycol Pump Command"),
        ],

        values=[
            ValuePoint(230, "PH-SAT-SP",   "AV", 55.0,  "Preheat LAT Setpoint",       "°F"),
            ValuePoint(231, "PH-PMP-FAIL", "BV", False,  "Preheat Pump Failure Alarm"),
        ],

        loops=[
            LoopDef(13, "PH-VLV-LOOP", "PH-LAT", "PH-SAT-SP", "PH-VLV",
                    p_band=12.0, integral=40.0, action="reverse",
                    description="Preheat Glycol Valve Control"),
        ],

        programs=[
            ProgramDef(40, "PH-PRG", "PRG40-PH-GLYCOL.bas", "", True,
                       "Preheat glycol valve + pump control",
                       exec_order=40),
        ],

        soo_paragraph="""A glycol preheat coil shall be provided upstream of the mixing section.
The preheat valve shall modulate to maintain leaving air temperature setpoint.
A dedicated glycol pump shall circulate whenever the valve is open or outdoor
temperature is below freeze protection setpoint.""",

        requires=["core"],
        conflicts=["ph-hw", "ph-elec", "ph-stm"],
        mutually_exclusive_group="preheat",
    )
