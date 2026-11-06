#!/bin/bash
# Puts back what postinstall.py install replaced: a copy of this script sits in each backup folder, next to the copies and the journal.
# It needs only bash and what any macOS has, Recovery included, so it works when the system no longer starts.
#   bash rollback.sh           prints what it would do
#   sudo bash rollback.sh --go the whole install back, last step first
# From Recovery the system is on another volume, the one that holds /Library and /Applications. The script sees that from its own path:
#   bash "/Volumes/NAME - Data/Library/ANV15-52/backup-DATE/rollback.sh" --go
# Each line of journal.tsv is: step, path, whether it was there. A path that was not there is removed.
# It is all or nothing on purpose: going back part of the way would leave a kernel collection that does not match the kexts on the disk.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=""; GO=0
case $HERE in */Library/ANV15-52/*) ROOT=${HERE%%/Library/ANV15-52/*} ;; esac   # empty on the running system
while [ $# -gt 0 ]; do
  case $1 in
    --root) ROOT=${2:?}; shift 2 ;;
    --go) GO=1; shift ;;
    *) echo "usage: rollback.sh [--go]"; exit 2 ;;
  esac
done
J=$HERE/journal.tsv
[ -f "$J" ] || { echo "STOP: no journal in $HERE"; exit 1; }
[ "$GO" = 1 ] || echo "Nothing is changed without --go. This is what it would do:"
if [ "$GO" = 1 ]; then
  if [ -z "$ROOT" ]; then
    [ "$(id -u)" = 0 ] || { echo "STOP: run it with sudo"; exit 1; }
    launchctl bootout system/com.nitrosense.nitrod 2>/dev/null
  fi
  rm -f "$HERE/../state.json"   # from here on the install is not what the state says; if this stops half way, run it again
fi
bad=0
# tail -r: the journal from the bottom up, so that a path saved by two steps ends up as the first one found it
while IFS='	' read -r step path state; do
  # Only a whole line is acted on. In Recovery ROOT is the data volume, so an empty path would mean all of it
  case $state in present|absent) ;; *) echo "BAD line in the journal, left alone: [$step] [$path] [$state]"; bad=1; continue ;; esac
  case $path in /?*) ;; *) echo "BAD line in the journal, left alone: [$step] [$path] [$state]"; bad=1; continue ;; esac
  target=$ROOT$path
  if [ "$state" = present ]; then
    copy=$HERE/files/$step/${path#/}
    if [ ! -e "$copy" ] && [ ! -L "$copy" ]; then echo "MISSING copy: $copy"; bad=1; continue; fi
    echo "  $step: restore $path"
    if [ "$GO" = 1 ]; then
      rm -rf "$target" && mkdir -p "$(dirname "$target")" && ditto "$copy" "$target" || { echo "FAILED: $target"; bad=1; }
    fi
  else
    if [ -e "$target" ] || [ -L "$target" ]; then
      echo "  $step: remove $path (it was not there)"
      if [ "$GO" = 1 ]; then rm -rf "$target" || { echo "FAILED: $target"; bad=1; }; fi
    fi
  fi
done < <(tail -r "$J")
if [ "$bad" != 0 ]; then echo "STOP: not everything came back; the copies stay in $HERE. This script can be run again."; exit 1; fi
if [ "$GO" = 1 ]; then
  sync
  echo "Done. The copies stay in $HERE. Restart: the EFI does not go back with this, and the Apple Intel driver in /Library needs WhateverXe in the EFI, so choose the EFI that matches."
fi
