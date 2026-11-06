#!/bin/bash
# Every check that needs no reboot and no sudo; it writes only under build/. Run it before a commit that goes public.
#   bash tools/check_all.sh [--compiled DIR] [arguments for check_identifiers.py]
# With --compiled DIR, the folder postinstall.py build fills, it also assembles and validates the full EFI.
# To look for your own values, pass your config.plist: bash tools/check_all.sh --config /Volumes/NAME/EFI/OC/config.plist
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
COMPILED=""
if [ "${1:-}" = --compiled ]; then COMPILED=$2; shift 2; fi
bad=0
run() { echo; echo "== $1"; shift; "$@" || { echo "FAILED: $*"; bad=$((bad + 1)); }; }
run "shell syntax" bash -n postinstall/build.sh postinstall/rollback.sh tools/check_all.sh
run "python syntax" python3 -c 'import ast, sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]' efi/build_efi.py postinstall/postinstall.py postinstall/drop_flat_weak_binds.py tools/check_identifiers.py tools/sanitize_config.py tools/update_pins.py tests/test_postinstall.py
run "plist and json" /bin/sh -c 'plutil -lint efi/config.template.plist efi/config.install.template.plist efi/kexts/*/Contents/Info.plist > /dev/null && python3 -c "import json; json.load(open(\"efi/sources.lock.json\")); json.load(open(\"postinstall/manifest.json\"))"'
run "links between the documents" python3 -I -c '
import re, sys
from pathlib import Path
bad = 0
for md in Path(".").rglob("*.md"):
    if {"build", "private"} & set(md.parts):
        continue
    for link in re.findall(r"\]\(([^)#\s]+)", md.read_text()):
        if not link.startswith("http") and not (md.parent / link).exists():
            print(f"{md}: {link}")
            bad += 1
sys.exit(1 if bad else 0)'
run "postinstall logic on a fake system" python3 -I tests/test_postinstall.py
run "EFI install: downloads, hashes, ocvalidate, references" python3 -I efi/build_efi.py build --profile install --placeholder-identity --output build/check
if [ -n "$COMPILED" ]; then
  run "EFI full: downloads, hashes, ocvalidate, references" python3 -I efi/build_efi.py build --profile full --compiled "$COMPILED" --placeholder-identity --output build/check
else
  echo; echo "== EFI full: skipped, no --compiled"
fi
run "personal identifiers" python3 -I tools/check_identifiers.py "$@"
echo
if [ "$bad" = 0 ]; then echo "every check passed"; else echo "$bad check(s) failed"; exit 1; fi
