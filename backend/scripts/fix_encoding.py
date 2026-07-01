import re
content = open('backend/scripts/collect_runtime_evidence.py', 'r', encoding='utf-8').read()
replacements = {
    '\u2500': '-',
    '\u2014': '-',
    '\u2013': '-',
    '\u26A0': '[WARN]',
    '\u2705': '[OK]',
    '\u201c': '"',
    '\u201d': '"',
}
for old, new in replacements.items():
    content = content.replace(old, new)
with open('backend/scripts/collect_runtime_evidence.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
