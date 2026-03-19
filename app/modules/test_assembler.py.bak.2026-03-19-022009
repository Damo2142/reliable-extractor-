#!/usr/bin/env python3
"""
SBS Controls — Modular Composition Engine Test

Tests the complete assembly pipeline:
    1. Load AHU-VAV base module
    2. Add all standard AHU features
    3. Run assembler with conflict/dependency checks
    4. Print: point list, I/O map, controller recommendation, assembled code
    5. Validate: no conflicts, all dependencies met, controller fits

Usage:
    cd /srv/reliable-generator-dev
    PYTHONPATH=/srv/reliable-generator-dev python -m app.modules.test_assembler
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.modules.assembler import assemble, print_assembly_report, AssemblyError
from app.modules import list_modules, list_bases


def test_full_ahu_vav():
    """Test: Full AHU-VAV with all standard features."""
    print("\n" + "=" * 72)
    print("  TEST 1: Full AHU-VAV Assembly")
    print("=" * 72)

    features = [
        "CHW",          # Chilled water cooling
        "HW",           # Hot water heating
        "ECON-DB",      # Dry bulb economizer
        "SF-VFD",       # VFD supply fan
        "FLTR-DP",      # Filter DP monitor
        "SMOKE-FIRE",   # Smoke & fire safety
        "FREEZE",       # Freeze protection
        "DSP",          # Duct static pressure
    ]

    result = assemble(
        equipment_type="AHU-VAV",
        features=features,
        device_name="AHU-1",
        equipment_category="ahu",
    )

    print_assembly_report(result)

    # ── Validation ───────────────────────────────────────────────────────
    print("\n── Validation Results ──")
    passed = 0
    failed = 0

    def check(condition, description):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        if condition:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {description}")

    # Check all modules loaded
    check(
        len(result["modules"]) == 9,
        f"All 9 modules loaded (got {len(result['modules'])})"
    )

    # Check module list includes base and all features
    mod_ids = [m["id"] for m in result["modules"]]
    check("base_ahu_vav" in mod_ids, "Base AHU-VAV module present")
    check("mod_chw_cooling" in mod_ids, "CHW cooling module present")
    check("mod_hw_heating" in mod_ids, "HW heating module present")
    check("mod_economizer_db" in mod_ids, "Economizer module present")
    check("mod_vfd_supply_fan" in mod_ids, "VFD supply fan module present")
    check("mod_freeze_protect" in mod_ids, "Freeze protection module present")
    check("mod_smoke_fire" in mod_ids, "Smoke/fire module present")
    check("mod_filter_dp" in mod_ids, "Filter DP module present")
    check("mod_static_pressure" in mod_ids, "Static pressure module present")

    # Check no errors
    check(len(result["errors"]) == 0, f"No errors (got {len(result['errors'])})")

    # Check point list has points
    check(
        len(result["point_list"]) > 20,
        f"Point list has {len(result['point_list'])} points (expected >20)"
    )

    # Check I/O counts
    counts = result["io_counts"]
    check(counts["num_ai"] > 0, f"Has analog inputs ({counts['num_ai']})")
    check(counts["num_ao"] > 0, f"Has analog outputs ({counts['num_ao']})")
    check(counts["num_di"] > 0, f"Has digital inputs ({counts['num_di']})")
    check(counts["num_do"] > 0, f"Has digital outputs ({counts['num_do']})")

    # Check controller was selected
    check(
        result["controller"].fits,
        f"Controller fits: {result['controller'].controller.id}"
    )

    # Check code is non-empty
    check(len(result["code"]) > 500, f"Code generated ({len(result['code'])} chars)")

    # Check device name substitution worked
    point_names = [p["name"] for p in result["point_list"]]
    check(
        all("AHU-1-" in n for n in point_names),
        "Device name substitution applied to all points"
    )
    check(
        "{device-name}" not in result["code"],
        "No un-substituted {device-name} templates in code"
    )

    # Check I/O map has entries
    check(
        len(result["io_map"]) > 5,
        f"I/O map has {len(result['io_map'])} entries"
    )

    # Check exec_order sorting
    orders = [m["exec_order"] for m in result["modules"]]
    check(
        orders == sorted(orders),
        f"Modules sorted by exec_order: {orders}"
    )

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_conflict_detection():
    """Test: Conflicting modules should raise error."""
    print("\n" + "=" * 72)
    print("  TEST 2: Conflict Detection")
    print("=" * 72)

    # Register a fake constant-speed fan module that conflicts with VFD
    from app.modules import register_module
    try:
        fake_cs = {
            "id": "mod_cs_supply_fan",
            "name": "Constant Speed Supply Fan (test)",
            "feature": "SF-CS",
            "category": "fan",
            "requires": [],
            "conflicts": ["mod_vfd_supply_fan"],
            "exec_order": 30,
            "objects": {"BO": [{"name": "{device-name}-SF-CMD2", "desc": "test"}]},
            "io_map": {},
            "code": "REM test",
        }
        register_module(fake_cs)
    except ValueError:
        pass  # Already registered from previous run

    try:
        assemble(
            equipment_type="AHU-VAV",
            features=["SF-VFD", "SF-CS"],
        )
        print("  [FAIL] Expected AssemblyError for conflicting modules")
        return False
    except AssemblyError as e:
        print(f"  [PASS] Correctly detected conflict: {e}")
        return True


def test_dependency_resolution():
    """Test: DSP module should auto-add VFD dependency."""
    print("\n" + "=" * 72)
    print("  TEST 3: Dependency Resolution")
    print("=" * 72)

    result = assemble(
        equipment_type="AHU-VAV",
        features=["DSP"],  # Requires mod_vfd_supply_fan
    )

    mod_ids = [m["id"] for m in result["modules"]]
    has_vfd = "mod_vfd_supply_fan" in mod_ids
    has_dep_warning = any("Auto-added" in w for w in result["warnings"])

    print(f"  [{'PASS' if has_vfd else 'FAIL'}] VFD module auto-added: {has_vfd}")
    print(f"  [{'PASS' if has_dep_warning else 'FAIL'}] Dependency warning generated: {has_dep_warning}")

    if result["warnings"]:
        for w in result["warnings"]:
            print(f"    Warning: {w}")

    return has_vfd and has_dep_warning


def test_controller_selection():
    """Test: Controller selection for different I/O configs."""
    print("\n" + "=" * 72)
    print("  TEST 4: Controller Selection")
    print("=" * 72)

    from app.modules.controller_selector import select_controller

    tests = [
        # (ai, ao, di, do, category, expected_family)
        (2, 1, 0, 1, "vav", "rcfa"),
        (3, 4, 6, 4, "ahu", "mpa"),
        (8, 6, 4, 6, "plant", "mp2"),
        (1, 0, 0, 1, "terminal", "rcfa"),
    ]

    all_pass = True
    for ai, ao, di, do_, cat, expected_fam in tests:
        result = select_controller(ai, ao, di, do_, cat)
        match = result.controller.family == expected_fam
        status = "PASS" if match else "FAIL"
        if not match:
            all_pass = False
        print(
            f"  [{status}] AI={ai} AO={ao} DI={di} DO={do_} ({cat}) "
            f"-> {result.controller.id} (family={result.controller.family}, "
            f"expected={expected_fam})"
        )

    return all_pass


def test_template_mode():
    """Test: Assembly with template placeholder preserved."""
    print("\n" + "=" * 72)
    print("  TEST 5: Template Mode (no device name substitution)")
    print("=" * 72)

    result = assemble(
        equipment_type="AHU-VAV",
        features=["CHW", "HW"],
        device_name="{device-name}",  # Keep template
    )

    point_names = [p["name"] for p in result["point_list"]]
    all_templated = all("{device-name}" in n for n in point_names)

    print(f"  [{'PASS' if all_templated else 'FAIL'}] All points use template placeholder")
    print(f"  Sample points: {point_names[:5]}")
    return all_templated


def test_registry():
    """Test: Module registry functions."""
    print("\n" + "=" * 72)
    print("  TEST 6: Module Registry")
    print("=" * 72)

    bases = list_bases()
    modules = list_modules()

    print(f"  Registered base types: {bases}")
    print(f"  Registered feature modules: {len(modules)}")
    for mod in modules:
        print(f"    - {mod['id']:30s} [{mod['category']:12s}] {mod['name']}")

    has_base = "AHU-VAV" in bases
    has_modules = len(modules) >= 8

    print(f"  [{'PASS' if has_base else 'FAIL'}] AHU-VAV base registered")
    print(f"  [{'PASS' if has_modules else 'FAIL'}] At least 8 feature modules registered ({len(modules)})")

    return has_base and has_modules


def _run_assembly_test(test_name, equipment_type, features, device_name,
                       equipment_category, expected_min_points, expected_modules,
                       expected_base_id):
    """Generic assembly test helper. Returns True if all checks pass."""
    print("\n" + "=" * 72)
    print(f"  {test_name}")
    print("=" * 72)

    result = assemble(
        equipment_type=equipment_type,
        features=features,
        device_name=device_name,
        equipment_category=equipment_category,
    )

    print_assembly_report(result)

    passed = 0
    failed = 0

    def check(condition, description):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        if condition:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {description}")

    mod_ids = [m["id"] for m in result["modules"]]
    check(expected_base_id in mod_ids,
          f"Base module '{expected_base_id}' present")

    check(len(result["modules"]) == expected_modules,
          f"Expected {expected_modules} modules loaded (got {len(result['modules'])})")

    check(len(result["errors"]) == 0,
          f"No errors (got {len(result['errors'])})")

    check(len(result["point_list"]) >= expected_min_points,
          f"Point list has {len(result['point_list'])} points (expected >={expected_min_points})")

    check(result["controller"].fits,
          f"Controller fits: {result['controller'].controller.id}")

    check(len(result["code"]) > 100,
          f"Code generated ({len(result['code'])} chars)")

    point_names = [p["name"] for p in result["point_list"]]
    check(all(device_name + "-" in n for n in point_names),
          f"Device name '{device_name}' substituted in all points")

    orders = [m["exec_order"] for m in result["modules"]]
    check(orders == sorted(orders),
          f"Modules sorted by exec_order: {orders}")

    if result["warnings"]:
        for w in result["warnings"]:
            print(f"  Warning: {w}")

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_vav_hw_reheat():
    """Test: VAV terminal with HW reheat."""
    return _run_assembly_test(
        test_name="TEST 7: VAV Terminal with HW Reheat",
        equipment_type="VAV",
        features=["RH-HW"],
        device_name="VAV-1-01",
        equipment_category="vav",
        expected_min_points=12,
        expected_modules=2,
        expected_base_id="base_vav_terminal",
    )


def test_vav_elec_reheat():
    """Test: VAV terminal with electric reheat."""
    return _run_assembly_test(
        test_name="TEST 8: VAV Terminal with Electric Reheat",
        equipment_type="VAV",
        features=["RH-ELEC"],
        device_name="VAV-2-01",
        equipment_category="vav",
        expected_min_points=12,
        expected_modules=2,
        expected_base_id="base_vav_terminal",
    )


def test_ahu_cv_chw_hw_econ():
    """Test: AHU-CV with CHW + HW + economizer."""
    return _run_assembly_test(
        test_name="TEST 9: AHU-CV with CHW + HW + Economizer",
        equipment_type="AHU-CV",
        features=["CHW", "HW", "ECON-DB"],
        device_name="AHU-3",
        equipment_category="ahu",
        expected_min_points=15,
        expected_modules=4,
        expected_base_id="base_ahu_cv",
    )


def test_rtu_vav_dx_gas():
    """Test: RTU-VAV with DX cooling + gas heat."""
    return _run_assembly_test(
        test_name="TEST 10: RTU-VAV with DX Cooling + Gas Heat",
        equipment_type="RTU-VAV",
        features=["DX-1", "GAS-1", "ECON-DB"],
        device_name="RTU-1",
        equipment_category="rtu",
        expected_min_points=12,
        expected_modules=4,
        expected_base_id="base_rtu_vav",
    )


def test_fcu_4pipe():
    """Test: FCU 4-pipe (cooling + HW heating)."""
    return _run_assembly_test(
        test_name="TEST 11: FCU 4-Pipe (CHW + HW)",
        equipment_type="FCU",
        features=["HW-FCU"],
        device_name="FCU-1",
        equipment_category="fcu",
        expected_min_points=8,
        expected_modules=2,
        expected_base_id="base_fcu",
    )


def test_exhaust_fan():
    """Test: Simple exhaust fan."""
    return _run_assembly_test(
        test_name="TEST 12: Exhaust Fan - Simple",
        equipment_type="EF",
        features=[],
        device_name="EF-1",
        equipment_category="generic",
        expected_min_points=4,
        expected_modules=1,
        expected_base_id="base_exhaust_fan",
    )


def test_unit_heater():
    """Test: Unit heater."""
    return _run_assembly_test(
        test_name="TEST 13: Unit Heater",
        equipment_type="UH",
        features=[],
        device_name="UH-1",
        equipment_category="terminal",
        expected_min_points=4,
        expected_modules=1,
        expected_base_id="base_unit_heater",
    )


def test_wshp_base():
    """Test: Water Source Heat Pump base module."""
    return _run_assembly_test(
        test_name="TEST 14: Water Source Heat Pump (Base)",
        equipment_type="WSHP",
        features=[],
        device_name="WSHP-1",
        equipment_category="terminal",
        expected_min_points=10,
        expected_modules=1,
        expected_base_id="base_wshp",
    )


def test_doas_chw_hw_erw():
    """Test: DOAS with CHW + HW + Energy Recovery Wheel."""
    return _run_assembly_test(
        test_name="TEST 15: DOAS + CHW + HW + ERW",
        equipment_type="DOAS",
        features=["CHW", "HW", "ERW"],
        device_name="DOAS-1",
        equipment_category="ahu",
        expected_min_points=10,
        expected_modules=4,
        expected_base_id="base_doas",
    )


def test_rtu_cv_dx_gas_econ():
    """Test: RTU-CV with DX cooling + gas heat + economizer."""
    return _run_assembly_test(
        test_name="TEST 16: RTU-CV + DX-1 + GAS-1 + Economizer",
        equipment_type="RTU-CV",
        features=["DX-1", "GAS-1", "ECON-DB"],
        device_name="RTU-2",
        equipment_category="rtu",
        expected_min_points=12,
        expected_modules=4,
        expected_base_id="base_rtu_cv",
    )


def main():
    """Run all tests."""
    print("\n" + "#" * 72)
    print("  SBS CONTROLS — MODULAR COMPOSITION ENGINE TEST SUITE")
    print("#" * 72)

    results = []

    results.append(("Registry", test_registry()))
    results.append(("Full AHU-VAV Assembly", test_full_ahu_vav()))
    results.append(("Conflict Detection", test_conflict_detection()))
    results.append(("Dependency Resolution", test_dependency_resolution()))
    results.append(("Controller Selection", test_controller_selection()))
    results.append(("Template Mode", test_template_mode()))
    results.append(("VAV + HW Reheat", test_vav_hw_reheat()))
    results.append(("VAV + Electric Reheat", test_vav_elec_reheat()))
    results.append(("AHU-CV + CHW + HW + Econ", test_ahu_cv_chw_hw_econ()))
    results.append(("RTU-VAV + DX + Gas Heat", test_rtu_vav_dx_gas()))
    results.append(("FCU 4-Pipe", test_fcu_4pipe()))
    results.append(("Exhaust Fan Simple", test_exhaust_fan()))
    results.append(("Unit Heater", test_unit_heater()))
    results.append(("WSHP Base", test_wshp_base()))
    results.append(("DOAS + CHW + HW + ERW", test_doas_chw_hw_erw()))
    results.append(("RTU-CV + DX + Gas + Econ", test_rtu_cv_dx_gas_econ()))

    print("\n" + "=" * 72)
    print("  FINAL RESULTS")
    print("=" * 72)
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")

    print(f"\n  Overall: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    print("=" * 72)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
