"""
HW-PLANT Optional Modules

  hw-mixing-valve   — 3-way mixing valve with PID
  hw-iso-valves     — Boiler isolation valves
  hw-comb-damper    — Combustion air damper monitoring
  hw-hx             — Heat exchanger with valve control
  hw-ahu-integ      — AHU zone data integration
  hw-makeup-water   — Makeup water flow monitoring
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, LoopDef, TableDef,
    ProgramDef, SystemGroupDef
)


def build_mixing_valve():
    """3-way mixing valve for header temperature control."""
    return Module(
        id="hw-mixing-valve",
        name="Mixing Valve",
        category="hw-optional",
        description="3-way mixing valve for HW header temperature control",
        outputs=[
            OutputPoint(17, "HW-MIXING-VLV", "AO", "0.0 ->100%",
                "HW Mixing Valve", 2.0, 10.0),  # OUT17 — after pump outputs
        ],
        values=[
            ValuePoint(141, "HWV-PID-SP", "AV", 160.0, "Mixing Valve Setpoint", "°F"),
        ],
        loops=[
            LoopDef(2, "HWV-PID", "HWS-T", "HWV-PID-SP", "HW-MIXING-VLV",
                    p_band=10.0, integral=40.0, action="reverse",
                    description="HW Mixing Valve PID Control"),
        ],
        programs=[
            ProgramDef(30, "HW-MIXING-VLV-PRG", "HW-PRG26-MIXING-VLV.bas", "", True,
                       "Mixing valve modulation", "hw-mixing-valve", exec_order=30),
        ],
        soo_paragraph="""A 3-way mixing valve shall modulate to maintain the hot water
header temperature setpoint. The valve PID loop shall control the blend of
boiler supply water and return water to achieve the desired distribution temperature.""",
        requires=["hw-core"],
    )


def build_iso_valves(num_boilers=2):
    """Boiler isolation valves — one per boiler."""
    inputs = []
    outputs = []
    for n in range(1, num_boilers + 1):
        outputs.append(OutputPoint(
            17 + n, f"BLR{n}-ISO-VLV", "BO", "Close/Open",
            f"Boiler {n} Isolation Valve"))  # OUT18-21 (4 slots)
        inputs.append(InputPoint(
            27 + n, f"BLR{n}-ISO-VLV-ES", "BI", "Close/Open",
            f"Boiler {n} Isolation Valve End Switch"))  # IN28-31 (4 slots)

    return Module(
        id="hw-iso-valves",
        name=f"Isolation Valves ({num_boilers})",
        category="hw-optional",
        description=f"Boiler isolation valves for {num_boilers} boiler(s)",
        inputs=inputs, outputs=outputs,
        values=[
            ValuePoint(142, "ISO-VLV-OPEN-DLY", "AV", 30.0,
                "Isolation Valve Open Delay", "Sec"),
        ],
        tables=[
            TableDef(1, "BLR-ISO-VLV-POS", "Position", "Command",
                [[0, 0], [50, 0], [51, 1], [100, 1]],
                "Boiler isolation valve position lookup"),
        ],
        programs=[
            ProgramDef(27, "HW-ISO-VLV-PRG", "HW-PRG27-ISO-VLV.bas", "", True,
                       "Isolation valve sequencing", "hw-iso-valves", exec_order=27),
        ],
        soo_paragraph=f"""Motorized isolation valves shall be provided for each boiler.
