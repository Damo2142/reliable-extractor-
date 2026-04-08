"""
VAV Communicating Stat Module — vav-stat-comm (SMART-Sensor SS3)

No AI — room temp comes via BACnet to AV9 (ACT-RMT).
SS3 writes directly to controller via SHARE-NET.
This module confirms communicating stat is selected — no additional IO.
"""

from composition.models import Module


def build():
    return Module(
        id="vav-stat-comm",
        name="Communicating Stat (SMART-Sensor SS3)",
        category="thermostat",
        description="SMART-Sensor SS3 communicating thermostat — room temp via BACnet, no AI needed",
        is_core=False,

        inputs=[],
        outputs=[],
        values=[],
        loops=[],
        programs=[],
        system_groups=[],

        soo_paragraph="""Room temperature shall be sensed by a SMART-Sensor SS3 communicating
thermostat. The sensor shall communicate room temperature, setpoint,
and optional CO2/humidity/occupancy data to the controller via BACnet
MS/TP network. No hard-wired analog input is required for room
temperature.""",

        mutually_exclusive_group="thermostat",
    )
