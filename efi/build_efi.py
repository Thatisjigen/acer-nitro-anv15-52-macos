#!/usr/bin/env python3
"""Assemble the OpenCore folder for the Acer Nitro ANV15-52: downloads with hashes, ACPI and USB map from this repository, your identity.

  python3 efi/build_efi.py identity                          once only: your serial, MLB, UUID and ROM in private/identity.json
  python3 efi/build_efi.py build --profile install           the EFI for installing macOS: downloads only, no compiler needed
  python3 efi/build_efi.py build --profile full --compiled DIR   the EFI of the finished system; DIR comes from postinstall.py build
  python3 efi/build_efi.py validate FOLDER                   ocvalidate, then every file the config names, then the kext order
  python3 efi/build_efi.py deploy --profile full --volume /Volumes/NAME         what deploying would do; nothing is written
  python3 efi/build_efi.py deploy --profile full --volume /Volumes/NAME --go    backup, copy, read back

The result goes to build/EFI/EFI/OC (full) or build/EFI/EFI/OC-INSTALL (install), never with EFI/BOOT/BOOTx64.efi: rEFInd stays the
main boot manager and OpenCore is one of its entries. build/ and private/ are outside Git, because the result carries your identity.
Works on macOS and Linux; compiling the forks needs macOS. Python 3.9 or newer, standard library only.
"""
import argparse
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'efi/sources.lock.json').read_text())
CACHE = ROOT / 'build/cache'
IDENTITY = ROOT / 'private/identity.json'
PROFILES = {'full': ('config.template.plist', 'OC'), 'install': ('config.install.template.plist', 'OC-INSTALL')}
MODEL = 'MacBookPro16,2'
PLACEHOLDER_SERIAL = 'W00000000001'


def die(msg):
    sys.exit(f'STOP: {msg}')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch(name):
    """The asset, from the cache or the network; a hash that differs stops everything."""
    asset = LOCK['assets'][name]
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f'{asset["sha256"][:12]}-{asset["url"].rsplit("/", 1)[1]}'
    if not path.exists():
        print(f'  downloading {name}: {asset["url"]}')
        tmp = path.with_suffix('.part')
        with urllib.request.urlopen(asset['url'], timeout=300) as r, open(tmp, 'wb') as f:
            shutil.copyfileobj(r, f)
        tmp.rename(path)
    got = sha256(path)
    if got != asset['sha256']:
        path.unlink()
        die(f'{name}: hash {got}, expected {asset["sha256"]}; the file was removed')
    return path


def tool(kind, workdir):
    """ocvalidate or macserial for this system, out of the OpenCore archive."""
    member = LOCK['tools'][kind][platform.system()] if platform.system() in LOCK['tools'][kind] else None
    if not member:
        die(f'{kind} is available here only on macOS and Linux')
    target = Path(workdir) / kind
    if not target.exists():
        with zipfile.ZipFile(fetch(LOCK['tools']['asset'])) as z:
            target.write_bytes(z.read(member))
        target.chmod(0o755)
    return target


