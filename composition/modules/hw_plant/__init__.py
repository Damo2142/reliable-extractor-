"""
SBS HW-PLANT Modules — Hot Water Heating Plant

Controller Type: MPS (MACH-ProSys)
One controller per plant. Boilers are always third-party equipment.

Module structure:
  hw-core         — Always on. System enable, OA reset, temps, schedule.
  hw-blr-cascade  — Cascade boiler control (enable + setpoint)
  hw-blr-full     — Full boiler control (direct fire rate modulation)
  hw-pump-cs      — Constant speed pumps with lead/lag
  hw-pump-vfd     — VFD pumps with DP control
  hw-pump-pri-sec — Primary/secondary pumping
  hw-mixing-valve — 3-way mixing valve (optional)
  hw-iso-valves   — Boiler isolation valves (optional)
  hw-comb-damper  — Combustion air damper monitoring (optional)
  hw-hx           — Heat exchanger with valve control (optional)
  hw-ahu-integ    — AHU zone data integration (optional)
  hw-makeup-water — Makeup water flow monitoring (optional)

I/O Terminal Map (MPS):
  See hw_plant_io_map.txt for fixed terminal assignments.

Point Instance Ranges:
  AV/BV/MV 1-20     : Core
  AV/BV/MV 21-50    : Boiler module
  AV/BV/MV 51-80    : Pump module
  AV/BV/MV 81-100   : Mixing valve / iso valves / comb damper
  AV/BV/MV 101-120  : Heat exchanger
  AV/BV/MV 121-200  : AHU integration (per AHU block of 10)
  AV/BV/MV 201-210  : Makeup water

Program Instances:
  PRG1-5   : Core
  PRG6-15  : Boiler
  PRG16-25 : Pump
  PRG26-30 : Optional (mixing, iso, comb, hx)
  PRG31-40 : AHU integration
  PRG41    : Makeup water
  PRG50    : Alarms (auto-generated)

Loop Instances:
  LOOP1    : HW DP (VFD pumps)
  LOOP2    : Mixing valve PID
  LOOP3    : Heat exchanger valve
"""

from composition.modules.hw_plant.core import build as build_core
from composition.modules.hw_plant.boiler import build_blr_cascade, build_blr_full
from composition.modules.hw_plant.pumps import build_pump_cs, build_pump_vfd, build_pump_pri_sec
from composition.modules.hw_plant.optional import (
    build_mixing_valve, build_iso_valves, build_comb_damper,
    build_heat_exchanger, build_ahu_integration, build_makeup_water
)