Isolation valves shall open before the boiler is enabled and close after
the boiler is disabled. End switch feedback shall confirm valve position.
Boiler enable shall be delayed until the isolation valve is confirmed open.""",
        requires=["hw-core"],
    )


def build_comb_damper(num_boilers=2):
    """Combustion air damper status monitoring — one per boiler."""
    inputs = []
    for n in range(1, num_boilers + 1):
        inputs.append(InputPoint(
            31 + n, f"BLR{n}-COMB-DMPR-STS", "BI", "Close/Open",
            f"Boiler {n} Combustion Damper Status"))  # IN32-35 (4 slots)

    return Module(
        id="hw-comb-damper",
        name=f"Combustion Dampers ({num_boilers})",
        category="hw-optional",
        description=f"Combustion air damper monitoring for {num_boilers} boiler(s)",
        inputs=inputs,
        values=[
            ValuePoint(143, "COMB-DMPR-ALARM", "BV", False, "Combustion Damper Alarm"),
        ],
        programs=[
            ProgramDef(28, "HW-COMB-DMPR-PRG", "HW-PRG28-COMB-DMPR.bas", "", True,
                       "Combustion damper monitoring", "hw-comb-damper", exec_order=28),
        ],
        soo_paragraph="""Combustion air damper position shall be monitored for each boiler.
Boiler operation shall be interlocked with combustion damper — the boiler shall not
fire unless the combustion air damper is confirmed open.""",
        requires=["hw-core"],
    )


def build_heat_exchanger(valve_type="single_mod"):
    """Heat exchanger with valve control.

    Args:
        valve_type: "single_mod" = single modulating AO
                    "single_onoff" = single on/off BO (no loop)
                    "third_twothird" = 1/3 + 2/3 floating sequence
    """
    inputs = [
        InputPoint(36, "HX-SUPW-T", "AI", "10K -40 ->250",
            "Heat Exchanger Supply Water Temp", "°F"),  # IN36, after comb damper
        InputPoint(37, "HX-RETW-T", "AI", "10K -40 ->250",
            "Heat Exchanger Return Water Temp", "°F"),  # IN37
    ]
    outputs = []
    values = [
        ValuePoint(151, "HX-SP", "AV", 140.0, "Heat Exchanger Setpoint", "°F"),
        ValuePoint(152, "HX-DELTA-T", "AV", 0.0, "HX Delta T", "°F"),
    ]
    loops = []
    programs = []

    if valve_type == "single_mod":
        outputs.append(OutputPoint(22, "HX-VLV", "AO", "0.0 ->100%",
            "Heat Exchanger Valve (modulating)", 2.0, 10.0))
        loops.append(LoopDef(3, "HX-VLV-LOOP", "HX-SUPW-T", "HX-SP", "HX-VLV",
            p_band=10.0, integral=40.0, action="reverse",
            description="Heat Exchanger Valve Control"))
        programs.append(ProgramDef(29, "HW-HX-VLV-PRG", "HW-PRG29-HX-VLV.bas", "", True,
            "Heat exchanger valve control", "hw-hx", exec_order=29))

    elif valve_type == "single_onoff":
        outputs.append(OutputPoint(22, "HX-VLV", "BO", "Close/Open",
            "Heat Exchanger Valve (on/off)"))
        programs.append(ProgramDef(29, "HW-HX-VLV-PRG", "HW-PRG29-HX-VLV-ONOFF.bas", "", True,
            "Heat exchanger on/off valve control", "hw-hx", exec_order=29))

    elif valve_type == "third_twothird":
        outputs.append(OutputPoint(22, "HX-VLV-1/3", "AO", "0.0 ->100%",
            "Heat Exchanger 1/3 Valve", 2.0, 10.0))
        outputs.append(OutputPoint(23, "HX-VLV-2/3", "AO", "0.0 ->100%",
            "Heat Exchanger 2/3 Valve", 2.0, 10.0))
        loops.append(LoopDef(3, "HX-VLV-LOOP", "HX-SUPW-T", "HX-SP", "HX-VLV-1/3",
            p_band=10.0, integral=40.0, action="reverse",
            description="Heat Exchanger 1/3+2/3 Valve Sequence"))
        values.extend([
            ValuePoint(153, "HX-VLV-1/3-POS", "AV", 0.0, "1/3 Valve Position", "%"),
            ValuePoint(154, "HX-VLV-2/3-POS", "AV", 0.0, "2/3 Valve Position", "%"),
        ])
        programs.append(ProgramDef(29, "HW-HX-VLV-SEQ-PRG", "HW-PRG29-HX-VLV-SEQ.bas", "", True,
            "Heat exchanger 1/3+2/3 floating valve sequence", "hw-hx", exec_order=29))

    valve_desc = {
        "single_mod": "A single modulating valve shall control flow through the heat exchanger.",
        "single_onoff": "An on/off valve shall control flow through the heat exchanger.",
        "third_twothird": """A 1/3 + 2/3 floating valve sequence shall control flow.
