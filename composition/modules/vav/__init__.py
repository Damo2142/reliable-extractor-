"""
SBS VAV Terminal Unit Modules

Controller Type: RC-FLEXair (RCFA)
One controller per VAV box. Factory actuator + VP sensor built in.

Module structure:
  vav-core          — Always on. Modes, setpoints, flow control, network vars, arrays, faults.
  vav-rh-hw-mod     — Modulating HW reheat (AO valve)
  vav-rh-hw-flt     — Floating HW reheat (BO open/close + FLOAT)
  vav-rh-elec-1     — 1-stage electric reheat (BO)
  vav-rh-elec-2     — 2-stage electric reheat (BO x2)
  vav-rh-elec-scr   — SCR modulating electric reheat (AO)
  vav-fan-parallel   — Parallel fan (BO + BI status)
  vav-fan-series     — Series fan (BO + BI status)
  vav-dd-hot-deck    — Dual duct hot deck damper

Factory reserved points (from blank file only — NEVER in module):
  AI4=VP, AI5=DMP-POS, BI6=DMP@END, BO8=CW-CLS, BV6=FLO-CTRL, MO7=DMP
  AV1=DIAM, AV2=FLO-CAL, AV3=CAL-K, AV4=FLO, AV5=FLO-SP, AV7=FLO-DB

Point Instance Ranges:
  AV 8-76     : Core values
  AV 81-110   : Reheat / fan / diagnostics
  BV 20-109   : Core binary values
  MV 16-72    : Core multi-state values
"""

from composition.modules.vav.core import build as build_core
from composition.modules.vav.rh_hw_mod import build as build_rh_hw_mod
from composition.modules.vav.rh_hw_flt import build as build_rh_hw_flt
from composition.modules.vav.rh_elec_1 import build as build_rh_elec_1
from composition.modules.vav.rh_elec_2 import build as build_rh_elec_2
from composition.modules.vav.rh_elec_scr import build as build_rh_elec_scr
from composition.modules.vav.fan_parallel import build as build_fan_parallel
from composition.modules.vav.fan_series import build as build_fan_series
from composition.modules.vav.dd_hot_deck import build as build_dd_hot_deck
from composition.modules.vav.stat_hardwired import build as build_stat_hardwired
from composition.modules.vav.stat_hardwired_ud import build as build_stat_hardwired_ud
from composition.modules.vav.stat_comm import build as build_stat_comm
from composition.modules.vav.stat_comm_co2 import build as build_stat_comm_co2
from composition.modules.vav.stat_comm_hum import build as build_stat_comm_hum
from composition.modules.vav.stat_comm_occ import build as build_stat_comm_occ

__all__ = ['build_core', 'build_rh_hw_mod', 'build_rh_hw_flt',
           'build_rh_elec_1', 'build_rh_elec_2', 'build_rh_elec_scr',
           'build_fan_parallel', 'build_fan_series', 'build_dd_hot_deck',
           'build_stat_hardwired', 'build_stat_hardwired_ud',
           'build_stat_comm', 'build_stat_comm_co2',
           'build_stat_comm_hum', 'build_stat_comm_occ']
