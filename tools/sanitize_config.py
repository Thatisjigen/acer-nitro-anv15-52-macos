#!/usr/bin/env python3
"""Turn a working OpenCore config.plist into a template that can be published.

  python3 tools/sanitize_config.py make SOURCE TEMPLATE     write the template: identity replaced by OpenCore's sample values,
                                                            missing OpenCore 1.0.9 keys added with the value OpenCore uses
                                                            when they are absent, comments brought up to date
  python3 tools/sanitize_config.py compare SOURCE TEMPLATE  print what differs; identity values are never printed

Exit code of compare: 0 when the only differences are the identity and the expected ones, 1 otherwise. Comment fields do not count:
OpenCore does not read them.
"""
import plistlib
import re
import sys

IDENTITY_KEYS = ('SystemSerialNumber', 'MLB', 'SystemUUID', 'ROM')
PLACEHOLDERS = {'SystemSerialNumber': 'W00000000001', 'MLB': 'M0000000000000001',
                'SystemUUID': '00000000-0000-0000-0000-000000000000', 'ROM': bytes.fromhex('112233445566')}

# A config re-saved by an older editor loses these keys and ocvalidate 1.0.9 reports them. Each value is the default of
# OcConfigurationLib.h at OpenCore 78d5ff8, so adding it changes nothing OpenCore does. InitialMode is the one exception to "the
# default": its default is the empty string, which ocvalidate refuses, and "Auto" is the only mode that does not force one.
MISSING_DEFAULTS = {
    ('Booter', 'Quirks', 'ClearTaskSwitchBit'): False,
    ('Booter', 'Quirks', 'FixupAppleEfiImages'): False,
    ('Kernel', 'Quirks', 'DisableIoMapperMapping'): False,
    ('Misc', 'Boot', 'InstanceIdentifier'): '',
    ('UEFI', 'Output', 'ConsoleFont'): '',
    ('UEFI', 'Output', 'GopBurstMode'): False,
    ('UEFI', 'Output', 'InitialMode'): 'Auto',
    ('UEFI', 'ProtocolOverrides', 'PciIo'): False,
    ('UEFI', 'Quirks', 'ResizeUsePciRbIo'): False,
    ('UEFI', 'Quirks', 'ShimRetainProtocol'): False,
    ('UEFI', 'Unload'): [],
}

# OpenCore does not read comments: these say what each kext is here.
KEXT_COMMENTS = {
    'Lilu.kext': 'Lilu 1.7.2 DEBUG, needed by the DEBUG build of WhateverXe',
    'AppleALC.kext': 'AppleALC 1.9.8 with ALC245 layouts 66 and 67, fork branch acer/current',
    'NMHDA.kext': 'NMHDA of NullMoth, fork branch acer/current: HDMI audio of the RTX, 10DE:22EC',
    'AMFIPass.kext': 'AMFIPass 1.4.1 Mod, from WhateverXe-Graphics extras/: off, it has nothing to do with the AMFI boot-args',
    'SMCLightSensor.kext': 'VirtualSMC 1.3.9: off, it finds no light sensor on this laptop',
    'SMCProcessor.kext': 'VirtualSMC 1.3.9: off, it finds no processor it supports on this laptop',
    'SMCSuperIO.kext': 'VirtualSMC 1.3.9: off, it finds no SuperIO chip on this laptop',
    'VoodooPS2Controller.kext/Contents/PlugIns/VoodooPS2Mouse.kext': 'VoodooPS2 2.3.8: off, the trackpad is on I2C',
    'VoodooPS2Controller.kext/Contents/PlugIns/VoodooPS2Trackpad.kext': 'VoodooPS2 2.3.8: off, the trackpad is on I2C',
    'SMCNvidiaGPU.kext': 'RTX sensors for VirtualSMC, fork branch acer/current; built together with NVRM',
    'WhateverXe.kext': 'WhateverXe 0.8.2 DEBUG, fork branch acer/current; in place of WhateverGreen',
    'HybridPM.kext': 'XE-PM (JulioNectar, TSNPL 1.0) as a Lilu plugin; on by default, -nohpm in boot-args turns it off',
    'NitroEC.kext': 'NitroEC, fork branch acer/current: EC window 0xFE708500',
    'AirportItlwm.kext': 'AirportItlwm 2.4.0-alpha laobamac: only for an Intel card, in place of the MT7920',
    'IntelBluetoothFirmware.kext': 'Intel Bluetooth 2.5.2 lshbluesky: only for an Intel card',
    'IntelBTPatcher.kext': 'Intel Bluetooth 2.5.2 lshbluesky: only for an Intel card',
    'BlueToolFixup.kext': 'BrcmPatchRAM 2.7.2: for the Bluetooth of either card',
    'AirportMtkWlan.kext': 'AirportMtkWlan of SimpleMtkWlan, fork branch acer/current: the original MT7920 Wi-Fi card, Wi-Fi 6 unless -mtknohe, firmware generated at build',
    'SimpleMtkBtFw.kext': 'SimpleMtkBtFw 1.1.0 DEBUG with the USB match 13D3:3622 of this laptop: Bluetooth of the MT7920',
    'SimpleMtkBtPatcher.kext': 'SimpleMtkBtPatcher, fork branch acer/current: Bluetooth of the MT7920, USB buffers read only',
    'IDispHDA.kext': 'IDispHDA, AppleALC fork branch acer/current: audio of the Iris Xe over USB-C',
    'NMAppFree.kext': 'NMAppFree: user apps out of the strict Mach IPC policy of the AMFI boot-args, so Widevine works in Chrome; needs Lilu',
    'USBDiskKeeper.kext': 'USBDiskKeeper, USBKeeper main: the USB disk OpenCore starts from stays attached when its port drops it at wake; needs Lilu',
}
ACPI_COMMENTS = {'SSDT-NITRO.aml': 'NTRO device for NitroEC: EC RAM window 0xFE708500, firmware controls, Darwin only'}
COMMENTS = {
    'preserve firmware MMIO 0xFF000000 containing panic CR2 0xFF09804C; hardware test pending': 'Keep the firmware MMIO at 0xFF000000: without it, a page fault at boot',
    'remove one duplicate 101-byte Acer AEVD SSDT; preserve the other original': 'Remove one of the two 101-byte Acer AEVD SSDTs; the other stays',
    'VoodooI2C waits for VoodooGPIO without a limit, not 1 s': 'VoodooI2C waits for VoodooGPIO without a limit instead of 1 s, or the trackpad can stay absent',
}
REFERENCE = re.compile(r'\b[A-Z]+-\d{3}\b(?: fallback)?')
# -nmappfreedbg, a log line for each app NMAppFree exempts, is left out. HDR modes, turbo and Wi-Fi 6 are on in the kexts themselves
BOOT_ARGS_LEFT_OUT = ['-nmappfreedbg']
BOOT_ARGS_ADDED = []
# An experiment still listed, disabled, in the config this comes from
KEXTS_LEFT_OUT = []


