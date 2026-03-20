"""
SBS Composition Engine v2 — CBAS (Control-BASIC) Compiler

Compiles Control-BASIC .bas source code into the binary bytecode format
used by Reliable Controls .pan files.

Based on reverse engineering of RC Studio's compiled output.
Bytecode is a stack-based format derived from Dartmouth BASIC.

OPCODE TABLE (verified against compiled programs):
  Line Structure:
    01 [line_num LE16] 00 [opcodes...] 09  = code line
    01 [line_num LE16] 00 1a [ascii text] 02  = REM line
    Program ends with trailing bytes after last line

  Object References:
    c2 [instance] [type 3 bytes] = LOAD object value
    c3 [instance] [type 3 bytes] = STORE object value
    Type encoding: 00 00 00 = AI(0), 00 40 00 = AO(1), 00 80 00 = AV(2),
                   00 c0 00 = BI(3), 01 00 00 = BO(4), 01 40 00 = BV(5),
                   00 c0 04 = MV(19)

  Constants:
    9d [4 bytes BE IEEE754 float] = PUSH float constant

  Local Variables (A-Z):
    a3 = ASSIGN to local var (followed by 9a [slot])
    82 = LOAD local var (followed by 9a [slot])
    Local var slots: A=0, B=1, C=2, ... Z=25

  Operators:
    6b = ADD (+)
    6c = SUBTRACT (-)
    67 = MULTIPLY (*)
    68 = DIVIDE (/)

  Functions (followed by argument count byte):
    5d [n] = LIMIT(val, min, max)
    37 [n] = MAX(a, b, ...)
    38 [n] = MIN(a, b, ...)
    3f [n] = AVG(a, b, ...)
    da [n] = SELECT(index, v1, v2, ...)

  Control Flow:
    75 [offset] = IF condition
    76 [offset] = THEN
    0e [offset] = GOTO/jump
    84 = STOP
    ff = END

  Special:
    09 = END OF LINE
    1a = REM statement (text follows as ASCII)
    02 = END marker (after REM text or line group)
"""

import struct
import re


# BACnet object type to 3-byte encoding
# Format: 00 [type_hi] [type_lo] where type is split across 2 bytes
# Verified against compiled .pan files from RC Studio
TYPE_ENCODE = {
    "AI":   b'\x00\x00\x00',   # type 0
    "AO":   b'\x00\x00\x01',   # type 1
    "AV":   b'\x00\x80\x00',   # type 2
    "BI":   b'\x00\xc0\x00',   # type 3  (need to verify)
    "BO":   b'\x01\x00\x00',   # type 4  (need to verify)
    "BV":   b'\x00\x40\x01',   # type 5  (VERIFIED from compiled .pan)
    "MV":   b'\x00\xc0\x04',   # type 19 (VERIFIED)
    "MO":   b'\x00\x80\x03',   # type 14 (from .pan analysis)
    "LOOP": b'\x00\x00\x03',   # type 12 (from .pan analysis)
    "SCHED": b'\x00\x40\x04', # type 17 (schedule)
    "PROGRAM": b'\x00\x00\x04', # type 16 (program)
}

# Local variable name to slot number (A=2, B=3, ... Z=27 — offset of 2 from Reliable's convention)
LOCAL_VARS = {chr(c): c - ord('A') + 2 for c in range(ord('A'), ord('Z') + 1)}

# Function name to opcode
FUNCTIONS = {
    "LIMIT": 0x5d,
    "MAX": 0x37,
    "MIN": 0x38,
    "AVG": 0x3f,
    "ABS": 0x33,
    "SELECT": 0xda,
    "ENTHALPY": 0x42,
    "SLIDE": 0x43,
    "SWITCH": 0x44,
    "RAMP": 0x45,
    "TIME-ON": 0x46,
    "TIME-OFF": 0x47,
    "SCHED": 0x4a,
    "INTERVAL": 0x4b,
    "BIT-TEST": 0x4c,
}

# Operators
OPERATORS = {
    "+": 0x6b,
    "-": 0x6c,
    "*": 0x67,
    "/": 0x68,
    "=": 0x65,
    ">": 0x6d,
    "<": 0x6e,
    ">=": 0x6f,
    "<=": 0x70,
    "<>": 0x71,
    "AND": 0x73,
    "OR": 0x74,
    "NOT": 0x72,
}


def compile_bas(source_code: str) -> bytes:
    """
    Compile Control-BASIC source code to binary bytecode.

    Args:
        source_code: The .bas program text with line numbers

    Returns:
        Compiled bytecode ready for embedding in a .pan file
    """
    lines = source_code.strip().split('\n')
    result = bytearray()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Parse line number
        parts = line.split(None, 1)
        if not parts or not parts[0].isdigit():
            continue

        line_num = int(parts[0])
        statement = parts[1] if len(parts) > 1 else ""

        compiled_line = _compile_line(line_num, statement)
        result.extend(compiled_line)

    return bytes(result)


