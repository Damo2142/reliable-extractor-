"""
SBS Composition Engine v2 — CBAS Decompiler

Decompiles Reliable Controls CBAS bytecode back to .bas source code.
Reverse of cbas_compiler.py — every opcode the compiler writes,
we decode here.

Opcode reference (from cbas_compiler.py):
  Line:   01 [LE16 line_num] = code line start
  EndLn:  09 = end of code line
  REM:    1a [len] [ascii] = remark (length-prefixed)
  OldREM: 00 1a [ascii...] 02 = old-style remark

  ObjRef: c2 [inst] [type3B] = LOAD object value
          c3 [inst] [type3B] = STORE object value
  Const:  9d [4B LE float] = push float
  LocalV: 82 9a [slot] = LOAD local var (slot: A=2..Z=27)
  StoreV: a3 9a [slot] = STORE local var

  Ops:    6b=+ 6c=- 67=* 68=/ 65== 6d=> 6e=< 6f=>= 70=<= 71=<> 73=AND 74=OR 72=NOT

  Funcs:  33=ABS 37=MAX 38=MIN 3f=AVG 42=ENTHALPY 43=SLIDE 44=SWITCH
          45=RAMP 46=TIME-ON 47=TIME-OFF 4a=SCHED 4b=INTERVAL 4c=BIT-TEST
          5d=LIMIT da=SELECT d8=FLOAT
          Each followed by [argc] byte.

  Control: 75 [LE16 offset] = IF (jump if false)
           76 [LE16 offset] = ELSE/THEN jump
           0e [LE16 offset] = GOTO
           84 = STOP (preceded by c2 obj ref)
           85 = START (preceded by c2 obj ref)
           ff = END
           17 = END (statement)

  Special: 08 = SET-PRIORITY
           07 = RELINQUISH
           31 = IDLE
           51 = SENSOR-ON (after c3 ref)
           55 = SENSOR-OFF (after c3 ref)
"""

import struct

TYPE_DECODE = {
    b'\x00\x00\x00': 'AI',
    b'\x00\x00\x01': 'AO',
    b'\x00\x80\x00': 'AV',
    b'\x00\xc0\x00': 'BI',
    b'\x01\x00\x00': 'BO',
    b'\x00\x40\x01': 'BV',
    b'\x00\xc0\x04': 'MV',
    b'\x00\x80\x03': 'MO',
    b'\x00\x00\x03': 'LOOP',
    b'\x00\x40\x04': 'SCHED',
    b'\x00\x00\x04': 'PRG',
}

SLOT_TO_VAR = {i + 2: chr(ord('A') + i) for i in range(26)}

OP_DECODE = {
    0x6b: '+', 0x6c: '-', 0x67: '*', 0x68: '/',
    0x6d: '>', 0x6e: '<', 0x6f: '>=', 0x70: '<=',
    0x71: '<>', 0x65: '=', 0x73: 'AND', 0x74: 'OR', 0x72: 'NOT',
}

FUNC_DECODE = {
    0x33: 'ABS', 0x37: 'MAX', 0x38: 'MIN', 0x3f: 'AVG',
    0x42: 'ENTHALPY', 0x43: 'SLIDE', 0x44: 'SWITCH',
    0x45: 'RAMP', 0x46: 'TIME-ON', 0x47: 'TIME-OFF',
    0x4a: 'SCHED', 0x4b: 'INTERVAL', 0x4c: 'BIT-TEST',
    0x5d: 'LIMIT', 0xd8: 'FLOAT', 0xda: 'SELECT',
}


def _fmt_float(val):
    """Format a float value nicely."""
    if val == int(val) and abs(val) < 100000:
        return str(int(val))
    return f"{val:.6g}"


def _decode_time(seconds):
    """Convert seconds float to H:MM:SS format."""
    s = int(seconds)
    if s <= 0:
        return "0:00:00"
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"