def clean_comments(node):
    """Comments that only speak to whoever reads the config. OpenCore does not read them."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == 'Comment' and isinstance(value, str):
                value = re.sub(r' from ' + REFERENCE.pattern, '', value)
                value = REFERENCE.sub('', value).replace('| : ', '| ').lstrip(': ').strip()
                node[key] = COMMENTS.get(value, value)
            else:
                clean_comments(value)
    elif isinstance(node, list):
        for item in node:
            clean_comments(item)


def make(source, target, profile):
    with open(source, 'rb') as f:
        cfg = plistlib.load(f)
    cfg['Kernel']['Add'] = [k for k in cfg['Kernel']['Add'] if k['BundlePath'] not in KEXTS_LEFT_OUT]
    for key in [k for k in cfg if k.startswith('#')]:
        del cfg[key]
    generic = cfg['PlatformInfo']['Generic']
    for key in IDENTITY_KEYS:
        generic[key] = PLACEHOLDERS[key]
    for path, value in MISSING_DEFAULTS.items():
        node = cfg
        for part in path[:-1]:
            node = node[part]
        node.setdefault(path[-1], value)
    for driver in cfg['UEFI']['Drivers']:
        driver.setdefault('HideVerbose', False)
    for kext in cfg['Kernel']['Add']:
        if kext['BundlePath'] in KEXT_COMMENTS and profile == 'full':
            kext['Comment'] = KEXT_COMMENTS[kext['BundlePath']]
    for table in cfg['ACPI']['Add']:
        if table['Path'] in ACPI_COMMENTS and profile == 'full':
            table['Comment'] = ACPI_COMMENTS[table['Path']]
    clean_comments(cfg)
    uuid = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
    args = cfg['NVRAM']['Add'][uuid]['boot-args'].split()
    cfg['NVRAM']['Add'][uuid]['boot-args'] = ' '.join([a for a in args if a not in BOOT_ARGS_LEFT_OUT] + [x for x in BOOT_ARGS_ADDED if x not in args])
    with open(target, 'wb') as f:
        plistlib.dump(cfg, f, sort_keys=False)
    print(f'{target}: identity replaced by placeholders')


def walk(a, b, path, report):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            sub = path + '/' + key
            if key.startswith('#') or key == 'Comment':
                continue
            if key in IDENTITY_KEYS:
                report.append(('identity', sub, 'replaced' if a.get(key) != b.get(key) else 'SAME VALUE'))
            elif key not in a:
                report.append(('added', sub, repr(b[key])))
            elif key not in b:
                report.append(('REMOVED', sub, repr(a[key])))
            else:
                walk(a[key], b[key], sub, report)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            report.append(('CHANGED', path, f'{len(a)} entries => {len(b)}'))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f'{path}[{i}]', report)
    elif a != b or type(a) is not type(b):
        report.append(('CHANGED', path, f'{a!r} => {b!r}'))


def compare(source, target):
    with open(source, 'rb') as f:
        a = plistlib.load(f)
    with open(target, 'rb') as f:
        b = plistlib.load(f)
    uuid = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
    args = a['NVRAM']['Add'][uuid]['boot-args'].split()
    a['NVRAM']['Add'][uuid]['boot-args'] = ' '.join([x for x in args if x not in BOOT_ARGS_LEFT_OUT] + [x for x in BOOT_ARGS_ADDED if x not in args])
    a['Kernel']['Add'] = [k for k in a['Kernel']['Add'] if k['BundlePath'] not in KEXTS_LEFT_OUT]
    report = []
    walk(a, b, '', report)
    expected = {'/'.join(('',) + p) for p in MISSING_DEFAULTS}
    bad = 0
    for kind, path, detail in report:
        unexpected = kind in ('REMOVED', 'CHANGED') or detail == 'SAME VALUE' or (
            kind == 'added' and path not in expected and not path.endswith('/HideVerbose'))
        bad += unexpected
        print(f'{"UNEXPECTED " if unexpected else ""}{kind:9} {path} {detail}')
    print(f'{len(report)} differences, {bad} unexpected')
    return 1 if bad else 0


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ('make', 'make-install', 'compare'):
        sys.exit(__doc__)
    mode, source, target = sys.argv[1:]
    if mode == 'compare':
        sys.exit(compare(source, target))
    make(source, target, 'install' if mode == 'make-install' else 'full')


if __name__ == '__main__':
    main()
