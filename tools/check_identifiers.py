#!/usr/bin/env python3
"""Before anything goes public: look for personal identifiers in this repository, files and Git history. It never prints a value.

  python3 tools/check_identifiers.py [--config PLIST ...] [--identity JSON ...] [--also-from FILE ...]

It looks for:
  - serial, MLB, SystemUUID and ROM of every --config (OpenCore config.plist) and --identity (JSON, for example private/identity.json);
  - the MAC addresses, Bluetooth addresses, platform UUID and serial of the machine it runs on;
  - your Git address, your user name, your real name, your home folder and the name of this computer;
  - each line of every --also-from file: anything else you do not want published;
  - shapes that should not be here: home folders, e-mail addresses, MAC addresses, unknown UUIDs, references to a private work log.
In Git it reads every commit: authors, messages and patches. Every author and committer must use the address in ALLOWED_ADDRESS.
Binary files must be on BINARIES_ALLOWED, and their bytes are searched too.
A value found stops it with the kind of value and where, not the value. Exit code 0 means nothing was found.
"""
import argparse
import base64
import getpass
import json
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ADDRESS = {'55486333+Thatisjigen@users.noreply.github.com', 'noreply@anthropic.com'}
BINARIES_ALLOWED = re.compile(r'^efi/acpi/SSDT-[A-Za-z-]+\.aml$')
# GUIDs of OpenCore and Apple, OpenCore's sample identity, and the WMI interfaces of the Acer firmware named in SSDT-NITRO
UUIDS_ALLOWED = {'7c436110-ab2a-4bbb-a880-fe41995c9f82', '4d1fda02-38c7-4a6a-9cc6-4bcca8b30102', '8be4df61-93ca-11d2-aa0d-00e098032b8c',
                 '00000000-0000-0000-0000-000000000000', '94b73556-2197-4702-82a8-3e1337dafbfb',
                 '79772ec5-04b1-4bfd-843c-61e7f77b6cc9', '7a4ddfe7-5b5d-40b4-8595-4408e0cc7f56', '61ef69ea-865c-4bc3-a502-a0deba0cb531'}
PLACEHOLDERS = {'w00000000001', 'm0000000000000001', '112233445566', '11:22:33:44:55:66', 'erizrfvm'}
SKIP = {'.git', 'build', 'private', '__pycache__', 'out'}


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors='replace').stdout


def identifiers(args):
    """{lowercase value: kind}; values shorter than 6 characters would match by chance."""
    found = {}

    def add(kind, value):
        value = str(value).strip().lower()
        if len(value) >= 6 and value not in PLACEHOLDERS:
            found[value] = kind

    def add_generic(generic, kind):
        for key in ('SystemSerialNumber', 'MLB', 'SystemUUID'):
            if generic.get(key):
                add(f'{kind} {key}', generic[key])
                add(f'{kind} {key}', str(generic[key]).replace('-', ''))
        rom = generic.get('ROM')
        if rom:
            rom = bytes.fromhex(rom) if isinstance(rom, str) else rom
            add(f'{kind} ROM', rom.hex())
            add(f'{kind} ROM', ':'.join(f'{b:02x}' for b in rom))
            add(f'{kind} ROM', '-'.join(f'{b:02x}' for b in rom))
            add(f'{kind} ROM', base64.b64encode(rom).decode().rstrip('='))

    for path in args.config:
        with open(path, 'rb') as f:
            add_generic(plistlib.load(f)['PlatformInfo']['Generic'], 'config')
    for path in args.identity:
        add_generic(json.loads(Path(path).read_text()), 'identity file')
    own = ROOT / 'private/identity.json'
    if own.exists():
        add_generic(json.loads(own.read_text()), 'identity file')
    for path in args.also_from:
        for line in Path(path).read_text().splitlines():
            add('--also-from value', line)

    for mac in re.findall(r'ether ((?:[0-9a-f]{2}:){5}[0-9a-f]{2})', sh('/sbin/ifconfig', '-a')):
        add('MAC address', mac)
        add('MAC address', mac.replace(':', ''))
        add('MAC address', mac.replace(':', '-'))
    for value in re.findall(r'"IOPlatform(?:UUID|SerialNumber)" = "([^"]+)"', sh('/usr/sbin/ioreg', '-rd1', '-c', 'IOPlatformExpertDevice')):
        add('platform identity', value)
        add('platform identity', value.replace('-', ''))
    for mac in re.findall(r'Address: ((?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})', sh('/usr/sbin/system_profiler', 'SPBluetoothDataType')):
        add('Bluetooth address', mac.replace('-', ':'))
        add('Bluetooth address', re.sub('[:-]', '', mac))
    user = os.environ.get('SUDO_USER') or getpass.getuser()
    add('user name', user)
    add('home folder', str(Path.home()))
    real = sh('/usr/bin/dscl', '.', '-read', f'/Users/{user}', 'RealName')
    for part in real.replace('RealName:', '').split():
        add('real name', part)
    for key in ('ComputerName', 'LocalHostName', 'HostName'):
        add('computer name', sh('/usr/sbin/scutil', '--get', key).strip())
    for scope in ('--global', '--system'):
        address = sh('/usr/bin/git', 'config', scope, 'user.email').strip()
        if address and address not in ALLOWED_ADDRESS:
            add('Git address', address)
            add('name in the Git address', address.split('@')[0])
    return found


