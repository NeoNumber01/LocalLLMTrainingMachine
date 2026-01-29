#!/usr/bin/env python3
"""Debug script to test eval.py test generation logic."""

import json
import sys
from io import StringIO

# Mock solution code (correct solution)
code = '''n = int(input())
cn5 = n * (n - 1) // 2 * (n - 2) // 3 * (n - 3) // 4 * (n - 4) // 5
an5 = n * (n - 1) * (n - 2) * (n - 3) * (n - 4)
print(cn5 * an5)'''

# Test from the dataset
test_str = '{"type": "stdin_stdout", "fn_name": "", "input": "5\\n", "expected_output": "120"}'
test = json.loads(test_str)
inp = test['input']
exp = test['expected_output']

print("=== Test Input ===")
print(f"inp: {repr(inp)}")
print(f"exp: {repr(exp)}")
print(f"code: {repr(code[:100])}")
print()

# This simulates _convert_stdin_test_enhanced
idx = 0
if inp and not inp.endswith('\n'):
    inp += '\n'

test_code = f'''
# Test {idx}
import sys
from io import StringIO
_i{idx}={repr(inp)}
_e{idx}={repr(str(exp))}
_si{idx},_so{idx}=sys.stdin,sys.stdout
try:
    sys.stdin=StringIO(_i{idx})
    _c{idx}=StringIO()
    sys.stdout=_c{idx}
    exec({repr(code)},{{}})
finally:
    sys.stdout,sys.stdin=_so{idx},_si{idx}
_o{idx}=_c{idx}.getvalue()
def _n{idx}(s):return'\\n'.join(l.rstrip()for l in str(s).strip().replace('\\r\\n','\\n').split('\\n'))
print(f"Output: {{repr(_o{idx})}}", file=_so{idx})
print(f"Expected: {{repr(_e{idx})}}", file=_so{idx})
assert _n{idx}(_o{idx})==_n{idx}(_e{idx}),f"Test {idx} failed: got {{repr(_o{idx}[:100])}} expected {{repr(_e{idx}[:100])}}"
print("Test PASSED!", file=_so{idx})
'''

print("=== Generated Test Code ===")
print(test_code)
print()
print("=== Running Test ===")

try:
    exec(test_code)
except AssertionError as e:
    print(f"AssertionError: {e}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
