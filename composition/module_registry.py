"""
SBS Composition Engine v2 — Module Registry

Central registry of all available modules. Builds and caches module instances.
"""

from composition.modules import (
    core, dsp_ctrl, sz_vav_fan_ctrl, fan_supply, fan_return_exhaust, heating, cooling,
    economizer, erw, ventilation, optimum_start, safety, preheat, humidity, pump,
    dual_duct
)
from composition.modules.hw_plant import (
    build_core as hwp_build_core,
    build_blr_cascade, build_blr_full,
    build_pump_cs as hwp_build_pump_cs,
    build_pump_vfd as hwp_build_pump_vfd,
    build_pump_pri_sec as hwp_build_pump_pri_sec,
    build_mixing_valve, build_iso_valves, build_comb_damper,
    build_heat_exchanger, build_ahu_integration, build_makeup_water
)
from composition.modules.chw_plant import (
    build_core as chwp_build_core,
    build_chiller as chwp_build_chiller,
    build_pump_pri as chwp_build_pump_pri,
    build_pump_sec as chwp_build_pump_sec,
    build_cdwp as chwp_build_cdwp,
    build_tower as chwp_build_tower,
    build_tower_bypass as chwp_build_tower_bypass,
    build_bypass_valve as chwp_build_bypass_valve,
    build_iso_valves as chwp_build_iso_valves,
    build_makeup_water as chwp_build_makeup_water,
    build_ahu_integration as chwp_build_ahu_integration,
)
from composition.modules.vav import build_core as vav_build_core
from composition.modules.vav import build_rh_hw_mod as vav_build_rh_hw_mod
from composition.modules.vav import build_rh_hw_flt as vav_build_rh_hw_flt
from composition.modules.vav import build_rh_elec_1 as vav_build_rh_elec_1
from composition.modules.vav import build_rh_elec_2 as vav_build_rh_elec_2
from composition.modules.vav import build_rh_elec_scr as vav_build_rh_elec_scr
from composition.modules.vav import build_fan_parallel as vav_build_fan_parallel
from composition.modules.vav import build_fan_series as vav_build_fan_series
from composition.modules.vav import build_dd_hot_deck as vav_build_dd_hot_deck
from composition.modules.vav import build_stat_hardwired as vav_build_stat_hardwired
from composition.modules.vav import build_stat_hardwired_ud as vav_build_stat_hardwired_ud
from composition.modules.vav import build_stat_comm as vav_build_stat_comm
from composition.modules.vav import build_stat_comm_co2 as vav_build_stat_comm_co2
from composition.modules.vav import build_stat_comm_hum as vav_build_stat_comm_hum
from composition.modules.vav import build_stat_comm_occ as vav_build_stat_comm_occ
from composition.modules.vvt import (
    build_zone_core as vvt_build_zone_core,
    build_bypass_core as vvt_build_bypass_core,
    build_mpv_core as vvt_build_mpv_core,
    build_rh_hw_mod as vvt_build_rh_hw_mod,
    build_rh_hw_flt as vvt_build_rh_hw_flt,
    build_rh_elec_1 as vvt_build_rh_elec_1,
    build_rh_elec_2 as vvt_build_rh_elec_2,
)
from composition.modules.fcu import (
    build_fcu_core, build_fcu_fan_cv, build_fcu_fan_ms, build_fcu_fan_vfd,
    build_fcu_chw_mod, build_fcu_chw_flt, build_fcu_hw_mod, build_fcu_hw_flt,
    build_fcu_elec_1, build_fcu_elec_2, build_fcu_2pipe_mod, build_fcu_2pipe_flt,
    build_fcu_dx_1, build_fcu_dx_2, build_fcu_econ_mod, build_fcu_econ_flt,
    build_fcu_hp_core, build_fcu_hp_aux, build_fcu_freezestat,
)
from composition.modules.uv import (
    build_uv_core, build_uv_fan_cv, build_uv_fan_vfd,
    build_uv_oad_mod, build_uv_oad_flt, build_uv_fbp_mod, build_uv_fbp_flt,
    build_uv_hw_mod, build_uv_hw_flt, build_uv_hw_mod_fbp,
    build_uv_steam_mod, build_uv_steam_onoff, build_uv_steam_onoff_fbp,
    build_uv_chw_mod, build_uv_chw_flt, build_uv_dx_1, build_uv_dx_2,
    build_uv_dcv, build_uv_freezestat,
)


# Registry: module_id -> builder function
_BUILDERS = {}


def _register(module_id, builder_fn):
    _BUILDERS[module_id] = builder_fn


# Core
_register("core", core.build)
_register("dsp-ctrl", dsp_ctrl.build)
_register("sz-vav-fan-ctrl", sz_vav_fan_ctrl.build)

# Supply fan
_register("fan-sf-vfd", fan_supply.build_sf_vfd)
_register("fan-sf-cs", fan_supply.build_sf_cs)

# Return / exhaust / relief fan
_register("fan-rf-vfd", fan_return_exhaust.build_rf_vfd)
_register("fan-rf-cs", fan_return_exhaust.build_rf_cs)
_register("fan-ef-vfd", fan_return_exhaust.build_ef_vfd)
_register("fan-ef-cs", fan_return_exhaust.build_ef_cs)
_register("fan-rlf-vfd", fan_return_exhaust.build_rlf_vfd)
_register("fan-rlf-cs", fan_return_exhaust.build_rlf_cs)

# Heating
_register("htg-hw", heating.build_htg_hw)
_register("htg-elec", heating.build_htg_elec)
_register("htg-elec-2", heating.build_htg_elec_2)
_register("htg-elec-3", heating.build_htg_elec_3)
_register("htg-elec-scr", heating.build_htg_elec_scr)
_register("htg-gas", heating.build_htg_gas)
_register("htg-gas-mod", heating.build_htg_gas_mod)

# Cooling
_register("clg-chw", cooling.build_clg_chw)
_register("clg-dx", cooling.build_clg_dx)
_register("clg-dx-2", cooling.build_clg_dx_2)
_register("clg-dx-vfd", cooling.build_clg_dx_vfd)

# Economizer
_register("econ-db", economizer.build_econ_db)
_register("econ-enth", economizer.build_econ_enth)
_register("econ-diff", economizer.build_econ_diff)
_register("econ-diff-db", economizer.build_econ_diff_db)

# Energy Recovery
_register("erw", erw.build)

# Ventilation
_register("vent-fix", ventilation.build_vent_fix)
_register("vent-ams", ventilation.build_vent_ams)
_register("dcv-co2", ventilation.build_dcv_co2)
_register("dcv-occ", ventilation.build_dcv_occ)
_register("vent-100", ventilation.build_vent_100)

# Optimum Start
_register("opt-start", optimum_start.build)

# Safety
_register("safe-freeze", safety.build_safe_freeze)
_register("safe-smoke", safety.build_safe_smoke)
_register("safe-hi-static", safety.build_safe_hi_static)
_register("safe-filter", safety.build_safe_filter)
_register("safe-filter-oa", safety.build_safe_filter_oa)
_register("safe-filter-final", safety.build_safe_filter_final)
_register("safe-filter-ea", safety.build_safe_filter_ea)
_register("safe-fire-sd", safety.build_safe_fire_sd)
_register("safe-cond-ovf", safety.build_safe_cond_ovf)
_register("safe-freeze-dp", safety.build_safe_freeze_dp)
_register("safe-ea-static", safety.build_safe_ea_static)
_register("safe-ra-static", safety.build_safe_ra_static)

# Preheat
_register("ph-hw", preheat.build_ph_hw)
_register("ph-elec", preheat.build_ph_elec)
_register("ph-glycol", preheat.build_ph_glycol)

# Humidity
_register("hum-stm", humidity.build_hum_stm)
_register("hum-elec", humidity.build_hum_elec)
_register("hum-ultra", humidity.build_hum_ultra)
_register("dehum-sc", humidity.build_dehum_sc)

# Pumps
_register("htg-hw-pump", pump.build_hw_pump)
_register("clg-chw-pump", pump.build_chw_pump)
_register("ph-hw-pump", pump.build_ph_pump)

# Dual Duct
_register("dd-cold-chw", dual_duct.build_dd_cold_chw)
_register("dd-hot-hw", dual_duct.build_dd_hot_hw)
_register("dd-hot-elec", dual_duct.build_dd_hot_elec)

# HW Plant — static core registration (dynamic modules built via hwp_assemble)
_register("hw-core", hwp_build_core)

# CHW Plant — static core registration (dynamic modules built via chwp_assemble)
_register("chw-core", chwp_build_core)

# VAV Terminal Units
_register("vav-core", vav_build_core)
_register("vav-rh-hw-mod", vav_build_rh_hw_mod)
_register("vav-rh-hw-flt", vav_build_rh_hw_flt)
_register("vav-rh-elec-1", vav_build_rh_elec_1)
_register("vav-rh-elec-2", vav_build_rh_elec_2)
_register("vav-rh-elec-scr", vav_build_rh_elec_scr)
_register("vav-fan-parallel", vav_build_fan_parallel)
_register("vav-fan-series", vav_build_fan_series)
_register("vav-dd-hot-deck", vav_build_dd_hot_deck)
_register("vav-stat-hardwired", vav_build_stat_hardwired)
_register("vav-stat-hardwired-ud", vav_build_stat_hardwired_ud)
_register("vav-stat-comm", vav_build_stat_comm)
_register("vav-stat-comm-co2", vav_build_stat_comm_co2)
_register("vav-stat-comm-hum", vav_build_stat_comm_hum)
_register("vav-stat-comm-occ", vav_build_stat_comm_occ)

# VVT Terminal Units
_register("vvt-zone-core", vvt_build_zone_core)
_register("vvt-bypass-core", vvt_build_bypass_core)
_register("vvt-mpv-core", vvt_build_mpv_core)
_register("vvt-rh-hw-mod", vvt_build_rh_hw_mod)
_register("vvt-rh-hw-flt", vvt_build_rh_hw_flt)
_register("vvt-rh-elec-1", vvt_build_rh_elec_1)
_register("vvt-rh-elec-2", vvt_build_rh_elec_2)

# FCU modules
_register("fcu-core", build_fcu_core)
_register("fcu-fan-cv", build_fcu_fan_cv)
_register("fcu-fan-ms", build_fcu_fan_ms)
_register("fcu-fan-vfd", build_fcu_fan_vfd)
_register("fcu-chw-mod", build_fcu_chw_mod)
_register("fcu-chw-flt", build_fcu_chw_flt)
_register("fcu-hw-mod", build_fcu_hw_mod)
_register("fcu-hw-flt", build_fcu_hw_flt)
_register("fcu-elec-1", build_fcu_elec_1)
_register("fcu-elec-2", build_fcu_elec_2)
_register("fcu-2pipe-mod", build_fcu_2pipe_mod)
_register("fcu-2pipe-flt", build_fcu_2pipe_flt)
_register("fcu-dx-1", build_fcu_dx_1)
_register("fcu-dx-2", build_fcu_dx_2)
_register("fcu-econ-mod", build_fcu_econ_mod)
_register("fcu-econ-flt", build_fcu_econ_flt)
_register("fcu-hp-core", build_fcu_hp_core)
_register("fcu-hp-aux", build_fcu_hp_aux)
_register("fcu-freezestat", build_fcu_freezestat)

# UV modules
_register("uv-core", build_uv_core)
_register("uv-fan-cv", build_uv_fan_cv)
_register("uv-fan-vfd", build_uv_fan_vfd)
_register("uv-oad-mod", build_uv_oad_mod)
_register("uv-oad-flt", build_uv_oad_flt)
_register("uv-fbp-mod", build_uv_fbp_mod)
_register("uv-fbp-flt", build_uv_fbp_flt)
_register("uv-hw-mod", build_uv_hw_mod)
_register("uv-hw-flt", build_uv_hw_flt)
_register("uv-hw-mod-fbp", build_uv_hw_mod_fbp)
_register("uv-steam-mod", build_uv_steam_mod)
_register("uv-steam-onoff", build_uv_steam_onoff)
_register("uv-steam-onoff-fbp", build_uv_steam_onoff_fbp)
_register("uv-chw-mod", build_uv_chw_mod)
_register("uv-chw-flt", build_uv_chw_flt)
_register("uv-dx-1", build_uv_dx_1)
_register("uv-dx-2", build_uv_dx_2)
_register("uv-dcv", build_uv_dcv)
_register("uv-freezestat", build_uv_freezestat)