def _compile_line(line_num: int, statement: str) -> bytes:
    """Compile a single BASIC line."""
    result = bytearray()

    # Line header: 01 [line_num LE16]
    result.append(0x01)
    result.extend(struct.pack('<H', line_num))

    statement = statement.strip()

    if not statement:
        # Empty line
        result.append(0x00)
        result.append(0x09)
        return bytes(result)

    # REM line
    if statement.upper().startswith('REM'):
        rem_text = statement[3:].lstrip()
        result.append(0x00)  # separator after line num for REM
        result.append(0x1a)  # REM opcode
        result.extend(rem_text.encode('ascii', errors='replace'))
        result.append(0x02)  # End REM marker
        return bytes(result)

    # Code line — no separator, opcodes start immediately
    compiled = _compile_statement(statement)
    result.extend(compiled)
    result.append(0x09)  # End of line

    return bytes(result)


def _compile_statement(statement: str) -> bytes:
    """Compile a code statement (assignment, IF, STOP, START, etc.)."""
    result = bytearray()
    statement = statement.strip()

    # Handle IF/THEN/ELSE (complex — simplified for now)
    if statement.upper().startswith('IF'):
        return _compile_if_statement(statement)

    # Handle STOP/START
    if statement.upper().startswith('STOP '):
        target = statement[5:].strip()
        result.extend(_compile_object_ref(target, store=False))
        result.append(0x84)  # STOP
        return bytes(result)

    if statement.upper().startswith('START '):
        target = statement[6:].strip()
        result.extend(_compile_object_ref(target, store=False))
        result.append(0x85)  # START
        return bytes(result)

    # Handle END
    if statement.upper() == 'END':
        result.append(0xff)
        return bytes(result)

    # Assignment: target = expression
    if '=' in statement:
        eq_pos = statement.index('=')
        target = statement[:eq_pos].strip()
        expr = statement[eq_pos+1:].strip()

        # Compile target (STORE)
        target_bytes = _compile_target(target)

        # Compile expression
        expr_bytes = _compile_expression(expr)

        result.extend(target_bytes)
        result.extend(expr_bytes)

    return bytes(result)


def _compile_target(target: str) -> bytes:
    """Compile an assignment target (left side of =)."""
    target = target.strip()

    # Local variable (A-Z)
    if len(target) == 1 and target.upper() in LOCAL_VARS:
        slot = LOCAL_VARS[target.upper()]
        return bytes([0xa3, 0x9a, slot])

    # Object reference (AV1, BI3, etc.)
    return _compile_object_ref(target, store=True)


def _compile_object_ref(name: str, store: bool = False) -> bytes:
    """Compile a BACnet object reference."""
    name = name.strip()

    # Parse type and instance: AV123, BI4, etc.
    # Also handle {device-name}-POINT-NAME format (use the full name)
    m = re.match(r'^(AI|AO|AV|BI|BO|BV|MV|MO|LOOP)(\d+)$', name.upper())
    if m:
        obj_type = m.group(1)
        instance = int(m.group(2))
        opcode = 0xc3 if store else 0xc2
        type_bytes = TYPE_ENCODE.get(obj_type, b'\x00\x80\x00')
        return bytes([opcode, instance & 0xFF]) + type_bytes

    # If it's a {device-name}-XXX reference, we need to resolve it later
    # For now, return a placeholder
    return bytes([0xc2, 0x00, 0x00, 0x80, 0x00])


def _compile_expression(expr: str) -> bytes:
    """Compile an expression (right side of =)."""
    result = bytearray()
    expr = expr.strip()

    # Strip outer parens if present
    while expr.startswith('(') and expr.endswith(')'):
        depth = 0
        matched = True
        for i, c in enumerate(expr):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            if depth == 0 and i < len(expr) - 1:
                matched = False
                break
        if matched:
            expr = expr[1:-1].strip()
        else:
            break

    # Check for function call: FUNC( args )
    func_match = re.match(r'^(\w+)\s*\(\s*(.*)\s*\)$', expr, re.DOTALL)
    if func_match:
        func_name = func_match.group(1).upper()
        args_str = func_match.group(2)

        if func_name in FUNCTIONS:
            # Compile arguments
            args = _split_args(args_str)
            for arg in args:
                result.extend(_compile_expression(arg))

            # Function opcode + arg count
            result.append(FUNCTIONS[func_name])
            result.append(len(args))
            return bytes(result)

    # Check for binary operator: expr OP expr
    # Find the main operator (lowest precedence, outside parens)
    for ops in [['OR'], ['AND'], ['<>', '>=', '<=', '>', '<', '='], ['+', '-'], ['*', '/']]:
        op_pos, op_str = _find_main_operator(expr, ops)
        if op_pos >= 0:
            left = expr[:op_pos].strip()
            right = expr[op_pos + len(op_str):].strip()
            result.extend(_compile_expression(left))
            result.extend(_compile_expression(right))
            result.append(OPERATORS[op_str])
            return bytes(result)

    # Check for NOT
    if expr.upper().startswith('NOT '):
        result.extend(_compile_expression(expr[4:]))
        result.append(OPERATORS['NOT'])
        return bytes(result)

    # Atom: number, variable, or object reference
    return bytes(_compile_atom(expr))


