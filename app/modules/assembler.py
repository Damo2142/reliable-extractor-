"""
SBS Controls — Module Assembler

Takes a base equipment type and list of feature codes, resolves dependencies
and conflicts, merges BACnet objects, stitches Control-BASIC code blocks in
execution order, counts I/O, and recommends a controller model.

Usage:
    from app.modules.assembler import assemble

    result = assemble(
        equipment_type="AHU-VAV",
        features=["CHW", "HW", "ECON-DB", "SF-VFD", "FLTR-DP", "SMOKE-FIRE", "FREEZE", "DSP"],
        device_name="AHU-1",
    )
    print(result["point_list"])
    print(result["controller"])
    print(result["code"])
"""

import copy
from typing import Dict, List, Optional, Tuple

from app.modules import get_base, get_module, get_modules_for_feature, _MODULE_REGISTRY
from app.modules.controller_selector import select_controller


class AssemblyError(Exception):
    """Raised when module assembly fails (conflicts, missing deps, etc.)."""
    pass


def assemble(
    equipment_type: str,
    features: List[str],
    device_name: str = "{device-name}",
    equipment_category: str = "ahu",
    prefer_family: Optional[str] = None,
) -> dict:
    """
    Assemble a complete controller configuration from base + feature modules.

    Args:
        equipment_type: Base equipment type code (e.g., "AHU-VAV")
        features: List of feature codes to include (e.g., ["CHW", "HW", "ECON-DB"])
        device_name: Equipment tag for name substitution (default keeps template)
        equipment_category: Category for controller selection preference
        prefer_family: Override controller family preference

    Returns:
        dict with keys:
            - modules: list of loaded module dicts
            - objects: merged object dict by type
            - point_list: flat list of all points with type info
            - io_map: merged I/O terminal map
            - io_counts: dict with num_ai, num_ao, num_di, num_do
            - controller: SelectionResult from controller selector
            - code: assembled Control-BASIC code (all blocks in exec_order)
            - warnings: list of warning messages
            - errors: list of error messages (empty if successful)
    """
    warnings = []
    errors = []

    # ── 1. Load base module ──────────────────────────────────────────────────
    base = get_base(equipment_type)
    if base is None:
        raise AssemblyError(
            f"Unknown equipment type: '{equipment_type}'. "
            f"Available: {', '.join(_get_available_bases())}"
        )

    modules = [copy.deepcopy(base)]

    # ── 2. Load feature modules ──────────────────────────────────────────────
    for feature_code in features:
        feature_modules = get_modules_for_feature(feature_code)
        if not feature_modules:
            # Try direct module ID lookup
            mod = get_module(feature_code)
            if mod:
                feature_modules = [mod]
            else:
                warnings.append(
                    f"Feature '{feature_code}' not found — skipped"
                )
                continue

        for mod in feature_modules:
            modules.append(copy.deepcopy(mod))

    # ── 3. Check conflicts ───────────────────────────────────────────────────
    module_ids = {m["id"] for m in modules}
    for mod in modules:
        for conflict_id in mod.get("conflicts", []):
            if conflict_id in module_ids:
                errors.append(
                    f"CONFLICT: Module '{mod['id']}' conflicts with "
                    f"'{conflict_id}' — both are selected"
                )

    if errors:
        raise AssemblyError(
            "Module conflicts detected:\n" + "\n".join(errors)
        )

    # ── 4. Resolve dependencies ──────────────────────────────────────────────
    max_iterations = 10
    for _ in range(max_iterations):
        all_ids = {m["id"] for m in modules}
        new_deps = []
        for mod in modules:
            for req_id in mod.get("requires", []):
                if req_id not in all_ids:
                    dep_mod = get_module(req_id)
                    if dep_mod:
                        new_deps.append(copy.deepcopy(dep_mod))
                        warnings.append(
                            f"Auto-added dependency '{req_id}' "
                            f"(required by '{mod['id']}')"
                        )
                    else:
                        errors.append(
                            f"MISSING DEPENDENCY: Module '{mod['id']}' requires "
                            f"'{req_id}' which is not registered"
                        )

        if not new_deps:
            break
        modules.extend(new_deps)

    if errors:
        raise AssemblyError(
            "Dependency errors:\n" + "\n".join(errors)
        )

    # ── 5. Sort by exec_order ────────────────────────────────────────────────
    modules.sort(key=lambda m: m["exec_order"])

    # ── 6. Merge objects (dedup by name) ─────────────────────────────────────
    merged_objects: Dict[str, list] = {}
    seen_names = set()

    for mod in modules:
        for obj_type, obj_list in mod.get("objects", {}).items():
            if obj_type not in merged_objects:
                merged_objects[obj_type] = []
            for obj in obj_list:
                obj_name = obj["name"]
                if obj_name not in seen_names:
                    seen_names.add(obj_name)
                    merged_objects[obj_type].append(obj)
                else:
                    # Deduplicate: skip if same name already exists
                    pass

    # ── 7. Build flat point list ─────────────────────────────────────────────
    point_list = []
    for obj_type in ["AI", "AO", "AV", "BI", "BO", "BV", "MO", "MV", "LOOP", "SCHEDULE"]:
        for obj in merged_objects.get(obj_type, []):
            point_list.append({
                "type": obj_type,
                "name": obj["name"],
                "desc": obj.get("desc", ""),
                "units": obj.get("units", "no-units"),
                "min": obj.get("min"),
                "max": obj.get("max"),
                "states": obj.get("states"),
                "default": obj.get("default"),
                "source_module": _find_source_module(obj["name"], modules),
            })

    # ── 8. Merge I/O maps ────────────────────────────────────────────────────
    io_map = {}
    for mod in modules:
        for terminal, point_name in mod.get("io_map", {}).items():
            if terminal in io_map and io_map[terminal] != point_name:
                warnings.append(
                    f"I/O map conflict on terminal '{terminal}': "
                    f"'{io_map[terminal]}' vs '{point_name}' "
                    f"(using '{point_name}' from module '{mod['id']}')"
                )
            io_map[terminal] = point_name

    # ── 9. Count I/O ─────────────────────────────────────────────────────────
    io_counts = _count_io(merged_objects)

    # ── 10. Select controller ────────────────────────────────────────────────
    controller_result = select_controller(
        num_ai=io_counts["num_ai"],
        num_ao=io_counts["num_ao"],
        num_di=io_counts["num_di"],
        num_do=io_counts["num_do"],
        equipment_category=equipment_category,
        prefer_family=prefer_family,
    )

    # ── 11. Assemble code ────────────────────────────────────────────────────
    code_blocks = []
    for mod in modules:
        code = mod.get("code", "").strip()
        if code:
            code_blocks.append(code)

    assembled_code = "\n\n".join(code_blocks)

    # ── 12. Apply device name substitution ───────────────────────────────────
    if device_name != "{device-name}":
        assembled_code = assembled_code.replace("{device-name}", device_name)
        for pt in point_list:
            pt["name"] = pt["name"].replace("{device-name}", device_name)
        io_map = {k: v.replace("{device-name}", device_name) for k, v in io_map.items()}
        for obj_type in merged_objects:
            for obj in merged_objects[obj_type]:
                obj["name"] = obj["name"].replace("{device-name}", device_name)

    return {
        "equipment_type": equipment_type,
        "device_name": device_name,
        "modules": [{"id": m["id"], "name": m["name"], "exec_order": m["exec_order"],
                     "code": m.get("code", "").strip(),
                     "objects": {k: [{"name": o["name"], "desc": o.get("desc","")} for o in v] for k, v in m.get("objects", {}).items() if v},
                     } for m in modules],
        "objects": merged_objects,
        "point_list": point_list,
        "io_map": io_map,
        "io_counts": io_counts,
        "controller": controller_result,
        "code": assembled_code,
        "warnings": warnings,
        "errors": errors,
    }