# Cache built modules
_CACHE = {}


def get_module(module_id):
    """Get a module by ID. Builds on first access."""
    if module_id not in _CACHE:
        if module_id not in _BUILDERS:
            raise ValueError(f"Unknown module: {module_id}")
        _CACHE[module_id] = _BUILDERS[module_id]()
    return _CACHE[module_id]


def list_modules():
    """List all available module IDs."""
    return sorted(_BUILDERS.keys())


def list_by_category():
    """List modules grouped by category."""
    result = {}
    for mid in _BUILDERS:
        mod = get_module(mid)
        cat = mod.category
        if cat not in result:
            result[cat] = []
        result[cat].append({
            "id": mod.id,
            "name": mod.name,
            "description": mod.description,
            "is_core": mod.is_core,
            "mutually_exclusive_group": mod.mutually_exclusive_group,
            "programs": len(mod.programs),
        })
    return result


_AHU_CORES = ['core', 'safe-freeze', 'safe-smoke', 'safe-filter']
_VAV_AHU_CORES = _AHU_CORES + ['dsp-ctrl']
_SZ_VAV_CORES = _AHU_CORES + ['sz-vav-fan-ctrl']

FAMILY_CORES = {
    'AHU-VAV':          _VAV_AHU_CORES,
    'VAV-AHU':          _VAV_AHU_CORES,
    'CV-AHU':           _AHU_CORES,
    'RTU':              _AHU_CORES,
    'DOAS':             _AHU_CORES,
    'SZ-CV':            _AHU_CORES,
    'SZ-VAV':           _SZ_VAV_CORES,
    'DD-AHU':           _AHU_CORES,
    'MZ-AHU':           _AHU_CORES,
    'HW-PLANT':         ['hw-core'],
    'CHW-PLANT-AIR':    ['chw-core'],
    'CHW-PLANT-TOWER':  ['chw-core'],
    # VAV Terminal Units
    'VAV-SD-CLG':       ['vav-core'],
    'VAV-SD-HW-MOD':    ['vav-core'],
    'VAV-SD-HW-FLT':    ['vav-core'],
    'VAV-SD-ELEC-1':    ['vav-core'],
    'VAV-SD-ELEC-2':    ['vav-core'],
    'VAV-SD-ELEC-SCR':  ['vav-core'],
    # Parallel fan-powered
    'VAV-PF-HW-MOD':    ['vav-core'],
    'VAV-PF-HW-FLT':    ['vav-core'],
    'VAV-PF-ELEC-2':    ['vav-core'],
    'VAV-PF-ELEC-SCR':  ['vav-core'],
    # Series fan-powered
    'VAV-SF-HW-MOD':    ['vav-core'],
    'VAV-SF-HW-FLT':    ['vav-core'],
    'VAV-SF-ELEC-2':    ['vav-core'],
    'VAV-SF-ELEC-SCR':  ['vav-core'],
    # Dual duct
    'VAV-DD-CLG':       ['vav-core'],
    'VAV-DD-HW-MOD':    ['vav-core'],
    'VAV-DD-HW-FLT':    ['vav-core'],
    # VVT System controllers
    'VVT-MPV':          ['vvt-mpv-core'],
    'VVT-ZONE':         ['vvt-zone-core'],
    'VVT-BYPASS':       ['vvt-bypass-core'],
    # FCU families
    'FCU-2P-SW':        ['fcu-core'],
    'FCU-2P-CHW':       ['fcu-core'],
    'FCU-4P-CHW-HW':    ['fcu-core'],
    'FCU-4P-CHW-HW-E':  ['fcu-core'],
    'FCU-4P-CHW-E':     ['fcu-core'],
    'FCU-DX-HW':        ['fcu-core'],
    'FCU-DX-E':         ['fcu-core'],
    'FCU-HP':           ['fcu-core'],
    'FCU-HP-AUX':       ['fcu-core'],
    # UV families
    'UV-HW-OAD':        ['uv-core'],
    'UV-HW-FBP':        ['uv-core'],
    'UV-STM-OAD':       ['uv-core'],
    'UV-STM-FBP':       ['uv-core'],
    'UV-CHW-HW-OAD':    ['uv-core'],
    'UV-CHW-HW-FBP':    ['uv-core'],
    'UV-DX-HW-OAD':     ['uv-core'],
    'UV-DX-HW-FBP':     ['uv-core'],
}


def get_core_modules(equipment_family=""):
    """Get core modules for an equipment family.

    Each family explicitly declares its own core modules.
    No inference, no shared groups, no bleed-through.
    """
    return list(FAMILY_CORES.get(equipment_family, _AHU_CORES))


# ═══════════════════════════════════════════════════════════════════════════
# SBS Standard Equipment Configurations
#
# Organized by equipment family, then least to most complex.
# Pick a standard, then toggle modules on/off to customize.
#
# Numbering:
#   VAV AHU:     SBS-AHU-101 to 120
#   CV AHU:      SBS-AHU-201 to 220
#   RTU:         SBS-RTU-301 to 320
#   DOAS / MAU:  SBS-DOAS-401 to 420
#   (Future)
#   VAV Terminal: SBS-VAV-501 to 520
#   FCU:         SBS-FCU-601 to 620
#   Plant:       SBS-PLT-701 to 720
# ═══════════════════════════════════════════════════════════════════════════

# Base safety modules
_SAFETY_BASE = ["safe-freeze", "safe-smoke", "safe-filter"]
_SAFETY_FULL = ["safe-freeze", "safe-smoke", "safe-hi-static", "safe-filter",
                "safe-filter-oa", "safe-filter-final"]
_SAFETY_FULL_EA = _SAFETY_FULL + ["safe-filter-ea"]

