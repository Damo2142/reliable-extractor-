"""
VAV Communicating Stat Humidity Add-on — vav-stat-comm-hum

Adds room humidity monitoring point from SS3.
AV103=RM-HUM. Display/trending only — no control action.
Requires: vav-stat-comm
"""

from composition.models import Module, ValuePoint


def build():
    return Module(
        id="vav-stat-comm-hum",
        name="Humidity Sensor",
        category="thermostat-addon",
        description="Room humidity monitoring from SMART-Sensor SS3",
        is_core=False,

        inputs=[],
        outputs=[],

        values=[
            ValuePoint(103, "RM-HUM", "AV", 50.0, "Room Humidity (from SS3)", "%RH"),
        ],

        loops=[],
        programs=[],
        system_groups=[],

        soo_paragraph="""The SMART-Sensor SS3 shall include an integral humidity sensor.
Room relative humidity shall be monitored and available for trending
and display. No humidity control action is taken by the VAV controller.""",

        requires=["vav-stat-comm"],
    )
