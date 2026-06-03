import os
import sys

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
issues = []

for dirpath, dirnames, filenames in os.walk(root):
    # skip __pycache__
    if '__pycache__' in dirpath:
        continue
    for fname in filenames:
        if not fname.endswith('.py'):
            continue
        path = os.path.join(dirpath, fname)
        rel = os.path.relpath(path, root)
        # ignore this checker script itself to avoid self-reporting
        if rel.replace('\\','/') .endswith('scripts/check_indentation.py'):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            issues.append((rel, f'ERROR reading file: {e}'))
            continue

        uses_tabs = False
        space_indents = set()
        line_infos = []
        for i, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            # skip shebang or encoding declarations
            if i <= 2 and (line.startswith('#!') or 'coding' in line):
                continue
            leading = 0
            for ch in line:
                if ch == ' ':
                    leading += 1
                elif ch == '\t':
                    uses_tabs = True
                    break
                else:
                    break
            else:
                # line only spaces? skip
                continue
            if uses_tabs:
                # mark tab usage but continue to collect
                pass
            if leading > 0:
                space_indents.add(leading)
                line_infos.append((i, leading, line.rstrip('\n')))

        file_issues = []
        if uses_tabs and space_indents:
            file_issues.append('Mixed tabs and spaces')
        if space_indents:
            # check if all indents are multiples of 4
            non_mult4 = [s for s in space_indents if s % 4 != 0]
            if non_mult4:
                file_issues.append(f'Indent widths not multiple of 4: {sorted(list(non_mult4))}')
            # check for many different indent sizes
            if len(space_indents) > 4:
                file_issues.append(f'Many different indent sizes used: {sorted(list(space_indents))}')

        if file_issues:
            issues.append((rel, file_issues, line_infos[:10]))

if not issues:
    print('No indentation issues found.')
    sys.exit(0)

for item in issues:
    if len(item) == 2:
        rel, msg = item
        print(f'{rel}: {msg}')
    else:
        rel, file_issues, examples = item
        print(f'File: {rel}')
        for fi in file_issues:
            print('  -', fi)
        if examples:
            print('  Examples:')
            for ln, spaces, text in examples:
                print(f'    {ln:4d}: ({spaces} spaces) {text}')
        print()

sys.exit(0)
