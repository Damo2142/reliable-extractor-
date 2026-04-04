# Composition Engine & Compiler — Standing Rules

## Code Path Tracing — Before Touching Composition Engine Code
Before modifying any composition engine code, trace the active code path from HTTP endpoint
to binary write. Prove the trace with grep, not assumption. If replacing a function or code
path, delete the dead code in the same commit as the replacement.

## RC Studio Verification Required
After any .pan binary fix, generate a test file to /srv/dfa/drops/ and report expected field
values. Do NOT declare a fix complete until Dave confirms in RC Studio. The 195-config audit
confirms structure only, not binary values — RC Studio is the only ground truth for binary
correctness.

## Dead Code Rule
When replacing a function, delete the old one in the same commit. No exceptions. Do not
leave commented-out code, renamed stubs, or "deprecated" wrappers. If it's replaced, it's
gone.

## Thinking Levels
- Standard fixes (point naming, UI tweaks): think normally
- Multi-system features (new equipment family, cross-module work): think hard
- Binary format / compiler changes (.pan structure, block encoding, CRC): think harder
- Loop and point property mappings (property IDs, value tags, field encoding): ultrathink