# The codes of a private work log: a word and a number, with a hyphen, or without one as they appear inside a name
_LOG = (b'XE|FORK|GATE|GLASS|HDR|USB-C|OBS|NV|DEC|FLIP|BCS|AMFI|GAME|VID|XGPU|WIFI|PUB|BOOT|SLEEP|NM|GROUP|CTRL|CMD|BL|FAN|KB|TP|PERF|'
        b'AUDIO|UPG|SPIN|CPU|COLOR|DRM|SEC|VA')
SHAPES = [
    ('home folder', re.compile(rb'/(?:Users|home)/(?!Shared\b|\$|<|[A-Z_]+\b|runner\b|user\b|name\b|you\b)[A-Za-z0-9._-]+')),
    ('e-mail address', re.compile(rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}')),
    ('MAC address', re.compile(rb'\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b')),
    ('UUID', re.compile(rb'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')),
    ('reference to a private work log', re.compile(rb'\b(?:' + _LOG + rb')-\d{1,3}[A-Za-z]?\b|TEST-LOG|experiments/20')),
    ('reference to a private work log', re.compile(rb'(?<![A-Za-z0-9])(?:' + _LOG.replace(b'USB-C', b'USBC') + rb')_?0\d\d(?![0-9])')),
]
# More shapes of a private work log, one regular expression a line, in a file that stays outside Git
_extra = ROOT / 'private/leak-patterns.txt'
if _extra.exists():
    for _line in _extra.read_text().splitlines():
        if _line.strip() and not _line.startswith('#'):
            SHAPES.append(('reference to a private work log', re.compile(_line.strip().encode())))


def shape_hits(data):
    hits = []
    for kind, rx in SHAPES:
        for m in rx.finditer(data):
            text = m.group(0).decode('latin-1').lower()
            if kind == 'UUID' and text in UUIDS_ALLOWED:
                continue
            if kind == 'e-mail address' and (text in {a.lower() for a in ALLOWED_ADDRESS} or text.endswith(('@example.com', '@apple.com'))):
                continue
            if kind == 'MAC address' and text in PLACEHOLDERS:
                continue
            hits.append(kind)
    return hits


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--config', action='append', default=[])
    p.add_argument('--identity', action='append', default=[])
    p.add_argument('--also-from', action='append', default=[])
    args = p.parse_args()
    secret = identifiers(args)
    print(f'{len(secret)} identifiers to look for')
    problems = 0

    def report(where, kind):
        nonlocal problems
        problems += 1
        print(f'FOUND {kind} in {where}')

    files = [f for f in ROOT.rglob('*') if f.is_file() and not (set(f.relative_to(ROOT).parts) & SKIP)]
    binaries = 0
    for f in files:
        rel = str(f.relative_to(ROOT))
        data = f.read_bytes()
        lower = data.lower()
        if b'\0' in data:
            binaries += 1
            if not BINARIES_ALLOWED.match(rel):
                report(rel, 'a binary file not on the list')
        for value, kind in secret.items():
            if value.encode() in lower:
                report(rel, kind)
        if rel != 'tools/check_identifiers.py':
            for kind in sorted(set(shape_hits(data))):
                report(rel, f'the shape of a {kind}')
    print(f'{len(files)} files read, {binaries} binary')

    if (ROOT / '.git').exists():
        git = ['/usr/bin/git', '-C', str(ROOT)]
        commits = subprocess.run(git + ['rev-list', '--all', '--count'], capture_output=True, text=True).stdout.strip() or '0'
        if commits != '0':
            for address in set(subprocess.run(git + ['log', '--all', '--format=%ae%n%ce'], capture_output=True, text=True).stdout.split()):
                if address not in ALLOWED_ADDRESS:
                    report('a commit', 'an author or committer address that is not allowed')
            log = subprocess.run(git + ['log', '--all', '-p', '--binary', '--no-color', '--format=%H%n%an%n%cn%n%B'], capture_output=True).stdout
            lower = log.lower()
            for value, kind in secret.items():
                if value.encode() in lower:
                    report('the Git history', kind)
            # Shape check on what was added or written, skipping this file's own patterns and the hashes that begin each commit
            this_file = False
            added = bytearray()
            for line in log.split(b'\n'):
                if line.startswith(b'diff --git'):
                    this_file = b'tools/check_identifiers.py' in line
                elif not this_file:
                    added += line + b'\n'
            for kind in sorted(set(shape_hits(bytes(added)))):
                report('the Git history', f'the shape of a {kind}')
        print(f'{commits} commits read')
    if problems:
        sys.exit(f'{problems} problem(s): nothing should be published until they are gone')
    print('nothing found')


if __name__ == '__main__':
    main()
