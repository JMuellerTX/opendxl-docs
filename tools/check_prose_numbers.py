#!/usr/bin/env python3
"""Check hand-written figures in the prose against data/fork-changes.json.

`tools/gen_fork.py` renders `docs/fork.md` from the inventory, and CI already
refuses a mismatch between the two. But a number can also be typed into a
sentence, and then nothing watches it: `docs/compatibility.md` claimed "215
commits across 43 of them, including 16 security changes and 35 bug fixes" for
six regenerations after that stopped being true - by the end it was off by a
factor of three, on a page that links to the correct figures one line later.

So any sentence in the prose that states these totals has to agree with the
inventory. Generated pages are skipped: gen_fork.py owns those, and the other
check owns gen_fork.py.

    python tools/check_prose_numbers.py      # exit 1 on a mismatch
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'fork-changes.json')
DOCS = os.path.join(ROOT, 'docs')
GENERATED = {'fork.md', 'repositories.md'}

# "330 commits across 44 of them, including 51 security changes and 59 bug fixes"
SENTENCE = re.compile(
    r'(\d+)\s+commits?\s+across\s+(\d+)\s+of\s+(?:them|\d+)[^.]*?'
    r'(\d+)\s+security\s+(?:changes|fixes)\s+and\s+(\d+)\s+bug\s+fixes',
    re.IGNORECASE | re.DOTALL)


def main():
    totals = json.load(open(DATA, encoding='utf-8'))['totals']
    want = (totals['commits'], totals['repositories_touched'],
            totals['by_kind'].get('security', 0), totals['by_kind'].get('bug', 0))
    labels = ('commits', 'repositories', 'security fixes', 'bug fixes')

    bad = found = 0
    for base, _, files in os.walk(DOCS):
        for name in sorted(files):
            if not name.endswith('.md') or name in GENERATED:
                continue
            path = os.path.join(base, name)
            text = open(path, encoding='utf-8').read()
            for match in SENTENCE.finditer(text):
                found += 1
                got = tuple(int(g) for g in match.groups())
                where = os.path.relpath(path, ROOT).replace(os.sep, '/')
                line = text[:match.start()].count('\n') + 1
                if got == want:
                    print('  ok    %s:%d  %s' % (where, line, ' / '.join(map(str, got))))
                    continue
                bad += 1
                print('  WRONG %s:%d' % (where, line))
                for label, g, w in zip(labels, got, want):
                    if g != w:
                        print('        %-14s says %s, the inventory says %s' % (label, g, w))

    print('inventory: %d commits, %d of %d repositories, %d security, %d bug'
          % (totals['commits'], totals['repositories_touched'],
             totals['repositories_total'], want[2], want[3]))
    if not found:
        print('no prose totals found - if the sentence was reworded, teach the '
              'pattern in this script rather than dropping the check.')
    if bad:
        print('\n%d mismatch(es). Regenerate the inventory, then fix the prose.' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