def make_identity(_args):
    if IDENTITY.exists():
        print(f'{IDENTITY.relative_to(ROOT)} exists and is kept: a new serial would make this a different Mac to macOS. Delete it by hand only if you mean that.')
        return
    with tempfile.TemporaryDirectory() as t:
        out = subprocess.run([str(tool('macserial', t)), '-m', MODEL, '-n', '1'], capture_output=True, text=True, check=True).stdout
    m = re.match(r'^([A-Z0-9]{12}) \| ([A-Z0-9]{17})\s*$', out.strip())
    if not m:
        die('unexpected output from macserial; nothing written')
    rom = bytearray(os.urandom(6))
    rom[0] = (rom[0] & 0xFE) | 0x02  # unicast, locally administered: never someone's real card
    identity = {'model': MODEL, 'SystemSerialNumber': m[1], 'MLB': m[2], 'SystemUUID': str(uuid.uuid4()).upper(), 'ROM': bytes(rom).hex()}
    IDENTITY.parent.mkdir(exist_ok=True)
    fd = os.open(IDENTITY, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(identity, f, indent=1)
    print(f'{IDENTITY.relative_to(ROOT)} written, readable by you only. The values are not printed. Keep a copy: this folder is not in Git.')


def load_identity(placeholder):
    if placeholder:
        return None
    if not IDENTITY.exists():
        die(f'no {IDENTITY.relative_to(ROOT)}: run "python3 efi/build_efi.py identity" first (--placeholder-identity is only for checking, it does not boot as a usable Mac)')
    value = json.loads(IDENTITY.read_text())
    uuid.UUID(value['SystemUUID'])
    if len(bytes.fromhex(value['ROM'])) != 6 or len(value['SystemSerialNumber']) != 12 or len(value['MLB']) != 17:
        die(f'{IDENTITY.relative_to(ROOT)} does not have the expected fields; nothing printed')
    return value


def copy_kext_from_zip(archive, root, dest):
    """Extract one kext folder from a zip, without the junk macOS archives carry."""
    with zipfile.ZipFile(archive) as z:
        prefix = root.rstrip('/') + '/'
        names = [n for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')]
        if not names:
            die(f'{root} is not in {archive.name}')
        for name in names:
            rel = name[len(prefix):]
            if '__MACOSX' in name or Path(rel).name in ('.DS_Store',) or Path(rel).name.startswith('._'):
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            info = z.getinfo(name)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:  # a symlink in the archive; a FAT volume cannot hold it
                die(f'{name} is a symbolic link; refusing it')
            target.write_bytes(z.read(name))


def add_usb_match(folder, match):
    """A copy of an existing USB personality with this laptop's Bluetooth ID: the driver still checks chip, firmware and flavour itself."""
    path = folder / 'Contents/Info.plist'
    info = plistlib.loads(path.read_bytes())
    personalities = info['IOKitPersonalities']
    candidate = dict(personalities[match['from']])
    if candidate['IOProviderClass'] != 'IOUSBHostDevice':
        die(f'{folder.name}: {match["from"]} is not a USB personality')
    candidate.update(idVendor=match['idVendor'], idProduct=match['idProduct'])
    personalities[match['name']] = candidate
    path.write_bytes(plistlib.dumps(info, sort_keys=False))


def check_kext(name, folder, spec):
    binary = folder / f'Contents/MacOS/{name}'
    plist = folder / 'Contents/Info.plist'
    if 'plist_sha256' in spec and sha256(plist) != spec['plist_sha256']:
        die(f'{name}: Info.plist is not the expected one')
    if 'binary_sha256' in spec and sha256(binary) != spec['binary_sha256']:
        die(f'{name}: executable is not the expected one')


def build(args):
    template, folder_name = PROFILES[args.profile]
    identity = load_identity(args.placeholder_identity)
    out_root = Path(args.output).resolve() if args.output else ROOT / 'build/EFI'
    oc = out_root / 'EFI' / folder_name
    with open(ROOT / 'efi' / template, 'rb') as f:
        cfg = plistlib.load(f)
    if args.profile == 'full' and not args.compiled:
        die('--profile full needs --compiled DIR: the kexts of the forks come from postinstall.py build')
    if oc.exists():
        shutil.rmtree(oc)
    for sub in ('ACPI', 'Drivers', 'Kexts'):
        (oc / sub).mkdir(parents=True)
    manifest = {'profile': args.profile, 'opencore': LOCK['opencore'], 'date': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'files': {}}

    for rel, spec in LOCK['efi_files'].items():
        archive = fetch(spec['asset'])
        target = oc / rel
        if spec['path']:
            with zipfile.ZipFile(archive) as z:
                target.write_bytes(z.read(spec['path']))
        else:
            shutil.copyfile(archive, target)
        if sha256(target) != spec['sha256']:
            die(f'{rel}: not the expected file')

    for entry in cfg['ACPI']['Add']:
        shutil.copyfile(ROOT / 'efi/acpi' / entry['Path'], oc / 'ACPI' / entry['Path'])

    compiled_seen = {}
    built = {}
    if args.compiled and (Path(args.compiled) / 'manifest.json').exists():
        built = json.loads((Path(args.compiled) / 'manifest.json').read_text())['files']
    for name, spec in LOCK['kexts'][args.profile].items():
        dest = oc / 'Kexts' / f'{name}.kext'
        if spec.get('compiled'):
            src = Path(args.compiled) / f'{name}.kext'
            if not (src / f'Contents/MacOS/{name}').is_file():
                die(f'{src} is missing: run postinstall.py build first')
            shutil.copytree(src, dest, symlinks=False, ignore=shutil.ignore_patterns('.DS_Store', '._*'))
            compiled_seen[name] = sha256(src / f'Contents/MacOS/{name}')
            recorded = built.get(f'{name}.kext/Contents/MacOS/{name}')
            if recorded and recorded != compiled_seen[name]:
                die(f'{name} changed after the build recorded it')
        elif spec.get('local'):
            shutil.copytree(ROOT / spec['local'], dest, ignore=shutil.ignore_patterns('.DS_Store', '._*'))
        else:
            copy_kext_from_zip(fetch(spec['asset']), spec['root'], dest)
            if spec.get('usb_match'):
                add_usb_match(dest, spec['usb_match'])
        check_kext(name, dest, spec)

    if identity:
        generic = cfg['PlatformInfo']['Generic']
        for key in ('SystemSerialNumber', 'MLB', 'SystemUUID'):
            generic[key] = identity[key]
        generic['ROM'] = bytes.fromhex(identity['ROM'])
    cfg.pop('#Origin', None)
    with open(oc / 'config.plist', 'wb') as f:
        plistlib.dump(cfg, f, sort_keys=False)
    (oc / '.contentFlavour').write_text('OpenCore')
    (oc / '.contentVisibility').write_text('Disabled')

    for path in sorted(p for p in oc.rglob('*') if p.is_file()):
        if path.name != 'config.plist':
            manifest['files'][str(path.relative_to(oc))] = sha256(path)
    manifest['compiled'] = compiled_seen
    manifest['identity'] = 'placeholder' if not identity else 'private/identity.json'
    (out_root / f'manifest-{args.profile}.json').write_text(json.dumps(manifest, indent=1) + '\n')

    issues = validate_folder(oc)
    if issues:
        die(f'{oc} did not pass: {issues} problem(s) above')
    print(f'{oc}: {len(manifest["files"])} files, config validated')
    if not identity:
        print('This one has the sample identity of OpenCore: it is for checking. Run "identity" and build again before you boot from it.')
    not_tested = [k for k, v in LOCK['kexts'][args.profile].items() if not v.get('compiled') and not v.get('same_as_tested')]
    if not_tested:
        print('Not byte-identical to what was tested: ' + ', '.join(not_tested) + ' (see efi/README.md)')
    if compiled_seen:
        print('Compiled on this machine: ' + ', '.join(sorted(compiled_seen)) + '. postinstall.py build says how each one compares with what was tested')


def validate_folder(oc):
    """ocvalidate, then the files the config refers to, then the order of the kexts. Returns the number of problems."""
    oc = Path(oc)
    cfg_path = oc / 'config.plist'
    with open(cfg_path, 'rb') as f:
        cfg = plistlib.load(f)
    problems = 0
    with tempfile.TemporaryDirectory() as t:
        r = subprocess.run([str(tool('ocvalidate', t)), str(cfg_path)], capture_output=True, text=True, errors='replace')
    text = r.stdout + r.stderr
    if 'No issues found' in text:
        print(f'ocvalidate {LOCK["opencore"].split()[0]}: no issues')
    else:
        problems += 1
        print(text.replace(str(oc), '<folder>'))
    missing = [k for k in ('ACPI', 'Kernel', 'Misc', 'UEFI') if k not in cfg]
    if missing:
        print('config.plist has no ' + ', '.join(missing))
        return problems + 1
    for entry in cfg['ACPI']['Add']:
        if entry['Enabled'] and not (oc / 'ACPI' / entry['Path']).is_file():
            print(f'missing ACPI/{entry["Path"]}')
            problems += 1
    for entry in cfg['UEFI']['Drivers']:
        if entry['Enabled'] and not (oc / 'Drivers' / entry['Path']).is_file():
            print(f'missing Drivers/{entry["Path"]}')
            problems += 1
    loaded = {}
    for entry in cfg['Kernel']['Add']:
        bundle = oc / 'Kexts' / entry['BundlePath']
        info = bundle / entry['PlistPath']
        if not info.is_file():
            print(f'missing Kexts/{entry["BundlePath"]}/{entry["PlistPath"]}{"" if entry["Enabled"] else " (entry disabled)"}')
            problems += 1
            continue
        if entry['ExecutablePath'] and not (bundle / entry['ExecutablePath']).is_file():
            print(f'missing Kexts/{entry["BundlePath"]}/{entry["ExecutablePath"]}')
            problems += 1
        if not entry['Enabled']:
            continue
        with open(info, 'rb') as f:
            plist = plistlib.load(f)
        for dep in plist.get('OSBundleLibraries', {}):
            if not dep.startswith('com.apple.') and dep not in loaded:
                print(f'{entry["BundlePath"]} needs {dep}, which no kext before it provides')
                problems += 1
        loaded[plist['CFBundleIdentifier']] = entry['BundlePath']
    boot = cfg['Misc']['Boot']
    if boot['LauncherOption'] != 'Disabled':
        print('LauncherOption must stay Disabled: rEFInd is the main boot manager')
        problems += 1
    if (oc.parent / 'BOOT').exists():
        print(f'{oc.parent / "BOOT"} exists next to this folder: this EFI does not provide a fallback loader; check it is not ours')
    print(f'{len(cfg["Kernel"]["Add"])} kext entries and {len(cfg["ACPI"]["Add"])} ACPI tables checked: {problems} problem(s)')
    return problems


def validate(args):
    if validate_folder(args.folder):
        sys.exit(1)


def deploy(args):
    _, folder_name = PROFILES[args.profile]
    src = (Path(args.output).resolve() if args.output else ROOT / 'build/EFI') / 'EFI' / folder_name
    volume = Path(args.volume)
    if not (src / 'OpenCore.efi').is_file():
        die(f'{src} is not built yet')
    with open(src / 'config.plist', 'rb') as f:
        if plistlib.load(f)['PlatformInfo']['Generic']['SystemSerialNumber'] == PLACEHOLDER_SERIAL and not args.allow_placeholder:
            die('this build has the sample identity: run "identity" and build again')
    if validate_folder(src):
        die(f'{src} did not pass: nothing written')
    if not volume.is_dir():
        die(f'{volume} is not mounted')
    if platform.system() == 'Darwin':
        info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(volume)]))
        if info.get('FilesystemType') != 'msdos' or not info.get('WritableVolume'):
            die(f'{volume} is not a writable FAT volume')
    dest = volume / 'EFI' / folder_name
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'private/efi-backups' / f'{folder_name}-before-{stamp}'
    new = sum(1 for p in src.rglob('*') if p.is_file())
    print(f'source: {src} ({new} files)')
    print(f'target: {dest} ({"exists: it would be saved to " + str(backup.relative_to(ROOT)) if dest.exists() else "new"})')
    print('Not touched: EFI/BOOT, any other folder on the volume, BootOrder, NVRAM, rEFInd.')
    tmp = dest.with_name(dest.name + '.new')
    size = sum(p.stat().st_size for p in src.rglob('*') if p.is_file())
    free = shutil.disk_usage(volume).free + (sum(p.stat().st_size for p in tmp.rglob('*') if p.is_file()) if tmp.exists() else 0)
    if free < size * 1.2:  # the old folder goes only once the new one is written and read back
        die(f'{volume} has {free // 2**20} MB free, and the new folder needs {size // 2**20} MB next to the old one; nothing written')
    if not args.go:
        print(f'It needs {size // 2**20} MB, {free // 2**20} MB are free. Nothing written. Add --go to do it.')
        return
    if dest.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(dest, backup)
    if tmp.exists():
        shutil.rmtree(tmp)
    (volume / 'EFI').mkdir(exist_ok=True)
    try:
        shutil.copytree(src, tmp, copy_function=shutil.copyfile)
    except (shutil.Error, OSError):
        shutil.rmtree(tmp, ignore_errors=True)
        die(f'the copy to {volume} failed; {dest} was not changed')
    for path in src.rglob('*'):
        if path.is_file() and sha256(path) != sha256(tmp / path.relative_to(src)):
            die(f'read-back differs on {path.relative_to(src)}; {dest} was not changed, the copy is in {tmp}')
    os.sync()   # the read-back may have come from the cache: the new folder must be on the stick before the old one goes
    old = dest.with_name(dest.name + '.old')
    if old.exists():
        shutil.rmtree(old)
    if dest.exists():
        dest.rename(old)
    tmp.rename(dest)
    if old.exists():
        shutil.rmtree(old)
    os.sync()
    print(f'{dest} written and read back. Previous copy: {backup.relative_to(ROOT) if backup.exists() else "none"}.')
    print('Rollback: copy that folder back over ' + str(dest) + '. Changing the EFI does not undo what is installed in /Library.')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('identity').set_defaults(func=make_identity)
    b = sub.add_parser('build')
    b.add_argument('--profile', choices=PROFILES, required=True)
    b.add_argument('--compiled', help='folder with the kexts of the forks (postinstall.py build writes them)')
    b.add_argument('--output', help='default: build/EFI')
    b.add_argument('--placeholder-identity', action='store_true', help='keep the sample identity, for checking only')
    b.set_defaults(func=build)
    v = sub.add_parser('validate')
    v.add_argument('folder', help='the folder with config.plist')
    v.set_defaults(func=validate)
    d = sub.add_parser('deploy')
    d.add_argument('--profile', choices=PROFILES, required=True)
    d.add_argument('--volume', required=True, help='a mounted FAT volume, /Volumes/NAME')
    d.add_argument('--output', help='where build wrote, default build/EFI')
    d.add_argument('--go', action='store_true', help='without it nothing is written')
    d.add_argument('--allow-placeholder', action='store_true', help=argparse.SUPPRESS)
    d.set_defaults(func=deploy)
    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
