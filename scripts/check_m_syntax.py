"""Check all generated TMDL files for M if/else balance."""
import re
import os
import sys

def check_m_if_else(text):
    """Count if/else outside M string literals."""
    stripped = re.sub(r'"([^"]|"")*"', '""', text)
    ifs = len(re.findall(r'\bif\b', stripped))
    elses = len(re.findall(r'\belse\b', stripped))
    return ifs, elses

errors = []
base = sys.argv[1] if len(sys.argv) > 1 else 'artifacts'
for root, dirs, files in os.walk(base):
    for f in files:
        if not f.endswith('.tmdl'):
            continue
        path = os.path.join(root, f)
        with open(path, 'r', encoding='utf-8') as fh:
            content = fh.read()
        parts = re.split(r'partition\s', content)
        for idx, part in enumerate(parts[1:], 1):
            if '= m' in part[:100]:
                ifs, elses = check_m_if_else(part)
                if ifs != elses:
                    short = os.path.relpath(path, base)
                    errors.append(f'{short} (partition {idx}): if={ifs}, else={elses}')

if errors:
    print('ERRORS FOUND:')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)
else:
    print('OK: all M partition expressions have balanced if/else')
