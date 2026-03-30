"""
SBS CHW-PLANT Modules — Chilled Water Plant

Two equipment types share these modules:
  chw_plant_air   — Air cooled chiller plant (no towers/CW pumps)
  chw_plant_tower — Water cooled chiller plant with cooling towers

Controller Type: MPS (MACH-ProSys)
One controller per plant. Chillers are always third-party BACnet devices.

Module structure:
  chw-core           — Always on. System enable, OA reset, temps, schedule, flow.
  chw-chlr           — Chiller control: enable, staging, lead/lag (dynamic N)
  chw-pump-pri       — Primary CHW pumps, constant speed, lead/lag (dynamic N)
  chw-pump-sec       — Secondary CHW pumps, VFD + DP control (dynamic N)
  chw-cdwp           — Condenser water pumps (tower only, dynamic N)
  chw-tower          — Cooling tower fan + wet-bulb reset (tower only, dynamic N)
  chw-tower-bypass   — Tower CW bypass valve (tower only, optional)
  chw-bypass-valve   — CHW header bypass valve (optional)
  chw-iso-valves     — Chiller isolation valves (optional)
  chw-makeup-water   — Makeup water flow monitoring (optional)
  chw-ahu-integ      — AHU zone data integration (optional)

I/O Terminal Map (MPS):
  See chw_plant_io_map.txt for fixed terminal assignments.

Point Instance Ranges:
  AV/BV/MV 1-20     : Core
  AV/BV/MV 21-50    : Chiller module
  AV/BV/MV 51-70    : Primary pump module
  AV/BV/MV 71-90    : Secondary pump module
  AV/BV/MV 91-110   : Condenser water pump module
  AV/BV/MV 111-120  : Cooling tower module
  AV/BV/MV 121-130  : Bypass valve / iso valves
  AV/BV/MV 131-140  : Makeup water
  AV/BV/MV 141-220  : AHU integration (per AHU block of 10)

Program Instances (no conflicts — each slot unique):
  PRG 1-5    : Core (1=config, 2=setpoint, 5=status; 3-4 reserved)
  PRG 6-8    : Chiller (6=ctrl, 7=lead/lag; 8 reserved)
  PRG 9-15   : Reserved for per-chiller expansion
  PRG 16-21  : Primary pump (16=pump1, 17=lead/lag, 19=pump2; 18,20,21=pump3-4)
  PRG 22-29  : Secondary pump (22=schwp1, 23=schwp2, 24=schwp1-spd, 25=schwp2-spd,
               26=lead/lag, 27=lag-staging; 28-29 reserved)
  PRG 30-33  : CW pump (30=cdwp1, 31=cdwp2, 32=lead/lag; 33 reserved)
  PRG 34-39  : Cooling tower (34=ctrl, 35=lead/lag, 39=tower-bypass; 36-38 reserved)
  PRG 40     : Isolation valves
  PRG 42     : CHW bypass valve
  PRG 43     : Makeup water
  PRG 45-49  : AHU integration (45=net-data, 46+=per-AHU config)
  PRG 50-54  : Power metering (reserved)

Loop Instances:
  LOOP1    : CHW secondary DP
  LOOP2    : Condenser water supply temp (tower fan)
  LOOP3    : Tower CW bypass valve
  LOOP4    : CHW header bypass valve
"""

from composition.modules.chw_plant.core import build as build_core
from composition.modules.chw_plant.chiller import build_chiller
from composition.modules.chw_plant.pumps import build_pump_pri, build_pump_sec, build_cdwp
from composition.modules.chw_plant.tower import build_tower, build_tower_bypass
from composition.modules.chw_plant.optional import (
    build_bypass_valve, build_iso_valves, build_makeup_water, build_ahu_integration
)
