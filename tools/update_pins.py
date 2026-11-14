#!/usr/bin/env python3
"""See whether the forks moved past what was last tested, and record a new test in postinstall/manifest.json.

  python3 tools/update_pins.py          read only: the commit last tested against the head of each branch on GitHub
  python3 tools/update_pins.py --write  writes the heads as the commits last tested

fetch takes the head of each branch anyway. The manifest says what the status in README.md is about and what fetch --tested takes, so
--write is a claim that those commits were tested: then update the status and tested_binaries, whose hashes are of what ran.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'postinstall/manifest.json'


def head(url, ref):
    out = subprocess.run(['/usr/bin/git', 'ls-remote', url, f'refs/heads/{ref}'], capture_output=True, text=True).stdout.split()
    return out[0] if out else None


def main():
    write = '--write' in sys.argv
    manifest = json.loads(PATH.read_text())
    moved = 0
    for name, fork in manifest['forks'].items():
        now = head(fork['url'], fork['ref'])
        same = now == fork['tested_commit']
        moved += not same
        print(f'{name:22} {fork["ref"]:14} tested {fork["tested_commit"][:12]}  on GitHub {(now or "absent")[:12]}  {"" if same else "MOVED"}')
        if write and now and not same:
            fork['tested_commit'] = now
    if write:
        PATH.write_text(json.dumps(manifest, indent=1) + '\n')
        print('manifest written: read the changes with git diff, and update tested_binaries and the docs')
    elif moved:
        print(f'{moved} moved. Nothing written; --write records the heads as tested.')


if __name__ == '__main__':
    main()
