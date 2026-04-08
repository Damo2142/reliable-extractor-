"""
VAV Dual Duct Hot Deck Module — vav-dd-hot-deck

Adds hot deck damper control for dual duct VAV boxes.
The cold deck damper is the factory damper (MO7/AI4/AI5).
The hot deck damper needs a second set of IO.

For DD-CLG (cooling only): no reheat module, just two dampers.
For DD-HW-MOD: adds modulating HW reheat on hot deck.
For DD-HW-FLT: adds floating HW reheat on hot deck.

This module provides the hot deck damper IO and control program.
Uses factory-style flow control on hot deck via AO.

Used by: VAV-DD-CLG, VAV-DD-HW-MOD, VAV-DD-HW-FLT
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint,
    ProgramDef, SystemGroupDef
)


_PRG06_DD = """\
REM --- DD-PRG ---
REM Dual duct hot deck damper control
REM Cold deck = factory damper (MO7, firmware flow control)
REM Hot deck = AO output, modulated by program
REM
REM --- Hot Deck Position ---
REM In cooling/vent mode: hot deck closed, cold deck open (firmware)
REM In reheat/heat mode: hot deck opens proportional to heating demand
REM Cold deck closes as hot deck opens (firmware handles cold deck)
REM
IF HVAC-MODE = 1 THEN HD-DMP = 0.0
IF HVAC-MODE = 2 THEN HD-DMP = 0.0
IF HVAC-MODE = 3 THEN HD-DMP = SLIDE( RMT-SP-HTG - ACT-RMT, 0.0, 4.0, 0.0, 100.0 )
IF HVAC-MODE = 4 THEN HD-DMP = 100.0
IF OCC-MODE = 4 THEN HD-DMP = 0.0
REM
REM --- Track Position ---
HD-DMP-POS = HD-DMP
"""


def build():
    return Module(
        id="vav-dd-hot-deck",
        name="Dual Duct Hot Deck",
        category="dual-duct",
        description="Hot deck damper control for dual duct VAV — AO output for hot deck position",
        is_core=False,

        inputs=[],

        outputs=[
            # Row 3 — rows 1-2 reserved for reheat outputs when combined with reheat module
            OutputPoint(3, "HD-DMP", "AO", "0.0 ->100%",
                        "Hot Deck Damper", 2.0, 10.0, False, "%"),
        ],

        values=[
            ValuePoint(84, "HD-DMP-POS", "AV", 0.0, "Hot Deck Damper Position", "%"),
        ],

        loops=[],

        programs=[
            ProgramDef(6, "DD-PRG", "PRG06-DD.bas", _PRG06_DD, True,
                       "Dual duct hot deck damper control",
                       exec_order=6),
        ],

        system_groups=[
            SystemGroupDef("{device-name}-DUAL-DUCT",
                           "Dual duct control: hot deck position, cold deck via firmware"),
        ],

        soo_paragraph="""The dual duct VAV terminal unit shall control two independent air
streams. The cold deck damper shall be controlled by the factory
integral actuator via firmware flow control. The hot deck damper
shall be controlled by a 0-10V analog output. In cooling and
ventilation modes, the hot deck damper shall be closed. In reheat
and heating modes, the hot deck damper shall modulate open
proportional to heating demand while the cold deck reduces.""",

        mutually_exclusive_group="dual-duct",
    )