def decompile(bytecode: bytes) -> str:
    """Decompile CBAS bytecode to .bas source."""
    lines = []
    bc = bytecode
    n = len(bc)
    i = 0

    while i < n:
        # Look for line start: 0x01 [LE16 line_num]
        if bc[i] != 0x01:
            i += 1
            continue

        if i + 2 >= n:
            break

        line_num = bc[i + 1] | (bc[i + 2] << 8)
        if line_num < 1 or line_num > 9999:
            i += 1
            continue
        i += 3

        # Check for REM: length-prefixed (1a [len] [text])
        if i < n and bc[i] == 0x1a:
            i += 1
            if i < n:
                rem_len = bc[i]
                i += 1
                text = bc[i:i + rem_len].decode('cp1252', errors='replace')
                i += rem_len
                lines.append(f"{line_num} REM {text}")
                continue

        # Check for old-style REM: 00 1a [text...] 02
        if i + 1 < n and bc[i] == 0x00 and bc[i + 1] == 0x1a:
            i += 2
            start = i
            while i < n and bc[i] != 0x02:
                i += 1
            text = bc[start:i].decode('cp1252', errors='replace')
            if i < n:
                i += 1
            lines.append(f"{line_num} REM {text}")
            continue

        # Code line — decode until 0x09 (end of line) or next 0x01
        parts = []
        stack = []
        store_target = None
        had_if = False
        then_parts = []
        else_parts = []
        in_else = False
        gotos = []

        while i < n and bc[i] != 0x09:
            b = bc[i]

            # STORE object ref: c3 [inst] [type3B]
            if b == 0xc3 and i + 4 < n:
                inst = bc[i + 1]
                tb = bytes(bc[i + 2:i + 5])
                tn = TYPE_DECODE.get(tb, f'??({tb.hex()})')
                ref = f"{tn}{inst}"
                # Check if next byte is START/STOP/SENSOR
                if i + 5 < n and bc[i + 5] == 0x84:
                    parts.append(f"STOP {ref}")
                    i += 6
                    continue
                elif i + 5 < n and bc[i + 5] == 0x85:
                    parts.append(f"START {ref}")
                    i += 6
                    continue
                elif i + 5 < n and bc[i + 5] == 0x51:
                    stack.append(f"SENSOR-ON({ref})")
                    i += 6
                    continue
                elif i + 5 < n and bc[i + 5] == 0x55:
                    stack.append(f"SENSOR-OFF({ref})")
                    i += 6
                    continue
                else:
                    store_target = ref
                    i += 5
                    continue

            # LOAD object ref: c2 [inst] [type3B]
            if b == 0xc2 and i + 4 < n:
                inst = bc[i + 1]
                tb = bytes(bc[i + 2:i + 5])
                tn = TYPE_DECODE.get(tb, f'??({tb.hex()})')
                stack.append(f"{tn}{inst}")
                i += 5
                continue

            # Float constant: 9d [4B LE float]
            if b == 0x9d and i + 4 < n:
                val = struct.unpack_from('<f', bc, i + 1)[0]
                # Check if it looks like a time value (> 60 and round)
                if val >= 30 and val == int(val) and val % 30 == 0 and val <= 86400:
                    stack.append(_decode_time(val))
                else:
                    stack.append(_fmt_float(val))
                i += 5
                continue

            # STORE local var: a3 9a [slot]
            if b == 0xa3 and i + 2 < n and bc[i + 1] == 0x9a:
                slot = bc[i + 2]
                store_target = SLOT_TO_VAR.get(slot, f'VAR{slot}')
                i += 3
                continue

            # LOAD local var: 82 9a [slot]
            if b == 0x82 and i + 2 < n and bc[i + 1] == 0x9a:
                slot = bc[i + 2]
                stack.append(SLOT_TO_VAR.get(slot, f'VAR{slot}'))
                i += 3
                continue

            # Binary/unary operators
            if b in OP_DECODE:
                op = OP_DECODE[b]
                if op == 'NOT':
                    if stack:
                        val = stack.pop()
                        stack.append(f"NOT {val}")
                elif len(stack) >= 2:
                    right = stack.pop()
                    left = stack.pop()
                    stack.append(f"{left} {op} {right}")
                i += 1
                continue

            # Functions: [opcode] [argc]
            if b in FUNC_DECODE and i + 1 < n:
                fn = FUNC_DECODE[b]
                argc = bc[i + 1]
                args = []
                for _ in range(min(argc, len(stack))):
                    args.insert(0, stack.pop())
                stack.append(f"{fn}( {', '.join(args)} )")
                i += 2
                continue

            # IF: 75 [LE16 offset]
            if b == 0x75 and i + 2 < n:
                offset = bc[i + 1] | (bc[i + 2] << 8)
                had_if = True
                # The condition is on the stack
                i += 3
                continue

            # THEN/ELSE jump: 76 [LE16 offset]
            if b == 0x76 and i + 2 < n:
                offset = bc[i + 1] | (bc[i + 2] << 8)
                in_else = True
                i += 3
                continue

            # GOTO: 0e [LE16 offset]
            if b == 0x0e and i + 2 < n:
                target_off = bc[i + 1] | (bc[i + 2] << 8)
                parts.append(f"GOTO {target_off}")
                i += 3
                continue

            # STOP (standalone, target already on stack or preceding c3)
            if b == 0x84:
                if stack:
                    ref = stack.pop()
                    parts.append(f"STOP {ref}")
                else:
                    parts.append("STOP")
                i += 1
                continue

            # START (standalone)
            if b == 0x85:
                if stack:
                    ref = stack.pop()
                    parts.append(f"START {ref}")
                else:
                    parts.append("START")
                i += 1
                continue

            # END statement
            if b == 0xff:
                parts.append("END")
                i += 1
                continue

            if b == 0x17:
                parts.append("END")
                i += 1
                continue

            # SET-PRIORITY
            if b == 0x08:
                i += 1
                continue

            # RELINQUISH
            if b == 0x07:
                if stack:
                    ref = stack.pop()
                    parts.append(f"RELINQUISH {ref}")
                i += 1
                continue

            # IDLE
            if b == 0x31:
                if stack:
                    ref = stack.pop()
                    parts.append(f"IDLE {ref}")
                i += 1
                continue

            # Unknown — skip
            i += 1

        # Skip end-of-line marker
        if i < n and bc[i] == 0x09:
            i += 1

        # Build the line
        line_str = ""

        if had_if and stack:
            cond = stack.pop()
            line_str = f"IF {cond} THEN "

        if store_target and stack:
            expr = stack[-1] if stack else "?"
            stack.pop()
            if had_if:
                line_str += f"{store_target} = {expr}"
            else:
                line_str = f"{store_target} = {expr}"
        elif store_target:
            if had_if:
                line_str += f"{store_target} = ?"
            else:
                line_str = f"{store_target} = ?"

        # Add any remaining stack items
        if stack:
            remaining = ', '.join(stack)
            if line_str:
                line_str += f" , {remaining}"
            else:
                line_str = remaining

        # Add statement parts (START, STOP, GOTO, END)
        if parts:
            stmt = ' , '.join(parts)
            if line_str:
                line_str += f" , {stmt}"
            else:
                line_str = stmt

        if line_str:
            lines.append(f"{line_num} {line_str}")

    return '\n'.join(lines)
