# UV Freeze Protection Refactor — Handoff

## STATE
- **Branch**: feature/binary-pan-parser
- **Status**: Code changes committed, nothing pushed
- **Gate**: Jerome's RC Studio hardware validation required before proceeding
- **Service**: Restarts required after code changes (Dave's authorization)

## COMMITS TODAY (in order)

| Hash | Message |
|------|---------|
| 6e12591 | PART 1: Rename OAT freeze path to clarify non-safety purpose |
| 5fb4759 | PART 2: Cabinet protection reset with OAT-based linear interpolation |
| a7d067c | PART 2 CORRECTIONS: Safety interlock hardening |
| 909bdbf | FIX: Detect duplicate program instances within same module |
| bfe936b | FIX: Reassign PRG02B-CAB-PROT-RESET to unique instance 11 |

## CORE DEFECT BEING FIXED

**The Real Problem:**
PRG09-FREEZESTAT / BV76 FREEZE-TRIP is the hardware safety interlock. It currently drives NOTHING.

**Today's State (before fix):**
- All consumers (FAN-CTRL, HTG-OUTPUT, FBP-CTRL) key off BV15 UNOCC-OAT-LOW
- UNOCC-OAT-LOW is the unoccupied OAT low limit, NOT a safety interlock
- A real freezestat trip (BI6 FREEZE-STAT = 0) does not:
  - Stop the fan
  - Open the valve
  - Close the damper
- It only alarms (BV79 FREEZE-ALARM = latch status)

**The 11-Part Fix:**
Rewire all outputs to respond to the real freezestat (FREEZE-TRIP), not the OAT flag.

## COMPLETED THIS SESSION

✓ **Part 1**: Renamed OAT path to clarify non-safety purpose
  - PRG03-FREEZE-PROTECT → PRG03-UNOCC-OAT-LIMIT
  - BV15 FREEZE-PROT → BV15 UNOCC-OAT-LOW
  - CFG-UV-FREEZE-OAT (AV40) → CFG-UNOCC-OAT-LIM
  - Removed CFG-UV-FREEZE-VLV (AV41)

✓ **Part 2**: Cabinet protection reset with OAT-based linear interpolation
  - Added 5 new points: CFG-CAB-OAT-HI/LO, CFG-CAB-VLV-MIN/MAX, CAB-PROT-VLV
  - PRG02B-CAB-PROT-RESET: explicit linear interpolation (not SLIDE to avoid ambiguity)
  - HTG-OUTPUT uses CAB-PROT-VLV when UNOCC-OAT-LOW is active

✓ **Assembler Fix**: Duplicate program instance validation
  - Detects when two programs in the SAME module share an instance number
  - Raises ValueError with clear message (silent drops are now loud)
  - Allows cross-module duplicates (intentional variant selection)

✓ **UV Family Fix**: Reassigned instance number
  - PRG02B-CAB-PROT-RESET: instance 2 → instance 11 (was duplicate, still collides cross-module)

## PENDING VERIFICATION

- **Part 2 generated output**: After service restart, regenerate both configs and confirm PRG02B appears in output
- **Parts 3–11**: Not yet started

## NOT STARTED

- Part 3: Fix the OAT path (guard OAD on Config A, delete fan shutdown from UNOCC-OAT-LOW)
- Part 4: Normalize freezestat polarity (CFG-FSTAT-NC)
- Part 5: Wire safety interlock to outputs
- Part 6: Execution order fix
- Part 7: Rolling lockout with trip counting
- Part 8: Fix reset defeat (FREEZE-RST self-clearing)
- Part 9: DAT low-limit backstop gating
- Part 10: Add alarming for latched condition
- Part 11: Full verification

## FULL 11-PART TASK TEXT (as specified for Parts 1-11)

Reference /srv/reliable-generator-dev/.claude/HANDOFF-11-PARTS.txt for complete unmodified task statement.

**Key revision for steam paths (to implement in Part 5):**
- Add CFG-CAB-STM-POS (AV, default 20.0%) for steam cabinet protection position
- Steam-mod WITH F&B (PRG05_STEAM_ONOFF_FBP): valve 100 and FBP-CTRL modulates off HTG-DAT-LOOP
- Steam-mod WITHOUT F&B (PRG05_STEAM_MOD): use CFG-CAB-STM-POS (OAT-based reset curve is HW-only)
- Steam on/off without F&B: full open, no change
- OAT reset curve (PRG02B-CAB-PROT-RESET) applies to HW only, not steam

## SETTLED DESIGN DECISIONS

- **CFG-FSTAT-NC** (BV): default TRUE → raw 0 = alarm (normally closed), raw 1 = healthy
- **Freezestat normalization**: Decode BI6 FREEZE-STAT + CFG-FSTAT-NC → FSTAT-TRIP (BV), read only that
- **Trip counting**: Rolling 60-minute window, 3 trips per window, count FSTAT-TRIP rising edges (not FREEZE-TRIP)
- **Reset behavior**: FREEZE-RST self-clears after consumed; does not clear if FSTAT-TRIP still 1
- **Safety outputs on FREEZE-TRIP = 1**:
  - Fan OFF (FAN-CMD = 0)
  - HW valve to CFG-FSTAT-VLV (default 100%)
  - OAD closed (if present)
  - F&B full face (if present)

## OPEN ITEMS / KNOWN ISSUES

1. **CAB-PROT-VLV high-end clamp**: Writes CFG-CAB-VLV-MIN instead of 0 on OAT >= CFG-CAB-OAT-HI
   - Unreachable with defaults (CFG-CAB-OAT-HI = 35°F, CFG-UNOCC-OAT-LIM = 35°F, mutually exclusive)
   - Reachable if technician sets CFG-CAB-OAT-HI < CFG-UNOCC-OAT-LIM
   - Decision: leave as CFG-CAB-VLV-MIN (allows trickle in warm unoccupied) or change to 0 (full close)?
   - Not yet decided — flagged for review

2. **Divide-by-zero guard**: PRG02B line asserts guard via REM, not code
   - Condition `ACT-OAT > CFG-CAB-OAT-LO AND ACT-OAT < CFG-CAB-OAT-HI` prevents division
   - Verified logically, not in compiled output — cannot confirm until Part 2 regenerated

3. **Cross-module duplicates**: Instance 11 now collides with STAT-PRG (vav/stat_hardwired.py)
   - Assembler silently drops one variant (by design for module selection)
   - Must reassign PRG02B-CAB-PROT-RESET to instance 15 or 18 (globally available)
   - Not yet fixed — flagged for next session

## STANDING RULES FOR THIS WORK

- **Verification only in regenerated output** — never from source inspection
- **Service restart required** after every code change; Dave must authorize
- **One part at a time** — never consolidate multiple parts
- **No floats in exec_order** — Python sort is stable but implicit on tie (DAT-RESET and CAB-PROT-RESET both exec_order=2)
- **No pushing to remote** — hold until Jerome validates in RC Studio
- **Assembly validator**: Duplicate same-module instances now raise error (was silent before)

## NEXT SESSION — FIRST TASK

1. Restart composition-engine service (if not already restarted)
2. Regenerate both configs (A: HW+FBP+freezestat, B: HW+OAD+freezestat)
3. Verify Part 2 output from freshly generated .bas files
4. If verified: proceed to Part 3
5. If verification fails: stop and diagnose

## QUEUED FOR LATER SESSIONS

**Parallel audit needed** (same defect, different families):
- FCU family: Has the same freezestat wiring issue (shares UV heritage)
  - BI2 FREEZE-STAT, SF-STS on BI1, HTG-OUTPUT at instance 5
  - Instance 5 collision: both fcu.py and uv.py define instance 5 for different purposes
  - Also uses BV15 UNOCC-OAT-LOW (OAT flag) instead of safety interlock
- Blower Coil: Likely same pattern (if it exists)

**Platform-level work** (not specific to this branch):
- Cross-module duplicate instance handling needs explicit variant marker on ProgramDef
- Current dedup silently drops duplicates from different modules (by design for variants)
- Should have a way to mark "this is a variant of instance X" vs "this is a unique program with instance X by accident"
- Silent drops make debugging hard when the "wrong" variant gets selected

---

**End of day. Branch gated on Jerome. Next session: restart, regenerate, verify Part 2, then Part 3.**