# Equipment family definitions — drives the UI dropdowns
EQUIPMENT_FAMILIES = {
    "VAV-AHU": {
        "name": "VAV Air Handling Unit",
        "description": "Variable air volume AHU — VFD supply fan, duct static pressure control, serves VAV terminal units",
        "prefix": "SBS-AHU",
        "required_modules": ["core", "fan-sf-vfd", "dsp-ctrl", "opt-start"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "fan", "safety", "pump"],
        "notes": "Supply fan always VFD. Return/exhaust/relief fan optional.",
    },
    "CV-AHU": {
        "name": "Constant Volume AHU",
        "description": "Constant volume AHU — constant speed or 2-speed fan, SAT control, no duct static",
        "prefix": "SBS-AHU",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "fan", "safety", "pump"],
        "notes": "Fan is constant speed or 2-speed. No DSP loop. SAT reset only.",
    },
    "RTU": {
        "name": "Rooftop Unit (Packaged)",
        "description": "Packaged rooftop unit — DX cooling, electric or gas heat, factory assembled",
        "prefix": "SBS-RTU",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "economizer", "ventilation", "safety"],
        "notes": "DX cooling (staged or VFD). Electric or gas heat. Usually no preheat or ERW.",
    },
    "DOAS": {
        "name": "Dedicated Outdoor Air System",
        "description": "100% outside air unit — no return air, typically with energy recovery",
        "prefix": "SBS-DOAS",
        "required_modules": ["core", "fan-sf-vfd", "vent-100"],
        "available_categories": ["cooling", "heating", "preheat", "energy-recovery", "humidity", "dsp", "safety", "pump"],
        "notes": "Always 100% OA. No economizer (no return air). ERW strongly recommended.",
    },
    "SZ-CV": {
        "name": "Single Zone Constant Volume",
        "description": "Constant speed fan, space temperature control — serves one zone, heating/cooling cycles to maintain space temp",
        "prefix": "SBS-SZCV",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "safety"],
        "notes": "Fan is constant speed. No duct static loop. Space temp sensor drives heating/cooling. Single zone only.",
    },
    "SZ-VAV": {
        "name": "Single Zone VAV",
        "description": "VFD fan modulates to space temperature — no VAV boxes, fan speed = capacity control for single zone",
        "prefix": "SBS-SZVAV",
        "required_modules": ["core", "fan-sf-vfd"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "safety", "pump"],
        "notes": "VFD supply fan modulates to space temp (NOT duct static). No downstream VAV boxes. Single zone served.",
    },
    "DD-AHU": {
        "name": "Dual Duct AHU",
        "description": "Hot deck + cold deck — downstream dual-duct mixing boxes blend hot and cold air per zone",
        "prefix": "SBS-DD",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "humidity", "fan", "dsp", "safety", "pump"],
        "notes": "Two parallel decks with independent SAT control. Hot deck SAT reset from heating demand, cold deck SAT reset from cooling demand. Common in retrofit.",
    },
    "MZ-AHU": {
        "name": "Multizone AHU",
        "description": "Zone mixing dampers AT the unit — hot and cold decks with per-zone mixing at the AHU",
        "prefix": "SBS-MZ",
        "required_modules": ["core"],
        "available_categories": ["cooling", "heating", "preheat", "economizer", "energy-recovery",
                                 "ventilation", "dsp", "safety"],
        "notes": "Zone dampers are outputs on the AHU controller. Limited zone count (4-12 typical). Hot/cold deck SAT control. Common in older buildings / retrofit.",
    },
    "HW-PLANT": {
        "name": "Hot Water Plant",
        "description": "Central HW heating plant — boiler control, pump control, distribution. MPS controller.",
        "prefix": "SBS-PLT",
        "required_modules": ["hw-core"],
        "available_categories": ["hw-core", "hw-boiler", "hw-pump", "hw-optional"],
        "notes": "Wizard-based configuration. Boiler and pump modules selected via question flow. One controller per plant.",
        "wizard": True,
    },
    "CHW-PLANT-AIR": {
        "name": "Air Cooled Chiller Plant",
        "description": "Air cooled chiller plant — chiller enable/staging, primary + secondary pumps, no cooling towers. MPS controller.",
        "prefix": "SBS-PLT",
        "required_modules": ["chw-core"],
        "available_categories": ["chw-core", "chw-chiller", "chw-pump-pri", "chw-pump-sec", "chw-optional"],
        "notes": "Wizard-based. Air cooled chillers — no condenser water system. Primary pumps CS, secondary pumps VFD with DP.",
        "wizard": True,
    },
    "VAV-SD-CLG": {
        "name": "VAV Single Duct — Cooling Only",
        "description": "Single duct VAV cooling only — RC-FLEXair with factory actuator and VP sensor, no reheat",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Simplest VAV: cooling only, no reheat, no fan. Factory damper and VP sensor. RC-FLEXair-12-A-F.",
    },
    "VAV-SD-HW-MOD": {
        "name": "VAV Single Duct — Modulating HW Reheat",
        "description": "Single duct VAV with modulating hot water reheat valve (AO 0-10V), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-hw-mod"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "HW reheat with modulating valve. DAT control loop. RC-FLEXair-34-A-F.",
    },
    "VAV-SD-HW-FLT": {
        "name": "VAV Single Duct — Floating HW Reheat",
        "description": "Single duct VAV with floating hot water reheat valve (BO open/close), DAT sensor, FLOAT()",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-hw-flt"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "HW reheat with floating valve. No PID loop — FLOAT() function. RC-FLEXair-34-A-F.",
    },
    "VAV-SD-ELEC-1": {
        "name": "VAV Single Duct — 1-Stage Electric Reheat",
        "description": "Single duct VAV with single stage electric reheat (BO), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-elec-1"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "1-stage electric reheat. On/off with DAT limit. RC-FLEXair-34-A-F.",
    },
    "VAV-SD-ELEC-2": {
        "name": "VAV Single Duct — 2-Stage Electric Reheat",
        "description": "Single duct VAV with two stage electric reheat (BO x2), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-elec-2"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "2-stage electric reheat. Staged on/off with DAT limit. RC-FLEXair-34-A-F.",
    },
    "VAV-SD-ELEC-SCR": {
        "name": "VAV Single Duct — SCR Modulating Electric Reheat",
        "description": "Single duct VAV with SCR modulating electric reheat (AO 0-10V), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-elec-scr"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "SCR modulating electric reheat. PID loop on DAT. RC-FLEXair-34-A-F.",
    },
    "VAV-PF-HW-MOD": {
        "name": "VAV Parallel Fan — Modulating HW Reheat",
        "description": "Parallel fan-powered VAV with modulating HW reheat valve (AO), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-hw-mod", "vav-fan-parallel"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Parallel fan + mod HW valve. RC-FLEXair-34-A-F.",
    },
    "VAV-PF-HW-FLT": {
        "name": "VAV Parallel Fan — Floating HW Reheat",
        "description": "Parallel fan-powered VAV with floating HW reheat valve (BO open/close), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-hw-flt", "vav-fan-parallel"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Parallel fan + floating HW valve + FLOAT(). RC-FLEXair-36-A-F.",
    },
    "VAV-PF-ELEC-2": {
        "name": "VAV Parallel Fan — 2-Stage Electric Reheat",
        "description": "Parallel fan-powered VAV with 2-stage electric reheat (BO x2), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-elec-2", "vav-fan-parallel"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Parallel fan + 2-stage electric. RC-FLEXair-36-A-F.",
    },
    "VAV-PF-ELEC-SCR": {
        "name": "VAV Parallel Fan — SCR Modulating Electric Reheat",
        "description": "Parallel fan-powered VAV with SCR modulating electric reheat (AO), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-elec-scr", "vav-fan-parallel"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Parallel fan + SCR electric. RC-FLEXair-34-A-F.",
    },
    "VAV-SF-HW-MOD": {
        "name": "VAV Series Fan — Modulating HW Reheat",
        "description": "Series fan-powered VAV with modulating HW reheat valve (AO), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-hw-mod", "vav-fan-series"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Series fan (continuous when occ) + mod HW valve. RC-FLEXair-34-A-F.",
    },
    "VAV-SF-HW-FLT": {
        "name": "VAV Series Fan — Floating HW Reheat",
        "description": "Series fan-powered VAV with floating HW reheat valve (BO open/close), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-hw-flt", "vav-fan-series"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Series fan (continuous when occ) + floating HW valve. RC-FLEXair-34-A-F.",
    },
    "VAV-SF-ELEC-2": {
        "name": "VAV Series Fan — 2-Stage Electric Reheat",
        "description": "Series fan-powered VAV with 2-stage electric reheat (BO x2), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-elec-2", "vav-fan-series"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Series fan (continuous when occ) + 2-stage electric. RC-FLEXair-34-A-F.",
    },
    "VAV-SF-ELEC-SCR": {
        "name": "VAV Series Fan — SCR Modulating Electric Reheat",
        "description": "Series fan-powered VAV with SCR modulating electric reheat (AO), DAT sensor",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-rh-elec-scr", "vav-fan-series"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Series fan (continuous when occ) + SCR electric. RC-FLEXair-34-A-F.",
    },
    "VAV-DD-CLG": {
        "name": "VAV Dual Duct — Cooling Only",
        "description": "Dual duct VAV with hot and cold deck dampers, no reheat",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-dd-hot-deck"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Dual duct cooling only. Hot deck AO + cold deck firmware. RC-FLEXair-34-A-F.",
    },
    "VAV-DD-HW-MOD": {
        "name": "VAV Dual Duct — Modulating HW Reheat",
        "description": "Dual duct VAV with hot deck damper + modulating HW reheat valve",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-dd-hot-deck", "vav-rh-hw-mod"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Dual duct + mod HW valve on hot deck. RC-FLEXair-34-A-F.",
    },
    "VAV-DD-HW-FLT": {
        "name": "VAV Dual Duct — Floating HW Reheat",
        "description": "Dual duct VAV with hot deck damper + floating HW reheat valve",
        "prefix": "SBS-VAV",
        "required_modules": ["vav-core", "vav-dd-hot-deck", "vav-rh-hw-flt"],
        "available_categories": ["thermostat", "thermostat-addon"],
        "notes": "Dual duct + floating HW valve on hot deck. RC-FLEXair-36-A-F.",
    },
    # ── VVT System ──
    "VVT-SYSTEM": {
        "name": "VVT System",
        "description": "Variable Volume Temperature system — MPV master RTU + zone dampers + bypass. Generates all controllers in one package.",
        "prefix": "SBS-VVT",
        "required_modules": ["vvt-mpv-core"],
        "available_categories": [],
        "notes": "Wizard-based. Generates MPV (ProView LCD), zone controllers (RC-FLEXair), and optional bypass controller.",
        "wizard": True,
    },
    # ── FCU Families ──
    "FCU-2P-SW": {
        "name": "FCU 2-Pipe Switchover",
        "description": "2-pipe fan coil — single valve switchover between heating and cooling based on HWS-OK or OAT",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-2pipe-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "FCU-2P-CHW": {
        "name": "FCU 2-Pipe CHW Only",
        "description": "2-pipe fan coil — chilled water cooling only, no heating",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-chw-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "FCU-4P-CHW-HW": {
        "name": "FCU 4-Pipe CHW + HW",
        "description": "4-pipe fan coil — separate CHW cooling and HW heating valves",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-chw-mod", "fcu-hw-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "FCU-4P-CHW-HW-E": {
        "name": "FCU 4-Pipe CHW + HW + Electric",
        "description": "4-pipe fan coil — CHW cooling, HW primary heating, electric backup",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-chw-mod", "fcu-hw-mod", "fcu-elec-1"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "FCU-4P-CHW-E": {
        "name": "FCU 4-Pipe CHW + Electric",
        "description": "4-pipe fan coil — CHW cooling, electric heating only",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-chw-mod", "fcu-elec-1"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "FCU-DX-HW": {
        "name": "FCU DX + HW",
        "description": "Fan coil with DX cooling and HW heating",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-dx-1", "fcu-hw-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "FCU-DX-E": {
        "name": "FCU DX + Electric",
        "description": "Fan coil with DX cooling and electric heating",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-dx-1", "fcu-elec-1"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "FCU-HP": {
        "name": "FCU Heat Pump",
        "description": "Heat pump fan coil — reversing valve, no auxiliary heat",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-hp-core"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "FCU-HP-AUX": {
        "name": "FCU Heat Pump + Aux",
        "description": "Heat pump fan coil with electric auxiliary heating",
        "prefix": "SBS-FCU",
        "required_modules": ["fcu-core", "fcu-fan-cv", "fcu-hp-core", "fcu-hp-aux"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    # ── UV Families ──
    "UV-HW-OAD": {
        "name": "UV HW + OA Damper",
        "description": "Unit ventilator — HW heating coil with modulating OA damper (ASHRAE Cycle 1+2)",
        "prefix": "SBS-UV",
        "required_modules": ["uv-core", "uv-fan-cv", "uv-hw-mod", "uv-oad-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "UV-HW-FBP": {
        "name": "UV HW + Face/Bypass",
        "description": "Unit ventilator — HW heating with face/bypass damper (cold/mild mode)",
        "prefix": "SBS-UV",
        "required_modules": ["uv-core", "uv-fan-cv", "uv-hw-mod-fbp", "uv-fbp-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "UV-STM-OAD": {
        "name": "UV Steam + OA Damper",
        "description": "Unit ventilator — steam heating with modulating OA damper",
        "prefix": "SBS-UV",
        "required_modules": ["uv-core", "uv-fan-cv", "uv-steam-mod", "uv-oad-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "UV-STM-FBP": {
        "name": "UV Steam + Face/Bypass",
        "description": "Unit ventilator — steam on/off with face/bypass damper",
        "prefix": "SBS-UV",
        "required_modules": ["uv-core", "uv-fan-cv", "uv-steam-onoff-fbp", "uv-fbp-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "UV-CHW-HW-OAD": {
        "name": "UV CHW + HW + OA Damper",
        "description": "Unit ventilator — CHW cooling + HW heating with OA damper",
        "prefix": "SBS-UV",
        "required_modules": ["uv-core", "uv-fan-cv", "uv-chw-mod", "uv-hw-mod", "uv-oad-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "UV-CHW-HW-FBP": {
        "name": "UV CHW + HW + Face/Bypass",
        "description": "Unit ventilator — CHW cooling + HW heating with face/bypass",
        "prefix": "SBS-UV",
        "required_modules": ["uv-core", "uv-fan-cv", "uv-chw-mod", "uv-hw-mod-fbp", "uv-fbp-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "UV-DX-HW-OAD": {
        "name": "UV DX + HW + OA Damper",
        "description": "Unit ventilator — DX cooling + HW heating with OA damper",
        "prefix": "SBS-UV",
        "required_modules": ["uv-core", "uv-fan-cv", "uv-dx-1", "uv-hw-mod", "uv-oad-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "UV-DX-HW-FBP": {
        "name": "UV DX + HW + Face/Bypass",
        "description": "Unit ventilator — DX cooling + HW heating with face/bypass",
        "prefix": "SBS-UV",
        "required_modules": ["uv-core", "uv-fan-cv", "uv-dx-1", "uv-hw-mod-fbp", "uv-fbp-mod"],
        "available_categories": ["fan", "cooling", "heating", "economizer", "safety", "thermostat", "thermostat-addon"],
    },
    "CHW-PLANT-TOWER": {
        "name": "Water Cooled Chiller Plant",
        "description": "Water cooled chiller plant — chillers, primary/secondary CHW pumps, CW pumps, cooling towers. MPS controller.",
        "prefix": "SBS-PLT",
        "required_modules": ["chw-core"],
        "available_categories": ["chw-core", "chw-chiller", "chw-pump-pri", "chw-pump-sec",
                                 "chw-cw-pump", "chw-tower", "chw-tower-opt", "chw-optional"],
        "notes": "Wizard-based. Water cooled chillers with cooling towers, CW pumps, and optional tower bypass.",
        "wizard": True,
    },
}

STANDARD_CONFIGS = {
    # ═══════════════════════════════════════════════════════════════════════
    #  VAV AHU — SBS-AHU-101 to 120
    #  Supply fan always VFD. Duct static pressure control standard.
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-AHU-101": {
        "family": "VAV-AHU",
        "name": "CHW / No Heat / Econ-DB",
        "description": "Simplest VAV AHU: CHW cooling only, dry bulb economizer, no heating",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-102": {
        "family": "VAV-AHU",
        "name": "CHW / Electric-2 / Econ-DB",
        "description": "CHW cooling with 2-stage electric backup heat",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-103": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-DB",
        "description": "Standard CHW/HW AHU with dry bulb economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-104": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth",
        "description": "Standard CHW/HW AHU with enthalpy economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-105": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / RF-VFD",
        "description": "CHW/HW with return fan VFD for building pressure control",
        "modules": [
            "core", "fan-sf-vfd", "fan-rf-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-106": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / EF-VFD",
        "description": "CHW/HW with exhaust fan VFD tracking OA airflow",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-107": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / ERW",
        "description": "CHW/HW with energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-108": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / ERW / EF-VFD",
        "description": "CHW/HW with ERW + exhaust fan VFD + OA airflow measurement",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-109": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / ERW / EF-VFD / DCV-CO2",
        "description": "Full-featured VAV AHU — the A201 reference config",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "dcv-co2", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-110": {
        "family": "VAV-AHU",
        "name": "CHW / HW / PH-HW / Econ-Enth",
        "description": "CHW/HW with hot water preheat coil + pump",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "ph-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-111": {
        "family": "VAV-AHU",
        "name": "CHW / HW / PH-HW / Econ-Enth / ERW / EF-VFD",
        "description": "Full preheat config: CHW, HW, preheat, ERW, exhaust fan",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "ph-hw", "econ-enth", "erw",
            "vent-ams", "opt-start",
        ] + _SAFETY_FULL_EA,
    },
    "SBS-AHU-112": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / HUM-STM",
        "description": "CHW/HW with steam humidifier",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "hum-stm",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-113": {
        "family": "VAV-AHU",
        "name": "CHW / HW / Econ-Enth / DEHUM-SC",
        "description": "CHW/HW with subcooling dehumidification",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "dehum-sc",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-114": {
        "family": "VAV-AHU",
        "name": "FULL — CHW / HW / PH-HW / ERW / EF-VFD / DCV / HUM / DEHUM",
        "description": "Maximum VAV AHU: every feature enabled",
        "modules": [
            "core", "fan-sf-vfd", "fan-ef-vfd",
            "clg-chw", "htg-hw", "ph-hw",
            "econ-enth", "erw",
            "dcv-co2", "hum-stm", "dehum-sc",
            "opt-start",
        ] + _SAFETY_FULL_EA + ["safe-cond-ovf"],
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  RTU (PACKAGED ROOFTOP) — SBS-RTU-301 to 310
    #  DX cooling, electric or gas heat, factory assembled
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-RTU-301": {
        "family": "RTU",
        "name": "DX-1 / Electric-1 / CS — Minimal",
        "description": "Simplest RTU: single DX, single electric, constant speed, no economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-dx", "htg-elec",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-302": {
        "family": "RTU",
        "name": "DX-2 / Electric-2 / VFD / Econ-DB",
        "description": "Standard RTU: 2-stage DX, 2-stage electric, VFD, dry bulb economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-303": {
        "family": "RTU",
        "name": "DX-2 / Gas-1 / VFD / Econ-DB",
        "description": "Gas-fired RTU: 2-stage DX, single gas, VFD, economizer",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-gas", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-304": {
        "family": "RTU",
        "name": "DX-2 / Gas-MOD / VFD / Econ-DB",
        "description": "Modulating gas RTU: 2-stage DX, modulating gas heat",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-gas-mod", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-305": {
        "family": "RTU",
        "name": "DX-VFD / Electric-SCR / VFD / Econ-DB",
        "description": "Variable capacity RTU: VFD compressor, modulating electric heat",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-vfd", "htg-elec-scr", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-RTU-306": {
        "family": "RTU",
        "name": "DX-2 / Electric-3 / VFD / Econ-DB / DCV-CO2",
        "description": "Full RTU: 2-stage DX, 3-stage electric, VFD, economizer, DCV",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-elec-3", "econ-db",
            "dcv-co2", "opt-start",
        ] + _SAFETY_BASE,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  CV AHU (CONSTANT VOLUME) — SBS-AHU-201 to 210
    #  Constant speed fan, no duct static, SAT control
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-AHU-201": {
        "family": "CV-AHU",
        "name": "CHW / HW / CS / Econ-DB",
        "description": "Constant volume CHW/HW AHU with dry bulb economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-202": {
        "family": "CV-AHU",
        "name": "CHW / HW / CS / Econ-Enth",
        "description": "Constant volume CHW/HW AHU with enthalpy economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-AHU-203": {
        "family": "CV-AHU",
        "name": "CHW / HW / CS / Econ-Enth / ERW",
        "description": "Constant volume with energy recovery wheel",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-AHU-204": {
        "family": "CV-AHU",
        "name": "CHW / Electric-2 / CS / Econ-DB",
        "description": "Constant volume CHW + electric heat",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  DOAS / MAU — SBS-DOAS-401 to 410
    #  100% outside air, no return, typically with energy recovery
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-DOAS-401": {
        "family": "DOAS",
        "name": "CHW / PH-HW / ERW",
        "description": "Standard DOAS: CHW cooling, HW preheat, energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "ph-hw", "erw",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-DOAS-402": {
        "family": "DOAS",
        "name": "DX-2 / PH-HW / ERW",
        "description": "DX DOAS: 2-stage DX, HW preheat, energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "ph-hw", "erw",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-DOAS-403": {
        "family": "DOAS",
        "name": "CHW / PH-HW / ERW / HUM-STM",
        "description": "DOAS with humidifier: CHW, HW preheat, ERW, steam humidifier",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "ph-hw", "erw", "hum-stm",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-DOAS-404": {
        "family": "DOAS",
        "name": "CHW / PH-Glycol / ERW",
        "description": "DOAS with glycol preheat: CHW cooling, glycol preheat, ERW",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "ph-glycol", "erw",
            "vent-100",
        ] + _SAFETY_FULL,
    },
    "SBS-DOAS-405": {
        "family": "DOAS",
        "name": "CHW / HW / No ERW",
        "description": "Simple DOAS without energy recovery: CHW, HW, no ERW",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw",
            "vent-100",
        ] + _SAFETY_BASE,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  SINGLE ZONE CV — SBS-SZCV-501 to 510
    #  Constant speed fan, space temp control, single zone
    #  Fan cycles or runs continuous — heating/cooling modulates to space temp
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-SZCV-501": {
        "family": "SZ-CV",
        "name": "CHW / HW / CS / Econ-DB — Basic",
        "description": "Single zone CV: CHW cooling, HW heating, constant speed, dry bulb econ",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-SZCV-502": {
        "family": "SZ-CV",
        "name": "CHW / Electric-1 / CS — Minimal",
        "description": "Simplest single zone: CHW cooling, single electric heat, constant speed",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-elec",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-SZCV-503": {
        "family": "SZ-CV",
        "name": "DX-1 / Electric-1 / CS — Package",
        "description": "Packaged single zone: single DX, single electric, constant speed",
        "modules": [
            "core", "fan-sf-cs",
            "clg-dx", "htg-elec",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-SZCV-504": {
        "family": "SZ-CV",
        "name": "DX-2 / Gas-1 / CS / Econ-DB — Gas Package",
        "description": "Packaged single zone: 2-stage DX, gas heat, economizer",
        "modules": [
            "core", "fan-sf-cs",
            "clg-dx-2", "htg-gas", "econ-db",
            "vent-fix",
        ] + _SAFETY_BASE,
    },
    "SBS-SZCV-505": {
        "family": "SZ-CV",
        "name": "CHW / HW / CS / Econ-Enth / ERW — With ERW",
        "description": "Single zone CV with energy recovery wheel",
        "modules": [
            "core", "fan-sf-cs",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix",
        ] + _SAFETY_FULL,
    },
    "SBS-SZCV-506": {
        "family": "SZ-CV",
        "name": "HW Only / CS — Heating Only (MAU)",
        "description": "Heating-only make-up air: HW heat, constant speed, no cooling",
        "modules": [
            "core", "fan-sf-cs",
            "htg-hw",
            "vent-fix",
        ] + _SAFETY_BASE,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  SINGLE ZONE VAV — SBS-SZVAV-601 to 610
    #  VFD supply fan modulates to SPACE TEMP (not duct static)
    #  No downstream VAV boxes — fan speed IS the capacity control
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-SZVAV-601": {
        "family": "SZ-VAV",
        "name": "CHW / HW / VFD / Econ-DB — Basic",
        "description": "Single zone VAV: CHW/HW, VFD fan to space temp, dry bulb econ",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-SZVAV-602": {
        "family": "SZ-VAV",
        "name": "CHW / HW / VFD / Econ-Enth — Enthalpy",
        "description": "Single zone VAV: CHW/HW, VFD fan to space temp, enthalpy econ",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-SZVAV-603": {
        "family": "SZ-VAV",
        "name": "CHW / HW / VFD / Econ-Enth / ERW — With ERW",
        "description": "Single zone VAV with energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-SZVAV-604": {
        "family": "SZ-VAV",
        "name": "DX-2 / Electric-2 / VFD / Econ-DB — Package",
        "description": "Packaged single zone VAV: 2-stage DX, 2-stage electric, VFD to space temp",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-elec-2", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-SZVAV-605": {
        "family": "SZ-VAV",
        "name": "DX-2 / Gas-1 / VFD / Econ-DB — Gas Package",
        "description": "Packaged single zone VAV: 2-stage DX, gas heat, VFD to space temp",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-dx-2", "htg-gas", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-SZVAV-606": {
        "family": "SZ-VAV",
        "name": "CHW / HW / PH-HW / VFD / Econ-Enth / ERW — Full Featured",
        "description": "Full single zone VAV: CHW, HW, preheat, ERW, enthalpy econ",
        "modules": [
            "core", "fan-sf-vfd",
            "clg-chw", "htg-hw", "ph-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  DUAL DUCT AHU — SBS-DD-701 to 710
    #  Hot deck + cold deck, downstream mixing boxes
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-DD-701": {
        "family": "DD-AHU",
        "name": "DD CHW / HW / VFD / Econ-DB",
        "description": "Dual duct VAV: CHW cold deck, HW hot deck, VFD fan, dry bulb econ",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-DD-702": {
        "family": "DD-AHU",
        "name": "DD CHW / HW / VFD / Econ-Enth",
        "description": "Dual duct VAV: CHW cold deck, HW hot deck, enthalpy econ",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-DD-703": {
        "family": "DD-AHU",
        "name": "DD CHW / HW / CS / Econ-DB — CV Dual Duct",
        "description": "Dual duct CV: constant speed fan, CHW/HW decks",
        "modules": [
            "core", "fan-sf-cs",
            "dd-cold-chw", "dd-hot-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-DD-704": {
        "family": "DD-AHU",
        "name": "DD CHW / Electric / VFD / Econ-DB",
        "description": "Dual duct VAV: CHW cold deck, electric hot deck",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-elec", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },
    "SBS-DD-705": {
        "family": "DD-AHU",
        "name": "DD CHW / HW / VFD / Econ-Enth / ERW",
        "description": "Dual duct VAV with energy recovery wheel",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-hw", "econ-enth", "erw",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  MULTIZONE AHU — SBS-MZ-801 to 810
    #  Zone mixing dampers at the unit, hot/cold decks
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-MZ-801": {
        "family": "MZ-AHU",
        "name": "MZ CHW / HW / CS / Econ-DB",
        "description": "Multizone CV: CHW cold deck, HW hot deck, constant speed, dry bulb econ",
        "modules": [
            "core", "fan-sf-cs",
            "dd-cold-chw", "dd-hot-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-MZ-802": {
        "family": "MZ-AHU",
        "name": "MZ CHW / HW / CS / Econ-Enth",
        "description": "Multizone CV: CHW cold deck, HW hot deck, enthalpy econ",
        "modules": [
            "core", "fan-sf-cs",
            "dd-cold-chw", "dd-hot-hw", "econ-enth",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-MZ-803": {
        "family": "MZ-AHU",
        "name": "MZ CHW / Electric / CS / Econ-DB",
        "description": "Multizone CV: CHW cold deck, electric hot deck",
        "modules": [
            "core", "fan-sf-cs",
            "dd-cold-chw", "dd-hot-elec", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_BASE,
    },
    "SBS-MZ-804": {
        "family": "MZ-AHU",
        "name": "MZ CHW / HW / VFD / Econ-DB",
        "description": "Multizone with VFD: CHW/HW decks, dry bulb econ",
        "modules": [
            "core", "fan-sf-vfd",
            "dd-cold-chw", "dd-hot-hw", "econ-db",
            "vent-fix", "opt-start",
        ] + _SAFETY_FULL,
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  HW Plant — SBS-PLT-701 to 720
    #  Wizard-based. Module list built dynamically from parameters.
    #  These presets define the wizard defaults for quick selection.
    # ═══════════════════════════════════════════════════════════════════════
    "SBS-PLT-701": {
        "family": "HW-PLANT",
        "name": "2-Boiler Cascade, 2-Pump CS",
        "description": "Interface boilers with analog setpoint, 2 constant speed pumps",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "cascade", "num_boilers": 2, "spt_output": "analog",
            "monitor_boiler_temps": False,
            "pump_type": "cs", "num_pumps": 2,
        },
    },
    "SBS-PLT-702": {
        "family": "HW-PLANT",
        "name": "2-Boiler Cascade, 2-Pump VFD",
        "description": "Interface boilers with analog setpoint, 2 VFD pumps with DP control",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "cascade", "num_boilers": 2, "spt_output": "analog",
            "monitor_boiler_temps": False,
            "pump_type": "vfd", "num_pumps": 2,
        },
    },
    "SBS-PLT-703": {
        "family": "HW-PLANT",
        "name": "2-Boiler Full, 2-Pump CS",
        "description": "Direct fire rate control, 2 boilers, 2 constant speed pumps",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "full", "num_boilers": 2, "monitor_boiler_temps": True,
            "pump_type": "cs", "num_pumps": 2,
        },
    },
    "SBS-PLT-704": {
        "family": "HW-PLANT",
        "name": "2-Boiler Full, 2-Pump VFD",
        "description": "Direct fire rate control, 2 boilers, 2 VFD pumps with DP",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "full", "num_boilers": 2, "monitor_boiler_temps": True,
            "pump_type": "vfd", "num_pumps": 2,
        },
    },
    "SBS-PLT-705": {
        "family": "HW-PLANT",
        "name": "3-Boiler Full, Pri-Sec (2+2)",
        "description": "3 direct-control boilers, primary/secondary pumping 2+2",
        "modules": ["hw-core"],
        "hwp_params": {
            "boiler_type": "full", "num_boilers": 3, "monitor_boiler_temps": True,
            "pump_type": "pri-sec", "num_primary": 2, "num_secondary": 2,
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  CHW Plant Air Cooled — SBS-PLT-751 to 760
    # ═══════════════════════════════════════════════════════════════════════
    "SBS-PLT-751": {
        "family": "CHW-PLANT-AIR",
        "name": "1-Chiller, 1-Pri, 2-Sec VFD",
        "description": "Single air cooled chiller, 1 primary CS pump, 2 secondary VFD pumps with DP",
        "modules": ["chw-core"],
        "chwp_params": {
            "num_chillers": 1, "num_pri_pumps": 1, "num_sec_pumps": 2, "num_dp_sensors": 2,
        },
    },
    "SBS-PLT-752": {
        "family": "CHW-PLANT-AIR",
        "name": "2-Chiller, 2-Pri, 2-Sec VFD",
        "description": "2 air cooled chillers, 2 primary CS pumps, 2 secondary VFD pumps with DP",
        "modules": ["chw-core"],
        "chwp_params": {
            "num_chillers": 2, "num_pri_pumps": 2, "num_sec_pumps": 2, "num_dp_sensors": 2,
        },
    },
    "SBS-PLT-753": {
        "family": "CHW-PLANT-AIR",
        "name": "2-Chiller, 2-Pri, 3-Sec VFD, Bypass",
        "description": "2 air cooled chillers, 2 primary CS, 3 secondary VFD, CHW bypass valve",
        "modules": ["chw-core"],
        "chwp_params": {
            "num_chillers": 2, "num_pri_pumps": 2, "num_sec_pumps": 3, "num_dp_sensors": 2,
            "bypass_valve": True,
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  CHW Plant Water Cooled (Tower) — SBS-PLT-771 to 780
    # ═══════════════════════════════════════════════════════════════════════
    "SBS-PLT-771": {
        "family": "CHW-PLANT-TOWER",
        "name": "2-Chiller, 2-Tower, 2+2 Pumps",
        "description": "2 water cooled chillers, 2 towers, 2 primary + 2 secondary CHW, 2 CW pumps",
        "modules": ["chw-core"],
        "chwp_params": {
            "num_chillers": 2, "num_pri_pumps": 2, "num_sec_pumps": 2, "num_dp_sensors": 2,
            "num_cw_pumps": 2, "num_towers": 2, "tower_bypass": True,
        },
    },
    "SBS-PLT-772": {
        "family": "CHW-PLANT-TOWER",
        "name": "2-Chiller, 2-Tower, 2+3 Pumps, Iso",
        "description": "2 water cooled chillers, 2 towers, 2 pri + 3 sec, 2 CW pumps, isolation valves",
        "modules": ["chw-core"],
        "chwp_params": {
            "num_chillers": 2, "num_pri_pumps": 2, "num_sec_pumps": 3, "num_dp_sensors": 2,
            "num_cw_pumps": 2, "num_towers": 2, "tower_bypass": True,
            "iso_valves": True,
        },
    },
    "SBS-PLT-773": {
        "family": "CHW-PLANT-TOWER",
        "name": "3-Chiller, 3-Tower, 3+3 Pumps, Iso",
        "description": "3 water cooled chillers, 3 towers, 3 pri + 3 sec, 3 CW pumps, isolation + bypass",
        "modules": ["chw-core"],
        "chwp_params": {
            "num_chillers": 3, "num_pri_pumps": 3, "num_sec_pumps": 3, "num_dp_sensors": 2,
            "num_cw_pumps": 3, "num_towers": 3, "tower_bypass": True,
            "iso_valves": True, "bypass_valve": True,
        },
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  VAV Terminal Units — SBS-VAV-501 to 520
    #  RC-FLEXair controllers with factory actuator + VP sensor
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-VAV-501": {
        "family": "VAV-SD-CLG",
        "name": "Single Duct — Cooling Only",
        "description": "Simplest VAV: cooling only, no reheat, no fan. RC-FLEXair-12.",
        "modules": ["vav-core", "vav-stat-hardwired"],
    },
    "SBS-VAV-502": {
        "family": "VAV-SD-HW-MOD",
        "name": "Single Duct — Modulating HW Reheat",
        "description": "HW reheat with modulating valve + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-hw-mod", "vav-stat-hardwired"],
    },
    "SBS-VAV-503": {
        "family": "VAV-SD-HW-FLT",
        "name": "Single Duct — Floating HW Reheat",
        "description": "HW reheat with floating valve + DAT sensor + FLOAT(). RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-hw-flt", "vav-stat-hardwired"],
    },
    "SBS-VAV-504": {
        "family": "VAV-SD-ELEC-1",
        "name": "Single Duct — 1-Stage Electric Reheat",
        "description": "1-stage electric reheat + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-elec-1", "vav-stat-hardwired"],
    },
    "SBS-VAV-505": {
        "family": "VAV-SD-ELEC-2",
        "name": "Single Duct — 2-Stage Electric Reheat",
        "description": "2-stage electric reheat + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-elec-2", "vav-stat-hardwired"],
    },
    "SBS-VAV-506": {
        "family": "VAV-SD-ELEC-SCR",
        "name": "Single Duct — SCR Modulating Electric Reheat",
        "description": "SCR modulating electric + DAT sensor + RH-LOOP. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-elec-scr", "vav-stat-hardwired"],
    },
    "SBS-VAV-507": {
        "family": "VAV-PF-HW-MOD",
        "name": "Parallel Fan — Modulating HW Reheat",
        "description": "Parallel fan + mod HW valve + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-hw-mod", "vav-fan-parallel", "vav-stat-hardwired"],
    },
    "SBS-VAV-508": {
        "family": "VAV-PF-HW-FLT",
        "name": "Parallel Fan — Floating HW Reheat",
        "description": "Parallel fan + floating HW valve + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-hw-flt", "vav-fan-parallel", "vav-stat-hardwired"],
    },
    "SBS-VAV-509": {
        "family": "VAV-PF-ELEC-2",
        "name": "Parallel Fan — 2-Stage Electric Reheat",
        "description": "Parallel fan + 2-stage electric + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-elec-2", "vav-fan-parallel", "vav-stat-hardwired"],
    },
    "SBS-VAV-510": {
        "family": "VAV-PF-ELEC-SCR",
        "name": "Parallel Fan — SCR Modulating Electric Reheat",
        "description": "Parallel fan + SCR electric + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-elec-scr", "vav-fan-parallel", "vav-stat-hardwired"],
    },
    "SBS-VAV-511": {
        "family": "VAV-SF-HW-MOD",
        "name": "Series Fan — Modulating HW Reheat",
        "description": "Series fan + mod HW valve + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-hw-mod", "vav-fan-series", "vav-stat-hardwired"],
    },
    "SBS-VAV-512": {
        "family": "VAV-SF-HW-FLT",
        "name": "Series Fan — Floating HW Reheat",
        "description": "Series fan + floating HW valve + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-hw-flt", "vav-fan-series", "vav-stat-hardwired"],
    },
    "SBS-VAV-513": {
        "family": "VAV-SF-ELEC-2",
        "name": "Series Fan — 2-Stage Electric Reheat",
        "description": "Series fan + 2-stage electric + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-elec-2", "vav-fan-series", "vav-stat-hardwired"],
    },
    "SBS-VAV-514": {
        "family": "VAV-SF-ELEC-SCR",
        "name": "Series Fan — SCR Modulating Electric Reheat",
        "description": "Series fan + SCR electric + DAT sensor. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-rh-elec-scr", "vav-fan-series", "vav-stat-hardwired"],
    },
    "SBS-VAV-515": {
        "family": "VAV-DD-CLG",
        "name": "Dual Duct — Cooling Only",
        "description": "Dual duct hot+cold deck dampers. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-dd-hot-deck", "vav-stat-hardwired"],
    },
    "SBS-VAV-516": {
        "family": "VAV-DD-HW-MOD",
        "name": "Dual Duct — Modulating HW Reheat",
        "description": "Dual duct + mod HW valve on hot deck. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-dd-hot-deck", "vav-rh-hw-mod", "vav-stat-hardwired"],
    },
    "SBS-VAV-517": {
        "family": "VAV-DD-HW-FLT",
        "name": "Dual Duct — Floating HW Reheat",
        "description": "Dual duct + floating HW valve on hot deck. RC-FLEXair-34.",
        "modules": ["vav-core", "vav-dd-hot-deck", "vav-rh-hw-flt", "vav-stat-hardwired"],
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  FCU — SBS-FCU-601 to 609
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-FCU-601": {
        "family": "FCU-2P-SW",
        "name": "2-Pipe HW/CHW Switchover",
        "description": "2-pipe FCU with single valve switching between heating and cooling. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-2pipe-mod"],
        "controller": "MPZ",
    },
    "SBS-FCU-602": {
        "family": "FCU-2P-CHW",
        "name": "2-Pipe CHW Only",
        "description": "2-pipe FCU cooling only with CHW modulating valve. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-chw-mod"],
        "controller": "MPZ",
    },
    "SBS-FCU-603": {
        "family": "FCU-4P-CHW-HW",
        "name": "4-Pipe CHW + HW Modulating",
        "description": "4-pipe FCU with separate CHW and HW modulating valves. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-chw-mod", "fcu-hw-mod"],
        "controller": "MPZ",
    },
    "SBS-FCU-604": {
        "family": "FCU-4P-CHW-HW-E",
        "name": "4-Pipe CHW + HW + Electric Backup",
        "description": "4-pipe FCU: CHW cooling, HW primary heat, electric backup. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-chw-mod", "fcu-hw-mod", "fcu-elec-1"],
        "controller": "MPZ",
    },
    "SBS-FCU-605": {
        "family": "FCU-4P-CHW-E",
        "name": "4-Pipe CHW + Electric Only",
        "description": "4-pipe FCU: CHW cooling, electric heating. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-chw-mod", "fcu-elec-1"],
        "controller": "MPZ",
    },
    "SBS-FCU-606": {
        "family": "FCU-DX-HW",
        "name": "DX + HW",
        "description": "DX cooling with HW heating valve. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-dx-1", "fcu-hw-mod"],
        "controller": "MPZ",
    },
    "SBS-FCU-607": {
        "family": "FCU-DX-E",
        "name": "DX + Electric",
        "description": "DX cooling with electric heating. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-dx-1", "fcu-elec-1"],
        "controller": "MPZ",
    },
    "SBS-FCU-608": {
        "family": "FCU-HP",
        "name": "Heat Pump — No Aux",
        "description": "Heat pump FCU: reversing valve + compressor, no auxiliary heat. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-hp-core"],
        "controller": "MPZ",
    },
    "SBS-FCU-609": {
        "family": "FCU-HP-AUX",
        "name": "Heat Pump + Electric Aux",
        "description": "Heat pump FCU with electric auxiliary heating. MPZ-88.",
        "modules": ["fcu-core", "fcu-fan-cv", "fcu-hp-core", "fcu-hp-aux"],
        "controller": "MPZ",
    },

    # ═══════════════════════════════════════════════════════════════════════
    #  UV — SBS-UV-701 to 708
    # ═══════════════════════════════════════════════════════════════════════

    "SBS-UV-701": {
        "family": "UV-HW-OAD",
        "name": "HW + OA Damper",
        "description": "Unit ventilator: HW heating coil with modulating OA damper. MPZ-88.",
        "modules": ["uv-core", "uv-fan-cv", "uv-hw-mod", "uv-oad-mod"],
        "controller": "MPZ",
    },
    "SBS-UV-702": {
        "family": "UV-HW-FBP",
        "name": "HW + Face/Bypass",
        "description": "Unit ventilator: HW heating with face/bypass damper. MPZ-88.",
        "modules": ["uv-core", "uv-fan-cv", "uv-hw-mod-fbp", "uv-fbp-mod"],
        "controller": "MPZ",
    },
    "SBS-UV-703": {
        "family": "UV-STM-OAD",
        "name": "Steam + OA Damper",
        "description": "Unit ventilator: steam heating with modulating OA damper. MPZ-88.",
        "modules": ["uv-core", "uv-fan-cv", "uv-steam-mod", "uv-oad-mod"],
        "controller": "MPZ",
    },
    "SBS-UV-704": {
        "family": "UV-STM-FBP",
        "name": "Steam + Face/Bypass",
        "description": "Unit ventilator: steam on/off with face/bypass damper. MPZ-88.",
        "modules": ["uv-core", "uv-fan-cv", "uv-steam-onoff-fbp", "uv-fbp-mod"],
        "controller": "MPZ",
    },
    "SBS-UV-705": {
        "family": "UV-CHW-HW-OAD",
        "name": "CHW + HW + OA Damper",
        "description": "Unit ventilator: CHW cooling + HW heating with OA damper. MPZ-88.",
        "modules": ["uv-core", "uv-fan-cv", "uv-chw-mod", "uv-hw-mod", "uv-oad-mod"],
        "controller": "MPZ",
    },
    "SBS-UV-706": {
        "family": "UV-CHW-HW-FBP",
        "name": "CHW + HW + Face/Bypass",
        "description": "Unit ventilator: CHW cooling + HW heating with face/bypass. MPZ-88.",
        "modules": ["uv-core", "uv-fan-cv", "uv-chw-mod", "uv-hw-mod-fbp", "uv-fbp-mod"],
        "controller": "MPZ",
    },
    "SBS-UV-707": {
        "family": "UV-DX-HW-OAD",
        "name": "DX + HW + OA Damper",
        "description": "Unit ventilator: DX cooling + HW heating with OA damper. MPZ-88.",
        "modules": ["uv-core", "uv-fan-cv", "uv-dx-1", "uv-hw-mod", "uv-oad-mod"],
        "controller": "MPZ",
    },
    "SBS-UV-708": {
        "family": "UV-DX-HW-FBP",
        "name": "DX + HW + Face/Bypass",
        "description": "Unit ventilator: DX cooling + HW heating with face/bypass. MPZ-88.",
        "modules": ["uv-core", "uv-fan-cv", "uv-dx-1", "uv-hw-mod-fbp", "uv-fbp-mod"],
        "controller": "MPZ",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# HW Plant Dynamic Assembly
# ═══════════════════════════════════════════════════════════════════════════

def hwp_assemble(params):
    """Build HW plant module list from wizard parameters.

    Args:
        params: dict with keys:
            boiler_type: "cascade" | "full"
            num_boilers: 1-4
            spt_output: "analog" | "bacnet" (cascade only)
            monitor_boiler_temps: bool
            pump_type: "cs" | "vfd" | "pri-sec"
            num_pumps: 1-4 (for cs/vfd)
            num_primary: 1-4 (for pri-sec)
            num_secondary: 1-4 (for pri-sec)
            mixing_valve: bool
            iso_valves: bool
            comb_damper: bool
            heat_exchanger: bool
            hx_valve_type: "single_mod" | "single_onoff" | "third_twothird"
            ahu_integration: bool
            num_ahus: 1-8
            makeup_water: bool

    Returns:
        list of Module objects ready for assembly
    """
    modules = [hwp_build_core()]

    bt = params.get('boiler_type', 'cascade')
    nb = params.get('num_boilers', 2)
    mbt = params.get('monitor_boiler_temps', False)

    if bt == 'cascade':
        analog = params.get('spt_output', 'analog') == 'analog'
        modules.append(build_blr_cascade(num_boilers=nb, analog_spt=analog, monitor_hwst=mbt))
    else:
        modules.append(build_blr_full(num_boilers=nb, monitor_hwst=mbt))

    pt = params.get('pump_type', 'cs')
    if pt == 'cs':
        modules.append(hwp_build_pump_cs(num_pumps=params.get('num_pumps', 2)))
    elif pt == 'vfd':
        modules.append(hwp_build_pump_vfd(num_pumps=params.get('num_pumps', 2)))
    elif pt == 'pri-sec':
        modules.append(hwp_build_pump_pri_sec(
            num_primary=params.get('num_primary', 2),
            num_secondary=params.get('num_secondary', 2)))

    if params.get('mixing_valve'):
        modules.append(build_mixing_valve())
    if params.get('iso_valves'):
        modules.append(build_iso_valves(num_boilers=nb))
    if params.get('comb_damper'):
        modules.append(build_comb_damper(num_boilers=nb))
    if params.get('heat_exchanger'):
        hvt = params.get('hx_valve_type', 'single_mod')
        modules.append(build_heat_exchanger(valve_type=hvt))
    if params.get('ahu_integration'):
        modules.append(build_ahu_integration(num_ahus=params.get('num_ahus', 2)))
    if params.get('makeup_water'):
        modules.append(build_makeup_water())

    # Generate dynamic CONFIG.bas based on pump type
    d = "{device-name}"
    cfg = f"REM **** HW Plant Configuration Program\n"
    cfg += "REM **** Generated by SBS Composition Engine v2\n\n"
    cfg += f"{d}-NET-OAT = {d}-OAT\n"
    cfg += f"{d}-NET-OAH = {d}-OAH\n"
    cfg += f"{d}-NET-OA-ERH = ENTHALPY( {d}-NET-OAT , {d}-NET-OAH , 1 )\n"
    cfg += f"{d}-HW-DELTA-T = {d}-HWS-T - {d}-HWR-T\n\n"

    if pt == 'pri-sec':
        np = params.get('num_primary', 2)
        ns = params.get('num_secondary', 2)
        cfg += "REM **** Primary pump runtime tracking ****\n"
        for n in range(1, np + 1):
            cfg += f"{d}-PHWP{n}-RUNTIME = TIME-ON( {d}-PHWP{n}-STS ) / 3600\n"
        cfg += "REM **** Secondary pump runtime tracking ****\n"
        for n in range(1, ns + 1):
            cfg += f"{d}-SHWP{n}-RUNTIME = TIME-ON( {d}-SHWP{n}-STS ) / 3600\n"
        cfg += f"\nREM **** DP averaging ****\n"
        cfg += f"{d}-AVG-DP = ABS( {d}-HW-PRESS1 )\n"
    elif pt == 'vfd':
        npp = params.get('num_pumps', 2)
        cfg += "REM **** Pump runtime tracking ****\n"
        for n in range(1, npp + 1):
            cfg += f"{d}-HWP{n}-RUNTIME = TIME-ON( {d}-HWP{n}-STS ) / 3600\n"
        cfg += f"\nREM **** DP averaging ****\n"
        cfg += f"{d}-AVG-DP = ABS( ( {d}-HW-PRESS1 + {d}-HW-PRESS2 ) / 2 )\n"
    else:  # cs
        npp = params.get('num_pumps', 2)
        cfg += "REM **** Pump runtime tracking ****\n"
        for n in range(1, npp + 1):
            cfg += f"{d}-HWP{n}-RUNTIME = TIME-ON( {d}-HWP{n}-STS ) / 3600\n"

    cfg += f"\nREM **** System enable — OAT below threshold ****\n"
    cfg += f"A = SWITCH( A , {d}-NET-OAT , {d}-CFG-HHW-OA-ENAB-SP + 3 , {d}-CFG-HHW-OA-ENAB-SP )\n"
    cfg += f"IF A THEN STOP {d}-HW-SYS-ENAB ELSE START {d}-HW-SYS-ENAB\n"

    # Replace the core module's CONFIG program with dynamic code
    core_mod = modules[0]
    for prg in core_mod.programs:
        if prg.instance == 1:
            prg.code = cfg
            break

    # Generate dynamic BOILER-CTRL.bas for full control based on num_boilers
    if bt == 'full':
        _inject_dynamic_boiler_ctrl(modules, nb, d)

    # Generate dynamic ISO-VLV and COMB-DMPR code based on boiler type
    if params.get('iso_valves'):
        _inject_dynamic_iso_vlv(modules, nb, bt, d)
    if params.get('comb_damper'):
        _inject_dynamic_comb_dmpr(modules, nb, bt, d)

    # Generate dynamic pri-sec pump code based on counts
    if pt == 'pri-sec':
        npp = params.get('num_primary', 2)
        nps = params.get('num_secondary', 2)
        _inject_dynamic_phwp(modules, npp, d)
        if nps == 1:
            _inject_dynamic_shwp_single(modules, d)

    return modules


def _inject_dynamic_boiler_ctrl(modules, num_boilers, d):
    """Generate BOILER-CTRL.bas dynamically for num_boilers."""
    code = f"REM **** Boiler Staging Control — {num_boilers} boiler(s)\n"
    code += "REM **** Generated by SBS Composition Engine v2\n\n"

    # System off — stop all
    stops = " , ".join(f"STOP {d}-BLR{n}-S/S" for n in range(1, num_boilers + 1))
    mods = " , ".join(f"RELINQUISH {d}-BLR{n}-MOD" for n in range(1, num_boilers + 1))
    if num_boilers > 1:
        code += f"IF NOT {d}-HW-SYS-ENAB THEN {stops} , STOP {d}-LEAD-BLR-SS , STOP {d}-LAG-BLR-SS , {mods} , END\n\n"
    else:
        code += f"IF NOT {d}-HW-SYS-ENAB THEN {stops} , {mods} , END\n\n"

    # Per-boiler OOS check
    for n in range(1, num_boilers + 1):
        code += f"IF {d}-BLR{n}-OOS THEN STOP {d}-BLR{n}-S/S , {d}-BLR{n}-MOD = 0\n"
    code += "\n"

    if num_boilers == 1:
        # Single boiler — direct enable, no lead/lag
        code += f"REM **** Single boiler — direct enable ****\n"
        code += f"{d}-TOTAL-BLRS-REQUESTED = 0\n"
        code += f"IF {d}-ANY-HWP-ON AND NOT {d}-BLR1-ALARM AND NOT {d}-BLR1-OOS THEN START {d}-BLR1-S/S , {d}-TOTAL-BLRS-REQUESTED = 1 ELSE STOP {d}-BLR1-S/S\n"
        code += f"IF {d}-BLR1-ALARM AND {d}-BLR1-SS THEN START {d}-BLR1-FAIL ELSE STOP {d}-BLR1-FAIL\n"
        code += f"IF {d}-RESET-SAFETIES THEN STOP {d}-BLR1-FAIL\n"
    else:
        # Multi-boiler with lead/lag staging
        code += f"REM **** Deviation-based staging ****\n"
        code += f"{d}-LEAD-BLR-DEV = {d}-ACT-HWS-TEMP-SP - {d}-HWS-T\n"
        code += f"{d}-TOTAL-BLRS-REQUESTED = 0\n"
        code += f"A = SWITCH( A , {d}-LEAD-BLR-DEV , -5 , 5 )\n"
        code += f"IF A AND {d}-ANY-HWP-ON THEN START {d}-LEAD-BLR-SS ELSE STOP {d}-LEAD-BLR-SS\n"
        code += f"IF {d}-LEAD-BLR-SS THEN {d}-TOTAL-BLRS-REQUESTED = {d}-TOTAL-BLRS-REQUESTED + 1\n"
        code += f"B = SWITCH( B , {d}-LEAD-BLR-DEV , 5 , 15 )\n"
        code += f"IF B AND {d}-LEAD-BLR-SS THEN START {d}-LAG-BLR-SS ELSE STOP {d}-LAG-BLR-SS\n"
        code += f"IF {d}-LAG-BLR-SS THEN {d}-TOTAL-BLRS-REQUESTED = {d}-TOTAL-BLRS-REQUESTED + 1\n\n"
        code += f"REM **** Map lead/lag to physical boilers ****\n"
        for n in range(1, num_boilers + 1):
            code += f"IF {d}-LEAD-BLR = {n} THEN {d}-BLR{n}-SS = {d}-LEAD-BLR-SS\n"
            code += f"IF {d}-LEAD-BLR <> {n} THEN {d}-BLR{n}-SS = {d}-LAG-BLR-SS\n"
        code += "\n"
        code += f"REM **** Write S/S with alarm and OOS interlock ****\n"
        for n in range(1, num_boilers + 1):
            code += f"IF {d}-BLR{n}-SS AND NOT {d}-BLR{n}-ALARM AND NOT {d}-BLR{n}-OOS THEN START {d}-BLR{n}-S/S ELSE STOP {d}-BLR{n}-S/S\n"
        code += "\n"
        code += f"REM **** Failure detection ****\n"
        for n in range(1, num_boilers + 1):
            code += f"IF {d}-BLR{n}-ALARM AND {d}-BLR{n}-SS THEN START {d}-BLR{n}-FAIL ELSE STOP {d}-BLR{n}-FAIL\n"
        code += f"\nREM **** Lead boiler failure flag ****\n"
        for n in range(1, num_boilers + 1):
            code += f"IF {d}-LEAD-BLR = {n} THEN {d}-LEAD-BLR-FAIL = {d}-BLR{n}-FAIL\n"
        code += f"\nREM **** Reset ****\n"
        resets = " , ".join(f"STOP {d}-BLR{n}-FAIL" for n in range(1, num_boilers + 1))
        code += f"IF {d}-RESET-SAFETIES THEN {resets} , STOP {d}-LEAD-BLR-FAIL\n"

    # Find the BOILER-CTRL program in the boiler module and inject code
    for mod in modules:
        for prg in mod.programs:
            if prg.instance == 6 and 'BOILER-CTRL' in prg.name:
                prg.code = code
                return
            if prg.instance == 6 and 'CHLR' not in prg.name:
                prg.code = code
                return


def _inject_dynamic_phwp(modules, num_primary, d):
    """Generate PHWP .bas dynamically for the actual number of primary pumps.

    1 pump: direct start on system enable, no standby logic
    2 pumps: pump 1 runs, pump 2 is standby on failure
    """
    code = f"REM **** Primary Pump Control — {num_primary} pump(s)\n"
    code += "REM **** Generated by SBS Composition Engine v2\n\n"
    code += "REM **** Primary loop delta T ****\n"
    code += f"{d}-PRI-DELTA-T = {d}-PRI-HWS-T - {d}-PRI-HWR-T\n\n"

    if num_primary == 1:
        code += "REM **** Single primary pump — direct enable ****\n"
        code += f"IF {d}-HW-SYS-ENAB AND NOT {d}-PHWP1-FAIL THEN START {d}-PHWP1-S/S ELSE STOP {d}-PHWP1-S/S\n\n"
        code += "REM **** Failure proof ****\n"
        code += f"IF TIME-ON( {d}-PHWP1-S/S ) > 0:00:30 AND NOT {d}-PHWP1-STS THEN START {d}-PHWP1-FAIL\n"
        code += f"IF {d}-PHWP1-STS THEN STOP {d}-PHWP1-FAIL\n"
        code += f"IF {d}-RESET-SAFETIES THEN STOP {d}-PHWP1-FAIL\n"
    else:
        # Multi-pump: pump 1 runs, pump 2 is standby
        code += "REM **** Start primary pump 1 when system enabled ****\n"
        code += f"IF {d}-HW-SYS-ENAB AND NOT {d}-PHWP1-FAIL THEN START {d}-PHWP1-S/S ELSE STOP {d}-PHWP1-S/S\n\n"
        code += "REM **** Primary pump 1 failure proof ****\n"
        code += f"IF TIME-ON( {d}-PHWP1-S/S ) > 0:00:30 AND NOT {d}-PHWP1-STS THEN START {d}-PHWP1-FAIL\n"
        code += f"IF {d}-PHWP1-STS THEN STOP {d}-PHWP1-FAIL\n\n"
        for n in range(2, num_primary + 1):
            code += f"REM **** Standby — pump {n} starts on prior pump failure ****\n"
            fail_cond = " AND ".join(f"{d}-PHWP{k}-FAIL" for k in range(1, n))
            code += f"IF {d}-HW-SYS-ENAB AND {fail_cond} AND NOT {d}-PHWP{n}-FAIL THEN START {d}-PHWP{n}-S/S ELSE STOP {d}-PHWP{n}-S/S\n\n"
            code += f"REM **** Primary pump {n} failure proof ****\n"
            code += f"IF TIME-ON( {d}-PHWP{n}-S/S ) > 0:00:30 AND NOT {d}-PHWP{n}-STS THEN START {d}-PHWP{n}-FAIL\n"
            code += f"IF {d}-PHWP{n}-STS THEN STOP {d}-PHWP{n}-FAIL\n\n"
        code += "REM **** Reset failures ****\n"
        resets = " , ".join(f"STOP {d}-PHWP{n}-FAIL" for n in range(1, num_primary + 1))
        code += f"IF {d}-RESET-SAFETIES THEN {resets}\n"

    for mod in modules:
        for prg in mod.programs:
            if 'PHWP-PRG' in prg.name:
                prg.code = code
                return


def _inject_dynamic_shwp_single(modules, d):
    """Generate SHWP1 .bas for single secondary pump — no lead/lag refs."""
    code = "REM **** Secondary HW Pump 1 S/S program (single pump)\n"
    code += "REM **** Generated by SBS Composition Engine v2\n\n"
    code += f"IF SELECT( {d}-SHWP1-S/S ) <> 1 THEN START {d}-SHWP1-OOS ELSE STOP {d}-SHWP1-OOS\n"
    code += f"IF {d}-SHWP1-OOS THEN STOP {d}-SHWP1-S/S , END\n"
    code += f"IF {d}-SHWP1-FAIL THEN STOP {d}-SHWP1-S/S , END\n\n"
    code += f"IF {d}-HW-SYS-ENAB AND NOT {d}-SHWP1-OOS THEN START {d}-SHWP1-S/S ELSE STOP {d}-SHWP1-S/S\n\n"
    code += f"B = SWITCH( B , TIME-ON( {d}-SHWP1-S/S ) , 0 , {d}-HWP-STOP-DELAY )\n"
    code += f"IF B AND NOT {d}-SHWP1-STS THEN START {d}-SHWP1-FAIL\n"
    code += f"IF {d}-SHWP1-STS THEN STOP {d}-SHWP1-FAIL\n"
    code += f"IF {d}-RESET-SAFETIES THEN STOP {d}-SHWP1-FAIL\n"

    for mod in modules:
        for prg in mod.programs:
            if prg.name == 'HW-SHWP1-PRG':
                prg.code = code
                return


def _inject_dynamic_iso_vlv(modules, num_boilers, boiler_type, d):
    """Generate ISO-VLV .bas dynamically based on boiler type and count.

    Full control: check BLR{n}-SS (per-boiler start status BV)
    Cascade: check BLRS-ENABLE (system cascade enable BO)
    """
    code = f"REM **** Boiler Isolation Valve Control — {num_boilers} boiler(s), {boiler_type}\n"
    code += "REM **** Generated by SBS Composition Engine v2\n"
    code += "REM **** Open valve BEFORE boiler enable, close AFTER disable with delay\n\n"

    for n in range(1, num_boilers + 1):
        if boiler_type == 'full':
            trigger = f"{d}-BLR{n}-SS"
        else:
            # Cascade — all boilers share BLRS-ENABLE
            trigger = f"{d}-BLRS-ENABLE"

        code += f"REM **** Boiler {n} isolation valve ****\n"
        code += f"IF {trigger} THEN START {d}-BLR{n}-ISO-VLV\n"
        code += f"IF NOT {trigger} AND TIME-OFF( {trigger} ) > {d}-ISO-VLV-OPEN-DLY THEN STOP {d}-BLR{n}-ISO-VLV\n\n"

    for mod in modules:
        for prg in mod.programs:
            if 'ISO-VLV' in prg.name:
                prg.code = code
                return


def _inject_dynamic_comb_dmpr(modules, num_boilers, boiler_type, d):
    """Generate COMB-DMPR .bas dynamically based on boiler type and count.

    Full control: check BLR{n}-S/S (per-boiler start/stop BO)
    Cascade: check BLRS-ENABLE (system cascade enable BO)
    """
    code = f"REM **** Combustion Air Damper Interlock — {num_boilers} boiler(s), {boiler_type}\n"
    code += "REM **** Generated by SBS Composition Engine v2\n"
    code += "REM **** Alarm if any boiler firing and damper not confirmed open\n\n"
    code += f"STOP {d}-COMB-DMPR-ALARM\n"

    for n in range(1, num_boilers + 1):
        if boiler_type == 'full':
            trigger = f"{d}-BLR{n}-S/S"
        else:
            trigger = f"{d}-BLRS-ENABLE"

        code += f"IF {trigger} AND NOT {d}-BLR{n}-COMB-DMPR-STS THEN START {d}-COMB-DMPR-ALARM\n"

    for mod in modules:
        for prg in mod.programs:
            if 'COMB-DMPR' in prg.name:
                prg.code = code
                return


# ═══════════════════════════════════════════════════════════════════════════
# CHW Plant Dynamic Assembly
# ═══════════════════════════════════════════════════════════════════════════

def chwp_assemble(params):
    """Build CHW plant module list from wizard parameters.

    Args:
        params: dict with keys:
            num_chillers: 1-4
            num_pri_pumps: 1-4
            num_sec_pumps: 1-4
            num_dp_sensors: 1 or 2 (default 2)
            num_cw_pumps: 1-4 (tower only)
            num_towers: 1-4 (tower only)
            tower_bypass: bool (tower only)
            bypass_valve: bool
            iso_valves: bool
            makeup_water: bool
            ahu_integration: bool
            num_ahus: 1-8

    Returns:
        list of Module objects ready for assembly
    """
    modules = [chwp_build_core()]

    nc = params.get('num_chillers', 2)
    modules.append(chwp_build_chiller(num_chillers=nc))
    modules.append(chwp_build_pump_pri(num_pumps=params.get('num_pri_pumps', 2)))
    modules.append(chwp_build_pump_sec(
        num_pumps=params.get('num_sec_pumps', 2),
        num_dp_sensors=params.get('num_dp_sensors', 2)))

    # Tower-specific modules
    if params.get('num_cw_pumps'):
        modules.append(chwp_build_cdwp(num_pumps=params['num_cw_pumps']))
    if params.get('num_towers'):
        modules.append(chwp_build_tower(num_towers=params['num_towers']))
    if params.get('tower_bypass'):
        modules.append(chwp_build_tower_bypass())

    # Optional modules
    if params.get('bypass_valve'):
        modules.append(chwp_build_bypass_valve())
    if params.get('iso_valves'):
        has_cdw = bool(params.get('num_cw_pumps'))
        modules.append(chwp_build_iso_valves(num_chillers=nc, has_cdw_side=has_cdw))
    if params.get('ahu_integration'):
        modules.append(chwp_build_ahu_integration(num_ahus=params.get('num_ahus', 2)))
    if params.get('makeup_water'):
        modules.append(chwp_build_makeup_water())

    # Generate dynamic CHW CONFIG.bas based on pump counts and DP sensors
    d = "{device-name}"
    np = params.get('num_pri_pumps', 2)
    ns = params.get('num_sec_pumps', 2)
    ndp = params.get('num_dp_sensors', 2)
    cfg = "REM **** CHW Plant Configuration Program\n"
    cfg += "REM **** Generated by SBS Composition Engine v2 — CHW Plant\n\n"
    cfg += f"{d}-NET-OAT = {d}-OAT\n"
    cfg += f"{d}-NET-OAH = {d}-OAH\n"
    cfg += f"{d}-NET-OA-ERH = ENTHALPY( {d}-NET-OAT , {d}-NET-OAH , 1 )\n"
    cfg += f"{d}-CHW-DELTA-T = {d}-CHWR-T - {d}-CHWS-T\n\n"
    cfg += "REM **** Flow monitoring ****\n"
    cfg += f"IF {d}-CHW-FLOW > 0 THEN {d}-CHW-FLOW-TTL = {d}-CHW-FLOW-TTL + {d}-CHW-FLOW * INTERVAL / 60\n\n"
    cfg += "REM **** Primary pump runtime tracking ****\n"
    for n in range(1, np + 1):
        cfg += f"{d}-PCHWP{n}-RUNTIME = TIME-ON( {d}-PCHWP{n}-STS ) / 3600\n"
    cfg += "\nREM **** Secondary pump runtime tracking ****\n"
    for n in range(1, ns + 1):
        cfg += f"{d}-SCHWP{n}-RUNTIME = TIME-ON( {d}-SCHWP{n}-STS ) / 3600\n"
    cfg += "\nREM **** DP sensor averaging ****\n"
    if ndp >= 2:
        cfg += f"{d}-AVG-DP = ABS( ( {d}-CHW-PRESS1 + {d}-CHW-PRESS2 ) / 2 )\n"
    else:
        cfg += f"{d}-AVG-DP = ABS( {d}-CHW-PRESS1 )\n"

    # Inject into core module's CONFIG program
    core_mod = modules[0]
    for prg in core_mod.programs:
        if prg.instance == 1:
            prg.code = cfg
            break

    # Dynamic single-pump SCHWP1 code when only 1 secondary pump
    nsp = params.get('num_sec_pumps', 2)
    if nsp == 1:
        _inject_dynamic_chw_schwp1_single(modules, d)

    # Dynamic CDWP code when chiller count < CW pump count
    ncw = params.get('num_cw_pumps', 0)
    if nc == 1 and ncw and ncw > 1:
        _inject_dynamic_chw_cdwp_single_chiller(modules, ncw, d)
    if ncw and ncw >= 3 and nc < 3:
        _inject_dynamic_chw_cdwp3_standby(modules, nc, d)

    # Dynamic PCHWP3 standby when fewer than 3 chillers
    npp = params.get('num_pri_pumps', 2)
    if npp >= 3 and nc < 3:
        _inject_dynamic_chw_pchwp3_standby(modules, nc, d)

    return modules


def _inject_dynamic_chw_schwp1_single(modules, d):
    """Generate CHW-SCHWP1-PRG for single secondary pump — no lead/lag refs."""
    code = "REM **** Secondary CHW Pump 1 S/S Program (single pump)\n"
    code += "REM **** Generated by SBS Composition Engine v2 — CHW Plant\n\n"
    code += f"IF SELECT( {d}-SCHWP1-S/S ) <> 1 THEN START {d}-SCHWP1-OOS ELSE STOP {d}-SCHWP1-OOS\n"
    code += f"IF {d}-SCHWP1-OOS THEN STOP {d}-SCHWP1-S/S , END\n"
    code += f"IF {d}-SCHWP1-FAIL THEN STOP {d}-SCHWP1-S/S , END\n\n"
    code += f"IF {d}-CHW-SYS-ENAB AND NOT {d}-SCHWP1-OOS THEN START {d}-SCHWP1-S/S ELSE STOP {d}-SCHWP1-S/S\n\n"
    code += f"B = SWITCH( B , TIME-ON( {d}-SCHWP1-S/S ) , 0 , {d}-SCHWP-STOP-DELAY )\n"
    code += f"IF B AND NOT {d}-SCHWP1-STS THEN START {d}-SCHWP1-FAIL\n"
    code += f"IF {d}-SCHWP1-STS THEN STOP {d}-SCHWP1-FAIL\n"
    code += f"IF {d}-RESET-SAFETIES THEN STOP {d}-SCHWP1-FAIL\n"

    for mod in modules:
        for prg in mod.programs:
            if prg.name == 'CHW-SCHWP1-PRG':
                prg.code = code
                return


def _inject_dynamic_chw_cdwp_single_chiller(modules, num_cw_pumps, d):
    """Fix CDWP programs for single-chiller tower configs.

    CDWP2+ can't reference CHLR2-S/S when there's only 1 chiller.
    All CW pumps pair with the single chiller instead.
    CDWP-LEAD-LAG can't reference LEAD-CHLR when there's only 1 chiller.
    """
    for mod in modules:
        for prg in mod.programs:
            # Fix CDWP2 to pair with CHLR1 instead of CHLR2
            if prg.name == 'CHW-CDWP2-PRG':
                code = "REM **** CW Pump 2 S/S (single chiller — paired with CHLR1)\n"
                code += "REM **** Generated by SBS Composition Engine v2 — CHW Plant\n\n"
                code += f"IF SELECT( {d}-CDWP2-S/S ) <> 1 THEN START {d}-CDWP2-OOS ELSE STOP {d}-CDWP2-OOS\n"
                code += f"IF {d}-CDWP2-OOS THEN STOP {d}-CDWP2-S/S , END\n"
                code += f"IF {d}-CDWP2-FAIL THEN STOP {d}-CDWP2-S/S , END\n\n"
                code += f"IF {d}-CHLR1-S/S AND NOT {d}-CDWP2-OOS THEN START {d}-CDWP2-S/S ELSE STOP {d}-CDWP2-S/S\n\n"
                code += f"B = SWITCH( B , TIME-ON( {d}-CDWP2-S/S ) , 0 , {d}-CDWP-STOP-DELAY )\n"
                code += f"IF B AND NOT {d}-CDWP2-STS THEN START {d}-CDWP2-FAIL\n"
                code += f"IF {d}-CDWP2-STS THEN STOP {d}-CDWP2-FAIL\n"
                code += f"IF {d}-RESET-SAFETIES THEN STOP {d}-CDWP2-FAIL\n"
                prg.code = code

            # Fix CDWP-LEAD-LAG to not reference LEAD-CHLR
            if prg.name == 'CHW-CDWP-LEAD-LAG-PRG':
                code = f"REM **** CW Pump Lead/Lag (single chiller — {num_cw_pumps} CW pumps)\n"
                code += "REM **** Generated by SBS Composition Engine v2 — CHW Plant\n\n"
                code += "REM **** Failover on failure or OOS ****\n"
                for n in range(1, num_cw_pumps + 1):
                    nxt = (n % num_cw_pumps) + 1
                    code += f"IF {d}-LEAD-CDWP = {n} AND ({d}-CDWP{n}-FAIL OR {d}-CDWP{n}-OOS) THEN {d}-LEAD-CDWP = {nxt}\n"
                code += f"\n{d}-LEAD-CDWP = LIMIT( {d}-LEAD-CDWP , 1 , {num_cw_pumps} )\n\n"
                code += "REM **** Lead CW pump failure flag ****\n"
                for n in range(1, num_cw_pumps + 1):
                    code += f"IF {d}-LEAD-CDWP = {n} THEN {d}-LEAD-CDWP-FAIL = {d}-CDWP{n}-FAIL\n"
                code += "\nREM **** Any CW pump running ****\n"
                sts_list = " OR ".join(f"{d}-CDWP{n}-STS" for n in range(1, num_cw_pumps + 1))
                code += f"IF {sts_list} THEN START {d}-ANY-CDWP-ON ELSE STOP {d}-ANY-CDWP-ON\n"
                prg.code = code


def _inject_dynamic_chw_cdwp3_standby(modules, num_chillers, d):
    """Fix CDWP3 when fewer than 3 chillers — 3rd CW pump is pure standby.

    Can't pair with CHLR3-S/S when there are only 1-2 chillers.
    Starts on dual failure or when both other pumps are running and one fails.
    """
    for mod in modules:
        for prg in mod.programs:
            if prg.name == 'CHW-CDWP3-PRG':
                code = f"REM **** CW Pump 3 S/S (standby — {num_chillers} chiller(s), no CHLR3)\n"
                code += "REM **** Generated by SBS Composition Engine v2 — CHW Plant\n\n"
                code += f"IF SELECT( {d}-CDWP3-S/S ) <> 1 THEN START {d}-CDWP3-OOS ELSE STOP {d}-CDWP3-OOS\n"
                code += f"IF {d}-CDWP3-OOS THEN STOP {d}-CDWP3-S/S , END\n"
                code += f"IF {d}-CDWP3-FAIL THEN STOP {d}-CDWP3-S/S , END\n\n"
                code += "REM **** Start on dual failure of pumps 1+2 ****\n"
                code += f"IF {d}-CDWP1-FAIL AND {d}-CDWP2-FAIL AND NOT {d}-CDWP3-OOS THEN START {d}-CDWP3-S/S , END\n\n"
                code += "REM **** Start as failover when lead running and other pump failed ****\n"
                code += f"IF {d}-LEAD-CDWP-SS AND ({d}-CDWP1-FAIL OR {d}-CDWP2-FAIL) AND NOT {d}-CDWP3-OOS THEN START {d}-CDWP3-S/S , END\n\n"
                code += "REM **** Stop when both pumps 1+2 are healthy ****\n"
                code += f"IF NOT {d}-CDWP1-FAIL AND NOT {d}-CDWP2-FAIL THEN STOP {d}-CDWP3-S/S\n\n"
                code += f"B = SWITCH( B , TIME-ON( {d}-CDWP3-S/S ) , 0 , {d}-CDWP-STOP-DELAY )\n"
                code += f"IF B AND NOT {d}-CDWP3-STS THEN START {d}-CDWP3-FAIL\n"
                code += f"IF {d}-CDWP3-STS THEN STOP {d}-CDWP3-FAIL\n"
                code += f"IF {d}-RESET-SAFETIES THEN STOP {d}-CDWP3-FAIL\n"
                prg.code = code
                return


def _inject_dynamic_chw_pchwp3_standby(modules, num_chillers, d):
    """Fix PCHWP3 when fewer than 3 chillers — 3rd primary pump is pure standby."""
    for mod in modules:
        for prg in mod.programs:
            if prg.name == 'CHW-PCHWP3-PRG':
                code = f"REM **** Primary CHW Pump 3 S/S (standby — {num_chillers} chiller(s))\n"
                code += "REM **** Generated by SBS Composition Engine v2 — CHW Plant\n\n"
                code += f"IF SELECT( {d}-PCHWP3-S/S ) <> 1 THEN START {d}-PCHWP3-OOS ELSE STOP {d}-PCHWP3-OOS\n"
                code += f"IF {d}-PCHWP3-OOS THEN STOP {d}-PCHWP3-S/S , END\n"
                code += f"IF {d}-PCHWP3-FAIL THEN STOP {d}-PCHWP3-S/S , END\n\n"
                code += "REM **** Start on dual failure of pumps 1+2 ****\n"
                code += f"IF {d}-PCHWP1-FAIL AND {d}-PCHWP2-FAIL AND NOT {d}-PCHWP3-OOS THEN START {d}-PCHWP3-S/S , END\n\n"
                code += "REM **** Start as failover when lead running and other pump failed ****\n"
                code += f"IF {d}-LEAD-PCHWP-SS AND ({d}-PCHWP1-FAIL OR {d}-PCHWP2-FAIL) AND NOT {d}-PCHWP3-OOS THEN START {d}-PCHWP3-S/S , END\n\n"
                code += "REM **** Stop when both pumps 1+2 are healthy ****\n"
                code += f"IF NOT {d}-PCHWP1-FAIL AND NOT {d}-PCHWP2-FAIL THEN STOP {d}-PCHWP3-S/S\n\n"
                code += f"B = SWITCH( B , TIME-ON( {d}-PCHWP3-S/S ) , 0 , {d}-CHWP-STOP-DELAY )\n"
                code += f"IF B AND NOT {d}-PCHWP3-STS THEN START {d}-PCHWP3-FAIL\n"
                code += f"IF {d}-PCHWP3-STS THEN STOP {d}-PCHWP3-FAIL\n"
                code += f"IF {d}-RESET-SAFETIES THEN STOP {d}-PCHWP3-FAIL\n"
                prg.code = code
                return