def _count_io(objects: Dict[str, list]) -> dict:
    """Count physical I/O requirements from merged objects."""
    num_ai = len(objects.get("AI", []))
    num_ao = len(objects.get("AO", []))
    num_di = len(objects.get("BI", []))
    num_do = len(objects.get("BO", []))

    # AV, BV, MV, MO are internal software points — no physical I/O
    num_av = len(objects.get("AV", []))
    num_bv = len(objects.get("BV", []))

    return {
        "num_ai": num_ai,
        "num_ao": num_ao,
        "num_di": num_di,
        "num_do": num_do,
        "total_physical": num_ai + num_ao + num_di + num_do,
        "num_av": num_av,
        "num_bv": num_bv,
        "total_software": num_av + num_bv,
        "total_points": num_ai + num_ao + num_di + num_do + num_av + num_bv,
    }


def _find_source_module(point_name: str, modules: list) -> str:
    """Find which module originally defined a point."""
    for mod in modules:
        for obj_list in mod.get("objects", {}).values():
            for obj in obj_list:
                if obj["name"] == point_name:
                    return mod["id"]
    return "unknown"


def _get_available_bases() -> list:
    """Get list of registered base equipment types."""
    from app.modules import list_bases
    return list_bases()


def print_assembly_report(result: dict) -> None:
    """Print a formatted assembly report to stdout."""
    print("=" * 72)
    print(f"  SBS CONTROLS — MODULAR ASSEMBLY REPORT")
    print(f"  Equipment: {result['equipment_type']}  |  "
          f"Device: {result['device_name']}")
    print("=" * 72)

    # Modules loaded
    print(f"\n── Modules Loaded ({len(result['modules'])}) ──")
    for mod in result["modules"]:
        print(f"  [{mod['exec_order']:2d}] {mod['id']:30s} {mod['name']}")

    # Point list
    print(f"\n── Point List ({len(result['point_list'])} points) ──")
    print(f"  {'Type':<6} {'Name':<35} {'Units':<12} {'Description'}")
    print(f"  {'─'*6} {'─'*35} {'─'*12} {'─'*30}")
    for pt in result["point_list"]:
        print(
            f"  {pt['type']:<6} {pt['name']:<35} "
            f"{pt['units']:<12} {pt['desc']}"
        )

    # I/O counts
    counts = result["io_counts"]
    print(f"\n── I/O Summary ──")
    print(f"  Analog Inputs  (AI): {counts['num_ai']}")
    print(f"  Analog Outputs (AO): {counts['num_ao']}")
    print(f"  Binary Inputs  (DI): {counts['num_di']}")
    print(f"  Binary Outputs (DO): {counts['num_do']}")
    print(f"  ─────────────────────")
    print(f"  Physical I/O Total:  {counts['total_physical']}")
    print(f"  Software Points:     {counts['total_software']} "
          f"(AV={counts['num_av']}, BV={counts['num_bv']})")
    print(f"  Grand Total:         {counts['total_points']}")

    # I/O Map
    if result["io_map"]:
        print(f"\n── I/O Terminal Map ──")
        for terminal, point in sorted(result["io_map"].items()):
            print(f"  {terminal:<8} → {point}")

    # Controller recommendation
    print(f"\n── Controller Recommendation ──")
    print(f"  {result['controller'].summary()}")

    # Assembled code
    print(f"\n── Assembled Control-BASIC Code ──")
    print("─" * 72)
    print(result["code"])
    print("─" * 72)

    # Warnings
    if result["warnings"]:
        print(f"\n── Warnings ({len(result['warnings'])}) ──")
        for w in result["warnings"]:
            print(f"  ⚠ {w}")

    print()
