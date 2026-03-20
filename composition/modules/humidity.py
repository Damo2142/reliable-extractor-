"""
Humidity Modules — Steam Humidifier, Dehumidification (Subcool)

HUM-STM, HUM-ELEC, HUM-ULTRA, DEHUM-SC
"""

from composition.models import (
    Module, InputPoint, OutputPoint, ValuePoint, ProgramDef, SystemGroupDef
)


def build_hum_stm():
    """Steam humidifier — modulating output"""
    return Module(
        id="hum-stm",
        name="Steam Humidifier",
        category="humidity",
        description="Modulating steam humidifier with status feedback",

        inputs=[
            InputPoint(10, "RAH",     "AI", "0 ->100% (0-5V)", "Return Air Humidity",   "%"),
            InputPoint(37, "HUM-STS", "BI", "Off/On",          "Humidifier Status"),
        ],

        outputs=[
            OutputPoint(16, "HUM", "AO", "0.0 ->100%", "Humidifier Output", 2.0, 10.0),
        ],

        values=[
            ValuePoint(13,  "RMH",         "AV", 37.4,  "Room Humidity",            "%"),
            ValuePoint(240, "HUM-SP",      "AV", 40.0,  "Humidity Setpoint",        "%"),
            ValuePoint(241, "HUM-DB",      "AV", 5.0,   "Humidity Deadband",        "%"),
            ValuePoint(242, "HUM-FAIL",    "BV", False,  "Humidifier Failure Alarm"),
            ValuePoint(243, "HUM-ENABLE",  "BV", False,  "Humidifier Enabled"),
        ],

        programs=[
            ProgramDef(46, "HUM-PRG", "PRG46-HUM-STM.bas", "", True,
                       "Steam humidifier modulating control",
                       exec_order=46),
        ],

        soo_paragraph="""A steam humidifier shall be provided to maintain space humidity.
The humidifier output shall modulate to maintain the humidity setpoint
measured at the return air duct. The humidifier shall be enabled only
when the supply fan is running and the unit is in occupied mode.
Humidifier status feedback shall be monitored — failure to confirm
operation after command shall generate an alarm.""",

        requires=["core"],
        conflicts=["hum-elec", "hum-ultra"],
        mutually_exclusive_group="humidifier",
    )


def build_hum_elec():
    """Electric humidifier — modulating"""
    return Module(
        id="hum-elec",
        name="Electric Humidifier",
        category="humidity",
        description="Modulating electric humidifier",

        inputs=[
            InputPoint(10, "RAH",     "AI", "0 ->100% (0-5V)", "Return Air Humidity", "%"),
            InputPoint(37, "HUM-STS", "BI", "Off/On",          "Humidifier Status"),
        ],

        outputs=[
            OutputPoint(16, "HUM", "AO", "0.0 ->100%", "Humidifier Output", 2.0, 10.0),
        ],

        values=[
            ValuePoint(13,  "RMH",        "AV", 37.4,  "Room Humidity",           "%"),
            ValuePoint(240, "HUM-SP",     "AV", 40.0,  "Humidity Setpoint",       "%"),
            ValuePoint(241, "HUM-DB",     "AV", 5.0,   "Humidity Deadband",       "%"),
            ValuePoint(242, "HUM-FAIL",   "BV", False,  "Humidifier Failure"),
            ValuePoint(243, "HUM-ENABLE", "BV", False,  "Humidifier Enabled"),
        ],

        programs=[
            ProgramDef(46, "HUM-PRG", "PRG46-HUM-ELEC.bas", "", True,
                       "Electric humidifier control",
                       exec_order=46),
        ],

        soo_paragraph="""An electric humidifier shall maintain space humidity at setpoint.
The humidifier shall modulate based on return air humidity sensor.""",

        requires=["core"],
        conflicts=["hum-stm", "hum-ultra"],
        mutually_exclusive_group="humidifier",
    )


def build_hum_ultra():
    """Ultrasonic humidifier"""
    return Module(
        id="hum-ultra",
        name="Ultrasonic Humidifier",
        category="humidity",
        description="Ultrasonic humidifier — modulating output",

        inputs=[
            InputPoint(10, "RAH",     "AI", "0 ->100% (0-5V)", "Return Air Humidity", "%"),
            InputPoint(37, "HUM-STS", "BI", "Off/On",          "Humidifier Status"),
        ],

        outputs=[
            OutputPoint(16, "HUM", "AO", "0.0 ->100%", "Humidifier Output", 2.0, 10.0),
        ],

        values=[
            ValuePoint(13,  "RMH",        "AV", 37.4,  "Room Humidity",           "%"),
            ValuePoint(240, "HUM-SP",     "AV", 40.0,  "Humidity Setpoint",       "%"),
            ValuePoint(241, "HUM-DB",     "AV", 5.0,   "Humidity Deadband",       "%"),
            ValuePoint(242, "HUM-FAIL",   "BV", False,  "Humidifier Failure"),
            ValuePoint(243, "HUM-ENABLE", "BV", False,  "Humidifier Enabled"),
        ],

        programs=[
            ProgramDef(46, "HUM-PRG", "PRG46-HUM-ULTRA.bas", "", True,
                       "Ultrasonic humidifier control",
                       exec_order=46),
        ],

        soo_paragraph="""An ultrasonic humidifier shall maintain space humidity at setpoint.""",

        requires=["core"],
        conflicts=["hum-stm", "hum-elec"],
        mutually_exclusive_group="humidifier",
    )


def build_dehum_sc():
    """Dehumidification — subcooling (overcool to dehumidify, then reheat)"""
    return Module(
        id="dehum-sc",
        name="Dehumidification Subcool",
        category="humidity",
        description="Dehumidification by subcooling — overcool SA then reheat",

        inputs=[
            InputPoint(10, "RAH",   "AI", "0 ->100% (0-5V)", "Return Air Humidity", "%"),
            InputPoint(18, "ZN-RH", "AI", "0 ->100% (0-5V)", "Zone Humidity",       "%"),
        ],

        values=[
            ValuePoint(13,  "RMH",           "AV", 37.4,  "Room Humidity",            "%"),
            ValuePoint(250, "DEHUM-SP",      "AV", 55.0,  "Dehumidification RH SP",   "%"),
            ValuePoint(251, "DEHUM-DB",      "AV", 5.0,   "Dehumidification Deadband","%"),
            ValuePoint(252, "DEHUM-MODE",    "BV", False,  "Dehumidification Active"),
            ValuePoint(253, "DEHUM-SAT-SP",  "AV", 48.0,  "Dehumid SAT Setpoint",     "°F"),
        ],

        programs=[
            ProgramDef(47, "DEHUM-PRG", "PRG47-DEHUM-SC.bas", "", True,
                       "Dehumidification subcooling control",
                       exec_order=47),
        ],

        soo_paragraph="""Dehumidification shall be achieved by subcooling the supply air
below the dew point and then reheating to the supply air temperature
setpoint. When return air humidity exceeds the dehumidification setpoint,
the supply air temperature setpoint shall be reduced to force additional
cooling coil dehumidification. The heating coil shall reheat the air to
prevent overcooling the space. Zone humidity shall be monitored to confirm
dehumidification is effective.""",

        requires=["core"],
    )