The 1/3 valve opens 0-100% first. Once fully open, the 2/3 valve opens and the 1/3 valve
closes. If the 2/3 valve reaches 100% and demand persists, the 1/3 valve reopens.""",
    }

    return Module(
        id="hw-hx",
        name=f"Heat Exchanger ({valve_type})",
        category="hw-optional",
        description=f"Heat exchanger with {valve_type} valve control",
        inputs=inputs, outputs=outputs, values=values,
        loops=loops, programs=programs,
        system_groups=[
            SystemGroupDef("{device-name}-HEAT-EXCHANGER", "HX temps, valve position, setpoint"),
        ],
        soo_paragraph=f"""A plate heat exchanger shall transfer heat from the boiler loop
to the distribution loop. Supply and return water temperatures shall be monitored.
{valve_desc[valve_type]}""",
        requires=["hw-core"],
    )


def build_ahu_integration(num_ahus=2):
    """AHU zone data integration — reads from N child AHU controllers.

    Args:
        num_ahus: 1-8 AHUs to integrate
    """
    values = []
    for n in range(1, num_ahus + 1):
        base = 171 + (n-1) * 10
        values.extend([
            ValuePoint(base,   f"AHU{n}-NET-OCC-CMD",  "BV", False,  f"AHU {n} Occupancy Command"),
            ValuePoint(base+1, f"AHU{n}-NET-OK",       "BV", False,  f"AHU {n} Network OK"),
            ValuePoint(base+2, f"AHU{n}-HEAT-MODE",    "BV", False,  f"AHU {n} Heating Mode"),
            ValuePoint(base+3, f"AHU{n}-HIGH-RMT",     "AV", 72.0,   f"AHU {n} Highest Room Temp", "°F"),
            ValuePoint(base+4, f"AHU{n}-AVG-RMT",      "AV", 70.0,   f"AHU {n} Average Room Temp", "°F"),
            ValuePoint(base+5, f"AHU{n}-LOW-RMT",      "AV", 68.0,   f"AHU {n} Lowest Room Temp",  "°F"),
            ValuePoint(base+6, f"AHU{n}-HTG-REQS",     "AV", 0.0,    f"AHU {n} Heating Requests",  "#"),
            ValuePoint(base+7, f"AHU{n}-CLG-DMD",      "AV", 0.0,    f"AHU {n} Cooling Demand",    "%"),
            ValuePoint(base+8, f"AHU{n}-HWV-POS",      "AV", 0.0,    f"AHU {n} HW Valve Position", "%"),
        ])

    # Aggregated values
    values.extend([
        ValuePoint(161, "SNOW-DAY",         "BV", False, "Snow Day Override"),
        ValuePoint(162, "TOTAL-HTG-REQS",   "AV", 0.0,   "Total Heating Requests", "#"),
    ])

    programs = [
        ProgramDef(31, "HW-NET-DATA-PRG", "HW-PRG31-NET-DATA.bas", "", True,
                   "Network data reads from AHU controllers", "hw-ahu-integ", exec_order=31),
    ]
    for n in range(1, num_ahus + 1):
        d = "{device-name}"
        p = "{parent}"  # parent AHU BACnet device — set at commissioning
        ahu_cfg = f"REM **** AHU {n} Configuration and Data Exchange\n"
        ahu_cfg += "REM **** Generated by SBS Composition Engine v2 — HW Plant\n"
        ahu_cfg += f"REM **** Reads zone data from AHU {n}, writes HW availability\n\n"
        ahu_cfg += f"REM **** Network health check ****\n"
        ahu_cfg += f"IF {d}-AHU{n}-NET-OK THEN A = 1 ELSE A = 0\n\n"
        ahu_cfg += f"REM **** Read zone data from AHU {n} ****\n"
        ahu_cfg += f"{d}-AHU{n}-HIGH-RMT = {p}-HIGH-RMT\n"
        ahu_cfg += f"{d}-AHU{n}-AVG-RMT = {p}-AVG-RMT\n"
        ahu_cfg += f"{d}-AHU{n}-LOW-RMT = {p}-LOW-RMT\n"
        ahu_cfg += f"{d}-AHU{n}-HTG-REQS = {p}-HTG-REQS\n"
        ahu_cfg += f"{d}-AHU{n}-CLG-DMD = {p}-CLG-DMD\n"
        ahu_cfg += f"{d}-AHU{n}-HWV-POS = {p}-HWV-POS\n\n"
        ahu_cfg += f"REM **** Write HW availability to AHU ****\n"
        ahu_cfg += f"IF {d}-HW-AVAIL THEN START {d}-AHU{n}-NET-OCC-CMD\n"
        ahu_cfg += f"IF NOT {d}-HW-AVAIL THEN STOP {d}-AHU{n}-NET-OCC-CMD\n"
        programs.append(ProgramDef(
            31 + n, f"HW-AHU{n}-CFG-PRG", f"HW-PRG{31+n}-AHU{n}-CFG.bas", ahu_cfg, True,
            f"AHU {n} configuration and data exchange", "hw-ahu-integ", exec_order=31+n))

    return Module(
        id="hw-ahu-integ",
        name=f"AHU Integration ({num_ahus})",
        category="hw-optional",
        description=f"Network integration with {num_ahus} AHU(s)",
        values=values, programs=programs,
        system_groups=[
            SystemGroupDef("{device-name}-AHU-DATA", "AHU zone data, heating requests, valve positions"),
        ],
        soo_paragraph=f"""The hot water plant controller shall communicate via BACnet with
{num_ahus} air handling unit controller(s). Zone temperature data, heating requests,
and hot water valve positions shall be read from each AHU. Aggregated heating demand
shall inform boiler staging decisions. Hot water availability status shall be written
to each AHU controller.""",
        requires=["hw-core"],
    )


def build_makeup_water():
    """Makeup water flow monitoring and totalization."""
    return Module(
        id="hw-makeup-water",
        name="Makeup Water Monitoring",
        category="hw-optional",
        description="Makeup water flow monitoring and totalization",
        inputs=[
            InputPoint(38, "MAKEUP-WTR-FLOW", "AI", "0 ->100% (0-5V)",
                "Makeup Water Flow Rate", "GPM"),  # IN38, after HX temps
        ],
        values=[
            ValuePoint(251, "MAKEUP-WTR-TTL",    "AV", 0.0,  "Makeup Water Total",          "Gal"),
            ValuePoint(252, "MAKEUP-WTR-ALARM",  "BV", False, "Excessive Makeup Water Alarm"),
            ValuePoint(253, "MAKEUP-WTR-HI-SP",  "AV", 50.0,  "Makeup Water High Flow SP",   "GPM"),
            ValuePoint(254, "MAKEUP-WTR-RESET",  "BV", False, "Reset Makeup Water Total"),
        ],
        tables=[
            TableDef(2, "MAKEUP-WTR-TBL", "Volts", "GPM",
                [[0.0, 0.0], [5.0, 50.0], [10.0, 100.0]],
                "Makeup water flow sensor scaling"),
        ],
        programs=[
            ProgramDef(41, "HW-MAKEUP-WTR-PRG", "HW-PRG41-MAKEUP-WTR.bas", "", True,
                       "Makeup water monitoring and totalization", "hw-makeup-water", exec_order=41),
        ],
        soo_paragraph="""Makeup water flow to the hot water system shall be monitored.
A flow totalizer shall track cumulative water usage. An alarm shall be generated
if the flow rate exceeds the configurable high limit, indicating a possible leak.""",
        requires=["hw-core"],
    )
