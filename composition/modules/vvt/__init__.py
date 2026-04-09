"""
SBS VVT System Modules

Three controller types work together via BACnet arrays:
  VVT-MPV   — MACH-ProView LCD: master RTU, fan/heat/cool staging, zone aggregation
  VVT-ZONE  — RC-FLEXair: zone damper, room temp control, HVAC voting, array writes
  VVT-BYPASS — RC-FLEXair: bypass damper, duct static pressure relief, DAT lockouts

Module structure:
  vvt-zone-core     — Zone core: modes, voting, damper, network reads, array writes
  vvt-bypass-core   — Bypass core: pressure control, DAT lockouts, MO7
  vvt-mpv-core      — MPV core: arrays, vote tallying, staging, LCD pages (parameterized)
  vvt-rh-hw-mod     — Modulating HW reheat for zone (AO valve)
  vvt-rh-hw-flt     — Floating HW reheat for zone (BO open/close + FLOAT)
  vvt-rh-elec-1     — 1-stage electric reheat for zone (BO)
  vvt-rh-elec-2     — 2-stage electric reheat for zone (BO x2)

VVT reheat modules reuse the same DAT/setpoint pattern as VAV but add
VVT-specific interlocks: warmup lockout, SAT lockout (electric), DAT high
limit (electric), minimum damper position (electric).

Thermostat modules: reuse vav-stat-hardwired and vav-stat-comm directly.
"""

from composition.modules.vvt.zone_core import build as build_zone_core
from composition.modules.vvt.bypass_core import build as build_bypass_core
from composition.modules.vvt.mpv_core import build as build_mpv_core
from composition.modules.vvt.rh_hw_mod import build as build_rh_hw_mod
from composition.modules.vvt.rh_hw_flt import build as build_rh_hw_flt
from composition.modules.vvt.rh_elec_1 import build as build_rh_elec_1
from composition.modules.vvt.rh_elec_2 import build as build_rh_elec_2

__all__ = ['build_zone_core', 'build_bypass_core', 'build_mpv_core',
           'build_rh_hw_mod', 'build_rh_hw_flt',
           'build_rh_elec_1', 'build_rh_elec_2']