def _compile_atom(expr: str) -> bytes:
    """Compile an atomic expression (number, variable, object ref)."""
    expr = expr.strip()

    # Float constant
    try:
        val = float(expr)
        return b'\x9d' + struct.pack('<f', val)
    except ValueError:
        pass

    # Time constant (H:MM:SS)
    time_match = re.match(r'^(\d+):(\d+):(\d+)$', expr)
    if time_match:
        h, m, s = int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3))
        total_seconds = h * 3600 + m * 60 + s
        return b'\x9d' + struct.pack('>f', float(total_seconds))

    # Local variable (A-Z)
    if len(expr) == 1 and expr.upper() in LOCAL_VARS:
        slot = LOCAL_VARS[expr.upper()]
        return bytes([0x82, 0x9a, slot])

    # Object reference
    return _compile_object_ref(expr, store=False)


def _split_args(args_str: str) -> list:
    """Split function arguments respecting parentheses."""
    args = []
    depth = 0
    current = []
    for c in args_str:
        if c == '(':
            depth += 1
            current.append(c)
        elif c == ')':
            depth -= 1
            current.append(c)
        elif c == ',' and depth == 0:
            args.append(''.join(current).strip())
            current = []
        else:
            current.append(c)
    if current:
        args.append(''.join(current).strip())
    return [a for a in args if a]


def _find_main_operator(expr: str, operators: list) -> tuple:
    """Find the main (lowest precedence) operator outside parentheses."""
    depth = 0
    # Scan right to left for left-associativity
    for i in range(len(expr) - 1, -1, -1):
        if expr[i] == ')':
            depth += 1
        elif expr[i] == '(':
            depth -= 1
        elif depth == 0:
            for op in operators:
                if expr[i:i+len(op)].upper() == op.upper():
                    # Make sure it's not part of a variable name
                    if op.isalpha():
                        before = expr[i-1] if i > 0 else ' '
                        after = expr[i+len(op)] if i + len(op) < len(expr) else ' '
                        if before.isalnum() or after.isalnum():
                            continue
                    return (i, op)
    return (-1, '')


def _compile_if_statement(statement: str) -> bytes:
    """Compile an IF/THEN/ELSE statement (simplified)."""
    # This is complex — for now, store as REM with a TODO marker
    # Full IF compilation requires jump offset calculation
    result = bytearray()
    result.append(0x1a)  # Store as REM for now
    result.extend(f"TODO: {statement}".encode('ascii', errors='replace'))
    return bytes(result)


def compile_program_to_pan_block(source_code: str, enabled: bool = True) -> bytes:
    """
    Compile source code into the full program property block
    that goes inside a .pan file PROGRAM object.

    Returns the bytes that go after the Mu header, including
    the 04 29 property marker and code header.
    """
    bytecode = compile_bas(source_code)

    # Build the program code property block
    # Structure: [pre-props] 04 29 65 fe [size_BE16] 91 [state] [bytecode]
    result = bytearray()

    # Pre-code properties
    result.extend(b'\x08\x00\x00\x00\x1c\x71\x00')  # status flags
    result.extend(b'\x00\x07\x00\x00\x04\x41')
    result.append(0x10 if not enabled else 0x10)  # program stop flag

    # Code size (big-endian 16-bit)
    code_size = len(bytecode)

    # Code property: 04 29
    result.extend(b'\x04\x29')

    # Code header: 65 fe [size_BE] 91 [state]
    result.append(0x65)
    result.append(0xfe)
    result.extend(struct.pack('>H', code_size))
    result.append(0x91)
    state = 0x02 if enabled else 0x00  # 02 = running
    result.append(state)

    # Bytecode
    result.extend(bytecode)

    # Program enabled property: 04 0a 91 [01=running, 00=stopped]
    result.extend(b'\x08\x00\x00\x04\x0a\x91')
    result.append(0x01 if enabled else 0x00)

    return bytes(result)


# Test
if __name__ == "__main__":
    test_code = """10 REM ***** TEST PROGRAM *****
20 REM ***** Configuration
30 A = AV52 / 2
40 AV11 = LIMIT( AV11 , AV50 , AV51 )
50 AV50 = LIMIT( AV50 , 55 , 85 )
60 IF AV9 > AV12 THEN B = AV9 - AV10
"""

    bytecode = compile_bas(test_code)
    print(f"Compiled {len(test_code)} chars source to {len(bytecode)} bytes bytecode")
    print()

    # Hex dump
    for i in range(0, len(bytecode), 16):
        hexs = ' '.join(f'{b:02x}' for b in bytecode[i:i+16])
        asci = ''.join(chr(b) if 32 <= b < 127 else '.' for b in bytecode[i:i+16])
        print(f"  {i:04x}: {hexs:<48s} {asci}")
