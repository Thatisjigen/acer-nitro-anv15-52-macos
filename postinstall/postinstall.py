#!/usr/bin/env python3
"""Put the drivers of the Acer Nitro ANV15-52 into /Library after a clean install of macOS, in order, with a way back.

  python3 postinstall/postinstall.py doctor              read only: is this the right machine and system, what is missing
  python3 postinstall/postinstall.py fetch [--tested]    downloads with hashes, and the latest acer/current of each fork, in ~/anv15-52-build;
                                                         --tested takes the commits last tested instead
  python3 postinstall/postinstall.py build [stage ...]   compiles what fetch took, in the same folder
  python3 postinstall/postinstall.py plan                read only: what install would do, file by file
  sudo python3 postinstall/postinstall.py install --go   does it: each step saves what it replaces, then checks what it wrote
  python3 postinstall/postinstall.py state               what is installed now, against what was built
  python3 postinstall/postinstall.py verify              after the reboot: drivers loaded, Metal, hashes, signatures
  sudo python3 postinstall/postinstall.py rollback --go  everything back, last step first

install and rollback without --go print what they would do and change nothing. fetch and build refuse sudo, install and rollback need it.
None of this reboots. --root PATH works on a copy of the system tree instead of /, without sudo: kmutil, installer and launchctl do not run.
A clean install following these scripts has never been done: read postinstall/README.md first.
"""
import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = json.loads(Path(os.environ.get('ANV_MANIFEST', HERE / 'manifest.json')).read_text())   # ANV_MANIFEST: the tests
EXT = '/Library/Extensions'
GB = '/Library/GPUBundles'
KC = '/Library/KernelCollections/AuxiliaryKernelExtensions.kc'
KB = '/System/Library/KernelCollections/BootKernelExtensions.kc'
KS = '/System/Library/KernelCollections/SystemKernelExtensions.kc'
KERNEL = '/System/Library/Kernels/kernel'
STATE_DIR = '/Library/ANV15-52'
NVMTL = GB + '/NVMTLDriver.bundle'
METAL = GB + '/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver'
IMPOSTOR = GB + '/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/impostor.dylib'
DESCRIPTOR = GB + '/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/descriptor.dylib'
NITRO_DIR = '/Library/Application Support/NitroSense'
NITRO_PLIST = '/Library/LaunchDaemons/com.nitrosense.nitrod.plist'
NITRO_APP = '/Applications/NitroSense.app'
NVMTL_CONF = GB + '/nvmtl/nvrm610.conf'
NVENCVT_LINE = 'NVMTL_NVENCVT=WallpaperAerialsExtension,DisplaysExt'   # the Aerial wallpaper decodes on the RTX instead of in software
PANEL_OVERRIDE = '/Library/Displays/Contents/Resources/Overrides/DisplayVendorID-e77/DisplayProductID-1513'
ARTIFACTS = ['NVRM.kext/Contents/MacOS/NVRM', 'NVRMFB.kext/Contents/MacOS/NVRMFB', 'NVAccel.kext/Contents/MacOS/NVAccel',
             'NVRMAGDC.kext/Contents/MacOS/NVRMAGDC', 'bundle/NVMTLDriver', 'bundle/libnvmtl_translate.dylib', 'bundle/libnvencvt.dylib', 'bundle/impostor.dylib',
             'LatSOFAudio.kext/Contents/MacOS/LatSOFAudio', 'nitrosense/nitrod', 'nitrosense/nitroctl',
             'nitrosense/NitroSense.app/Contents/MacOS/NitroSense',
             # these go into the EFI, not into /Library: efi/build_efi.py --compiled out/
             'NMHDA.kext/Contents/MacOS/NMHDA', 'NitroEC.kext/Contents/MacOS/NitroEC', 'SMCNvidiaGPU.kext/Contents/MacOS/SMCNvidiaGPU',
             'WhateverXe.kext/Contents/MacOS/WhateverXe', 'HybridPM.kext/Contents/MacOS/HybridPM', 'AppleALC.kext/Contents/MacOS/AppleALC',
             'IDispHDA.kext/Contents/MacOS/IDispHDA', 'AirportMtkWlan.kext/Contents/MacOS/AirportMtkWlan',
             'SimpleMtkBtPatcher.kext/Contents/MacOS/SimpleMtkBtPatcher']
GRAPHICS_FORK = 'https://github.com/Thatisjigen/WhateverXe-Graphics.git'
# Which forks each compiled file comes from. SMCNvidiaGPU is built with NVRM, so both count
ARTIFACT_FORKS = {
    'NVRM.kext/Contents/MacOS/NVRM': ['nvidia-macos-driver'], 'NVRMFB.kext/Contents/MacOS/NVRMFB': ['nvidia-macos-driver'],
    'NVAccel.kext/Contents/MacOS/NVAccel': ['nvidia-macos-driver'], 'NVRMAGDC.kext/Contents/MacOS/NVRMAGDC': ['nvidia-macos-driver'],
    'NMHDA.kext/Contents/MacOS/NMHDA': ['nvidia-macos-driver'], 'bundle/NVMTLDriver': ['nvidia-macos-driver'], 'bundle/libnvmtl_translate.dylib': ['nvidia-macos-driver'],
    'bundle/libnvencvt.dylib': ['nvenc'], 'LatSOFAudio.kext/Contents/MacOS/LatSOFAudio': ['LatSOF-Audio'],
    'nitrosense/nitrod': ['NitroSense-macOS'], 'nitrosense/nitroctl': ['NitroSense-macOS'], 'nitrosense/NitroSense.app/Contents/MacOS/NitroSense': ['NitroSense-macOS'],
    'NitroEC.kext/Contents/MacOS/NitroEC': ['NitroSense-macOS'], 'SMCNvidiaGPU.kext/Contents/MacOS/SMCNvidiaGPU': ['SMCNvidiaGPU', 'nvidia-macos-driver'],
    'WhateverXe.kext/Contents/MacOS/WhateverXe': ['WhateverXe'], 'HybridPM.kext/Contents/MacOS/HybridPM': ['HybridPM'], 'AppleALC.kext/Contents/MacOS/AppleALC': ['AppleALC'],
    'IDispHDA.kext/Contents/MacOS/IDispHDA': ['AppleALC'], 'AirportMtkWlan.kext/Contents/MacOS/AirportMtkWlan': ['SimpleMtkWlan'],
    'SimpleMtkBtPatcher.kext/Contents/MacOS/SimpleMtkBtPatcher': ['SimpleMtkBtFw'],
}
COMPILED_FOR_EFI = ['NMHDA', 'NitroEC', 'SMCNvidiaGPU', 'WhateverXe', 'HybridPM', 'AppleALC', 'IDispHDA', 'AirportMtkWlan', 'SimpleMtkBtPatcher']
EFI_ARTIFACTS = [f'{k}.kext/Contents/MacOS/{k}' for k in COMPILED_FOR_EFI]


class Stop(Exception):
    """Something that must stop the run, with a sentence for the person reading it."""


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def owner_home():
    user = os.environ.get('SUDO_USER')
    if user:
        out = subprocess.run(['/usr/bin/dscl', '.', '-read', f'/Users/{user}', 'NFSHomeDirectory'], capture_output=True, text=True).stdout
        if ':' in out:
            return Path(out.split(':', 1)[1].strip())
    return Path.home()


class Ctx:
    def __init__(self, args):
        self.root = args.root.rstrip('/') if getattr(args, 'root', None) else ''
        self.fake = bool(self.root)
        # absolute: build.sh runs commands from other folders, where a relative path points elsewhere
        self.work = Path(args.work).expanduser().resolve() if getattr(args, 'work', None) else owner_home() / 'anv15-52-build'
        self.go = getattr(args, 'go', False)
        self.args = args
        self.src, self.deps, self.obj, self.out, self.dl, self.logs = [self.work / d for d in ('src', 'deps', 'obj', 'out', 'dl', 'logs')]
        self.pkgroot = self.deps / 'nullmoth/pkgroot'
        self.state_file = STATE_DIR + '/state.json'
        self.backup = None

    def p(self, path):
        """A system path, inside --root when there is one."""
        return self.root + path

    def run(self, cmd, env=None):
        """A command with its output in the terminal and in the log. Ctrl-C reaches it too: it finishes its own clean-up, which closing its pipe would kill."""
        print('   $ ' + ' '.join(str(c) for c in cmd), flush=True)
        p = subprocess.Popen([str(c) for c in cmd], env=dict(os.environ, **(env or {})), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        interrupted = False
        while True:
            try:
                for line in p.stdout:
                    print('   ' + line, end='', flush=True)
                break
            except KeyboardInterrupt:
                interrupted = True
        p.wait()
        if interrupted:
            raise Stop(f'interrupted; {cmd[0]} ended with status {p.returncode}')
        if p.returncode:
            raise Stop(f'{cmd[0]} failed with status {p.returncode}')

    def out_manifest(self):
        path = self.out / 'manifest.json'
        return json.loads(path.read_text()) if path.exists() else None

    def read_state(self):
        path = self.p(self.state_file)
        if not os.path.exists(path):
            return {}
        try:
            return json.loads(Path(path).read_text())
        except ValueError:
            raise Stop(f'{self.state_file} cannot be read. Nothing was changed. rollback.sh in the latest backup folder next to it still works')

    def write_state(self, state):
        path = Path(self.p(self.state_file))
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path) + '.new', 'w') as f:
            f.write(json.dumps(state, indent=1) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(path) + '.new', path)


def tree_sha256(root):
    h = hashlib.sha256()
    root = Path(root)
    for p in sorted(x for x in root.rglob('*') if x.is_file()):
        h.update(str(p.relative_to(root)).encode() + b'\0' + hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def describe(path):
    if os.path.islink(path):
        return 'symbolic link'
    if not os.path.exists(path):
        return 'absent'
    if os.path.isdir(path):
        return 'folder'
    return sha256(path)[:16]


# ---------------------------------------------------------------- the steps

class Step:
    name = ''
    what = ''
    touches = []
    needs_out = []

    def __init__(self, ctx):
        self.ctx = ctx

    def preflight(self):
        """Read only: the problems that would stop this step, as sentences."""
        return []

    def detail(self):
        return []

    def run(self):
        raise NotImplementedError

    def check(self):
        """Read only: after run, the sentence saying what is wrong, or None."""
        return None


def put_tree(ctx, src, dst):
    """A whole kext or bundle: gone and written anew, root's, 755, no extended attributes."""
    if os.path.lexists(dst):
        rmtree(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(['/usr/bin/ditto', '--norsrc', '--noextattr', str(src), str(dst)], check=True)
    if not ctx.fake:
        subprocess.run(['/usr/sbin/chown', '-R', 'root:wheel', dst], check=True)
    subprocess.run(['/bin/chmod', '-R', '755', dst], check=True)


def put_file(ctx, src, dst, mode=0o755):
    """One file, by rename: a process that has the old one mapped keeps it."""
    tmp = dst + '.anv-new'
    shutil.copyfile(src, tmp)
    os.chmod(tmp, mode)
    if not ctx.fake:
        os.chown(tmp, 0, 0)
    os.replace(tmp, dst)


def rmtree(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def resign_nvmtl(ctx):
    bundle = ctx.p(NVMTL)
    r = subprocess.run(['/usr/bin/codesign', '-f', '-s', '-', '-i', 'com.nullmoth.NVMTLDriver', bundle], capture_output=True, text=True)
    if r.returncode:
        raise Stop(f'cannot sign {bundle}: {r.stderr[-300:]}')
    if subprocess.run(['/usr/bin/codesign', '--verify', bundle], capture_output=True).returncode:
        raise Stop(f'the seal of {bundle} does not verify: run rollback')


class NullMoth(Step):
    name = 'nullmoth'
    what = 'NullMoth 2.7.2, the official package and its own installer: the kexts, the Metal plugin, NVK, the GSP firmware. Without its audio driver'
    touches = [EXT + '/NVRM.kext', EXT + '/NVAccel.kext', EXT + '/NVRMFB.kext', EXT + '/NVRMAGDC.kext', EXT + '/NMXAudio.kext', NVMTL, GB + '/NVIDIAShared.bundle', GB + '/nvmtl',
               GB + '/nvmtl-allow.txt', '/Library/NullMoth', '/Users/Shared/nvfw', '/Library/LaunchDaemons/com.nullmoth.bootguard.plist', '/Library/LaunchDaemons/com.nullmoth.lastgood.plist', KC]

    def preflight(self):
        c = self.ctx
        d = MANIFEST['downloads']['nullmoth']
        f = c.dl / d['file']
        if not f.exists():
            return [f'{f} is missing: run fetch']
        if sha256(f) != d['sha256']:
            return [f'{f} does not have the expected hash']
        if not (c.pkgroot / 'install.sh').exists():
            return [f'{c.pkgroot} is missing: run fetch']
        if sha256(c.pkgroot / 'SHA256SUMS') != d['sums_sha256']:
            return [f'{c.pkgroot} is not the package of this manifest: run fetch']
        return []

    def detail(self):
        return [f'runs {self.ctx.pkgroot}/install.sh, which backs up by itself and rebuilds the auxiliary collection',
                'removes NMXAudio.kext, which that installer adds on macOS 26: here sound comes from AppleALC, LatSOF-Audio and NMHDA, and the auxkc step rebuilds the collection without it',
                'it ends with "Done. Reboot now" and an "Undo" of its own: both are for its own use, not for this install. Do not restart: the steps after it are not done']

    def run(self):
        c = self.ctx
        r = subprocess.run(['/usr/bin/shasum', '-a', '256', '--strict', '--quiet', '-c', 'SHA256SUMS'], cwd=c.pkgroot, capture_output=True, text=True)
        if r.returncode:
            raise Stop(f'the unpacked NullMoth package does not match its SHA256SUMS: {r.stdout[-300:]}')
        if c.fake:
            subprocess.run(['/usr/bin/ditto', str(c.pkgroot / 'Library'), c.p('/Library')], check=True)
            if (c.pkgroot / 'Users/Shared/nvfw').exists():
                subprocess.run(['/usr/bin/ditto', str(c.pkgroot / 'Users/Shared/nvfw'), c.p('/Library/NullMoth/nvfw')], check=True)
            Path(c.p('/Library/LaunchDaemons')).mkdir(parents=True, exist_ok=True)
            Path(c.p('/Library/LaunchDaemons/com.nullmoth.bootguard.plist')).write_text('test copy\n')
            Path(c.p(KC)).parent.mkdir(parents=True, exist_ok=True)
            Path(c.p(KC)).write_text('collection of the nullmoth step\n')
        else:
            print('   NullMoth\'s installer will say "Done. Reboot now": do not, the steps after it are not done. Its "Undo" is not for this install either: rollback.sh is')
            c.run(['/bin/bash', c.pkgroot / 'install.sh'])
        if os.path.lexists(c.p(EXT + '/NMXAudio.kext')):
            rmtree(c.p(EXT + '/NMXAudio.kext'))

    def check(self):
        c = self.ctx
        files = MANIFEST['installed_files']
        got = describe(c.p(GB + '/nvmtl/libvulkan_nouveau.dylib'))
        if got != files['nvk_in'][:16]:
            return f'libvulkan_nouveau.dylib is {got}, not the one of the 2.6.6 package'
        if not os.path.isdir(c.p(EXT + '/NVRM.kext')):
            return 'NVRM.kext was not installed'
        if os.path.lexists(c.p(EXT + '/NMXAudio.kext')):
            return 'NMXAudio.kext is still there'
        return None


class Graphics(Step):
    name = 'graphics'
    what = 'WhateverXe Graphics 0.4.0, the official pkg: the Intel kexts and bundles (modified Apple drivers, signed by its authors)'
    touches = [EXT + '/AppleIntelTGLCompat.kext', EXT + '/AppleIntelTGLGraphics.kext', EXT + '/AppleIntelTGLGraphicsFramebuffer.kext',
               GB + '/AppleIntelTGLGraphicsGLDriver.bundle', GB + '/AppleIntelTGLGraphicsMTLDriver.bundle', GB + '/AppleIntelTGLGraphicsVADriver.bundle',
               GB + '/XeCompilerAdapter.bundle', GB + '/XeOpenCL', '/Library/Preferences/FeatureFlags/Domain/CoreMedia.plist', KC]

    def package(self):
        return self.ctx.dl / MANIFEST['downloads']['graphics']['file']

    def preflight(self):
        d = MANIFEST['downloads']['graphics']
        if not self.package().exists():
            return [f'{self.package()} is missing: run fetch']
        if sha256(self.package()) != d['sha256']:
            return [f'{self.package()} does not have the expected hash']
        return []

    def detail(self):
        return [f'runs installer -pkg {self.package().name}; its postinstall sets AllowOnePassMetalScaling false for the whole system and rebuilds the auxiliary collection']

    def run(self):
        c = self.ctx
        if c.fake:
            with tempfile.TemporaryDirectory() as t:
                expanded = Path(t) / 'x'
                subprocess.run(['/usr/sbin/pkgutil', '--expand-full', str(self.package()), str(expanded)], check=True)
                for payload in sorted(expanded.glob('*/Payload')):
                    component = payload.parent.name.lower()
                    if 'common' in component or 'tahoe' in component:
                        subprocess.run(['/usr/bin/ditto', str(payload), c.root], check=True)
            Path(c.p(KC)).write_text('collection of the graphics step\n')
        else:
            c.run(['/usr/sbin/installer', '-pkg', self.package(), '-target', '/'])

    def check(self):
        c = self.ctx
        got = describe(c.p(METAL))
        if got != MANIFEST['installed_files']['graphics_metal_stock'][:16]:
            return f'the Metal driver is {got}, not the one of Graphics 0.4.0'
        for t in self.touches[:6]:
            if not os.path.isdir(c.p(t)):
                return f'{t} was not installed'
        return None


class Posh(Step):
    name = 'posh'
    what = 'Two bytes in the installed Intel Metal driver, so that WindowServer stops losing 96 KiB per frame: the script of the Graphics fork'
    touches = [GB + '/AppleIntelTGLGraphicsMTLDriver.bundle']

    def script(self):
        return self.ctx.dl / MANIFEST['downloads']['posh_patch']['file']

    def preflight(self):
        s = self.script()
        if not s.exists():
            return [f'{s} is missing: run fetch']
        recorded = Path(str(s) + '.sha256')   # fetch writes it when it takes the latest of the branch
        if sha256(s) != (recorded.read_text().strip() if recorded.exists() else MANIFEST['downloads']['posh_patch']['sha256']):
            return [f'{s} does not have the expected hash']
        return []

    def detail(self):
        return ['runs posh_patch.sh dryrun, then patch; it refuses any file but the one of Graphics 0.4.0, and the patched file is never published']

    def env(self):
        c = self.ctx
        env = {'POSH_GO': '1', 'POSH_BACKUP': str(c.backup / 'posh')}
        if c.fake:
            env['POSH_BUNDLE'] = c.p(GB + '/AppleIntelTGLGraphicsMTLDriver.bundle')
        return env

    def run(self):
        c = self.ctx
        c.run(['/bin/bash', self.script(), 'dryrun'], env=self.env())
        c.run(['/bin/bash', self.script(), 'patch'], env=self.env())

    def check(self):
        got = describe(self.ctx.p(METAL))
        if got != MANIFEST['installed_files']['graphics_metal_patched'][:16]:
            return f'the Metal driver is {got}, not the patched one'
        return None


class NGShim(Step):
    name = 'ngshim'
    what = 'NGShim of umeow0716 with three fixes of JulioNectar, in place of impostor.dylib of Graphics, the bridge of the Intel Metal driver'
    touches = [IMPOSTOR]
    needs_out = ['bundle/impostor.dylib']

    def preflight(self):
        c = self.ctx
        files = MANIFEST['installed_files']
        if not os.path.exists(c.p(IMPOSTOR)):
            return []  # the graphics step comes first
        if sha256(c.p(IMPOSTOR)) != files['graphics_impostor_stock']:
            return ['impostor.dylib is not the one of Graphics 0.4.0']
        if sha256(c.p(DESCRIPTOR)) != files['graphics_descriptor']:
            return ['descriptor.dylib is not the one NGShim was compared with']
        return []

    def detail(self):
        return ['after posh, whose checks want the bundle as Graphics sealed it: from here a deep check of the bundle can fail, and the blend test of verify is the check']

    def run(self):
        c = self.ctx
        problems = self.preflight()
        if problems:
            raise Stop(problems[0])
        # the 0.4.0 impostor exports one symbol that NGShim does not: nothing else may use it
        others = subprocess.run(['/usr/bin/grep', '-l', '-a', '-r', 'xe_install_descriptor_placement', c.p(GB), c.p(EXT)], capture_output=True, text=True, errors='replace').stdout.split('\n')
        others = [x for x in others if x and x != c.p(IMPOSTOR)]
        if others:
            raise Stop('something else uses the export of the 0.4.0 impostor, NGShim cannot replace it: ' + others[0])
        put_file(c, c.out / 'bundle/impostor.dylib', c.p(IMPOSTOR))

    def check(self):
        c = self.ctx
        if sha256(c.p(IMPOSTOR)) != sha256(c.out / 'bundle/impostor.dylib'):
            return 'impostor.dylib is not the build'
        return None


class NvrmKexts(Step):
    name = 'nvrm-kexts'
    what = 'NVRM, NVRMFB, NVAccel and NVRMAGDC built from nvidia-macos-driver acer/current over those of the package'
    KEXTS = ['NVRM', 'NVRMFB', 'NVAccel', 'NVRMAGDC']
    touches = [EXT + f'/{k}.kext' for k in KEXTS] + ['/Library/NullMoth/kexts/26']
    needs_out = [f'{k}.kext/Contents/MacOS/{k}' for k in KEXTS]

    def run(self):
        c = self.ctx
        for k in self.KEXTS:
            put_tree(c, c.out / f'{k}.kext', c.p(EXT + f'/{k}.kext'))
        # NullMoth keeps one accelerator per macOS for its own use after an upgrade: it must not be older than the one installed
        cache = c.p('/Library/NullMoth/kexts/26')
        put_tree(c, c.out / 'NVAccel.kext', cache + '/NVAccel.kext')
        sums = subprocess.run(['/usr/bin/find', 'NVAccel.kext', '-type', 'f', '-exec', '/usr/bin/shasum', '-a', '256', '{}', ';'], cwd=cache, capture_output=True, text=True, check=True).stdout
        Path(cache + '/SHA256SUMS').write_text(sums)

    def check(self):
        c = self.ctx
        for k in self.KEXTS:
            rel = f'{k}.kext/Contents/MacOS/{k}'
            if sha256(c.p(EXT + '/' + rel)) != sha256(c.out / rel):
                return f'{k} in {EXT} is not the build'
            if os.path.exists(c.p(EXT + f'/{k}.kext/Contents/_CodeSignature')):
                return f'{k} still has the signature of the package'
        return None


class Plugin(Step):
    name = 'plugin'
    what = 'The Metal plugin and the shader translator built from acer/current, in the NullMoth bundle, which is then sealed again'
    touches = [NVMTL]
    needs_out = ['bundle/NVMTLDriver', 'bundle/libnvmtl_translate.dylib']

    def run(self):
        c = self.ctx
        macos = c.p(NVMTL + '/Contents/MacOS/')
        put_file(c, c.out / 'bundle/libnvmtl_translate.dylib', macos + 'libnvmtl_translate.dylib')
        put_file(c, c.out / 'bundle/NVMTLDriver', macos + 'NVMTLDriver')
        resign_nvmtl(c)

    def check(self):
        c = self.ctx
        if sha256(c.p(NVMTL + '/Contents/MacOS/libnvmtl_translate.dylib')) != sha256(c.out / 'bundle/libnvmtl_translate.dylib'):
            return 'the translator in the bundle is not the build'
        if subprocess.run(['/usr/bin/codesign', '--verify', c.p(NVMTL)], capture_output=True).returncode:
            return 'the seal of the bundle does not verify'
        return None


class Decoder(Step):
    name = 'decoder'
    what = 'The video decoders of nvenc acer/current in place of the two of NullMoth; they also add VP9 and AV1, and take over the Aerial wallpaper'
    touches = [NVMTL, NVMTL_CONF]
    needs_out = ['bundle/libnvencvt.dylib']

    def preflight(self):
        c = self.ctx
        macos = c.p(NVMTL + '/Contents/MacOS/')
        if not os.path.exists(macos + 'libnvdec_h264.dylib'):
            return []  # the nullmoth step comes first
        for name, want in MANIFEST['installed_files']['nullmoth_decoders'].items():
            if os.path.islink(macos + name):
                return [f'{name} is a link already: the decoders were replaced before']
            if sha256(macos + name) != want:
                return [f'{name} is not the one of the NullMoth package']
        return []

    def run(self):
        c = self.ctx
        problems = self.preflight()
        if problems:
            raise Stop(problems[0])
        macos = c.p(NVMTL + '/Contents/MacOS/')
        put_file(c, c.out / 'bundle/libnvencvt.dylib', macos + 'libnvdec_h264.dylib')
        put_file(c, c.out / 'bundle/libnvencvt.dylib', macos + 'libnvencvt.dylib')   # the plugin loads it by this name for the processes in NVMTL_NVENCVT
        os.unlink(macos + 'libnvdec_hevc.dylib')
        os.symlink('libnvdec_h264.dylib', macos + 'libnvdec_hevc.dylib')
        resign_nvmtl(c)
        conf = c.p(NVMTL_CONF)
        text = Path(conf).read_text() if os.path.exists(conf) else ''
        if NVENCVT_LINE not in text.splitlines():
            Path(conf).write_text(text + NVENCVT_LINE + '\n')

    def check(self):
        c = self.ctx
        macos = c.p(NVMTL + '/Contents/MacOS/')
        for name in ('libnvdec_h264.dylib', 'libnvencvt.dylib'):
            if sha256(macos + name) != sha256(c.out / 'bundle/libnvencvt.dylib'):
                return f'{name} is not the build'
        if os.readlink(macos + 'libnvdec_hevc.dylib') != 'libnvdec_h264.dylib':
            return 'libnvdec_hevc.dylib does not point to libnvdec_h264.dylib'
        if NVENCVT_LINE not in Path(c.p(NVMTL_CONF)).read_text().splitlines():
            return 'nvrm610.conf does not send the wallpaper to this decoder'
        return None


class NvkBinds(Step):
    name = 'nvk-binds'
    what = 'NVK without its 2940 weak binds that dyld searches in vain: new apps start the Metal driver faster'
    touches = [GB + '/nvmtl/libvulkan_nouveau.dylib']

    def run(self):
        c = self.ctx
        lib = c.p(self.touches[0])
        files = MANIFEST['installed_files']
        if sha256(lib) != files['nvk_in']:
            raise Stop('libvulkan_nouveau.dylib is not the one of the 2.6.6 package')
        with tempfile.TemporaryDirectory() as t:
            new = Path(t) / 'libvulkan_nouveau.dylib'
            print('   ' + subprocess.run([sys.executable, '-I', str(HERE / 'drop_flat_weak_binds.py'), lib, str(new)], check=True, capture_output=True, text=True).stdout.strip())
            if sha256(new) != files['nvk_patched_unsigned']:
                raise Stop(f'the patched library is {sha256(new)[:16]}, expected {files["nvk_patched_unsigned"][:16]}')
            subprocess.run(['/usr/bin/codesign', '-f', '-s', '-', '--identifier', files['nvk_identifier'], str(new)], check=True, capture_output=True)
            put_file(c, new, lib)

    def check(self):
        lib = self.ctx.p(self.touches[0])
        if subprocess.run(['/usr/bin/codesign', '--verify', lib], capture_output=True).returncode:
            return 'the signature of libvulkan_nouveau.dylib does not verify'
        return None if sha256(lib) != MANIFEST['installed_files']['nvk_in'] else 'libvulkan_nouveau.dylib did not change'


class LatSOF(Step):
    name = 'latsof'
    what = 'LatSOFAudio, for the internal microphone: the firmware of Sound Open Firmware is inside the kext'
    touches = [EXT + '/LatSOFAudio.kext']
    needs_out = ['LatSOFAudio.kext/Contents/MacOS/LatSOFAudio']

    def run(self):
        put_tree(self.ctx, self.ctx.out / 'LatSOFAudio.kext', self.ctx.p(self.touches[0]))

    def check(self):
        c = self.ctx
        rel = 'LatSOFAudio.kext/Contents/MacOS/LatSOFAudio'
        return None if sha256(c.p(EXT + '/' + rel)) == sha256(c.out / rel) else 'LatSOFAudio in /Library/Extensions is not the build'


class PanelHiDPI(Step):
    name = 'hidpi-panel'
    what = 'The display override that makes macOS offer HiDPI modes on the CSOT panel, up to "looks like" 1600x900. WindowServer reads it at the next boot'
    touches = [PANEL_OVERRIDE]

    def run(self):
        c = self.ctx
        os.makedirs(os.path.dirname(c.p(PANEL_OVERRIDE)), exist_ok=True)
        put_file(c, HERE / 'overrides/DisplayVendorID-e77/DisplayProductID-1513', c.p(PANEL_OVERRIDE), mode=0o644)

    def check(self):
        return None if sha256(self.ctx.p(PANEL_OVERRIDE)) == sha256(HERE / 'overrides/DisplayVendorID-e77/DisplayProductID-1513') else 'the panel override is not the one of this repository'


class AuxKC(Step):
    name = 'auxkc'
    what = 'The auxiliary kernel collection again, from all of /Library/Extensions: swapped in only if it holds every driver'
    touches = [KC]

    def detail(self):
        return ['needs: ' + ', '.join(MANIFEST['aux_collection_ids'])]

    def run(self):
        c = self.ctx
        if c.fake:
            Path(c.p(KC)).write_text('collection of the auxkc step\n')
            return
        new = KC + '.anv-new'
        log = c.logs / f'kmutil-{datetime.now().strftime("%Y%m%d-%H%M%S")}.log'
        cmd = ['/usr/bin/kmutil', 'create', '-n', 'aux', '--volume-root', '/', '--allow-missing-kdk']
        if os.path.exists(KERNEL):
            cmd += ['--kernel', KERNEL]
        cmd += ['-B', KB, '-S', KS, '--repository', EXT, '-A', new, '-z']
        if os.path.exists(new):
            os.unlink(new)
        print('   rebuilding the auxiliary collection, 1 or 2 minutes')
        with open(log, 'w') as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode:
            raise Stop(f'kmutil failed, the collection did not change: see {log}')
        inspected = subprocess.run(['/usr/bin/kmutil', 'inspect', '-a', 'x86_64', '-A', new], capture_output=True, text=True)
        if inspected.returncode:
            os.unlink(new)
            raise Stop('cannot read the new collection; the old one stays')
        for ident in MANIFEST['aux_collection_ids']:
            if ident == 'com.hackintosh.LatSOFAudio' and 'latsof' in (c.args.skip or []):
                continue
            if not listed(inspected.stdout, ident):
                os.unlink(new)
                raise Stop(f'{ident} is not in the new collection; the old one stays')
        os.replace(new, KC)

    def check(self):
        return None if os.path.isfile(self.ctx.p(KC)) else 'no auxiliary collection'


class NitroSense(Step):
    name = 'nitrosense'
    what = 'nitrod, nitroctl and NitroSense.app: fans, modes, charge limit. It starts at the next boot, because it needs NitroEC from the EFI'
    touches = [NITRO_DIR, NITRO_PLIST, NITRO_APP]
    needs_out = ['nitrosense/nitrod', 'nitrosense/nitroctl', 'nitrosense/NitroSense.app/Contents/MacOS/NitroSense']

    def run(self):
        c = self.ctx
        folder = c.p(NITRO_DIR)
        os.makedirs(folder, exist_ok=True)
        put_file(c, c.out / 'nitrosense/nitrod', folder + '/nitrod')
        put_file(c, c.out / 'nitrosense/nitroctl', folder + '/nitroctl')
        plist = {'Label': 'com.nitrosense.nitrod', 'ProgramArguments': [NITRO_DIR + '/nitrod'], 'RunAtLoad': True, 'KeepAlive': True,
                 'ThrottleInterval': 10, 'StandardErrorPath': '/var/log/nitrod.log'}
        os.makedirs(os.path.dirname(c.p(NITRO_PLIST)), exist_ok=True)
        with open(c.p(NITRO_PLIST), 'wb') as f:
            plistlib.dump(plist, f)
        os.chmod(c.p(NITRO_PLIST), 0o644)
        if not c.fake:
            os.chown(c.p(NITRO_PLIST), 0, 0)
        app = c.p(NITRO_APP)
        if os.path.lexists(app):
            rmtree(app)
        os.makedirs(os.path.dirname(app), exist_ok=True)
        subprocess.run(['/usr/bin/ditto', str(c.out / 'nitrosense/NitroSense.app'), app], check=True)

    def check(self):
        c = self.ctx
        if sha256(c.p(NITRO_DIR + '/nitrod')) != sha256(c.out / 'nitrosense/nitrod'):
            return 'nitrod is not the build'
        return None if os.path.isdir(c.p(NITRO_APP)) else 'NitroSense.app was not copied'


STEPS = [NullMoth, Graphics, Posh, NGShim, NvrmKexts, Plugin, Decoder, NvkBinds, LatSOF, PanelHiDPI, AuxKC, NitroSense]


# ---------------------------------------------------------------- backups

def open_backup(ctx):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    ctx.backup = Path(ctx.p(f'{STATE_DIR}/backup-{stamp}'))
    (ctx.backup / 'files').mkdir(parents=True)
    if not ctx.fake:
        os.chmod(ctx.backup, 0o700)
    shutil.copyfile(HERE / 'rollback.sh', ctx.backup / 'rollback.sh')
    os.chmod(ctx.backup / 'rollback.sh', 0o755)
    return ctx.backup


def snapshot(ctx, step):
    """Each path as it is before the step, or the note that it was not there. rollback.sh reads this journal from the bottom up.
    A step that already has its copies keeps them: it stopped half way, and the copies are of before it first ran.
    The lines go in once every copy is made, so a step with lines in the journal has all its copies."""
    journal = ctx.backup / 'journal.tsv'
    if journal.exists() and any(line.startswith(step.name + '\t') for line in journal.read_text().splitlines()):
        return
    folder = ctx.backup / 'files' / step.name
    if folder.exists():
        shutil.rmtree(folder)   # the copies of a run that did not finish them
    lines = []
    for path in step.touches:
        real = ctx.p(path)
        if os.path.islink(real):
            raise Stop(f'{path} is a symbolic link, which a clean install does not have and rollback could not put back')
        if os.path.lexists(real):
            dest = folder / path.lstrip('/')
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['/usr/bin/ditto', real, str(dest)], check=True)
            lines.append(f'{step.name}\t{path}\tpresent\n')
        else:
            lines.append(f'{step.name}\t{path}\tabsent\n')
    with open(journal, 'a') as f:
        f.write(''.join(lines))
        f.flush()
        os.fsync(f.fileno())


# ---------------------------------------------------------------- commands

def machine_problems(ctx):
    """Read only. Returns (blocking, notes): sentences."""
    blocking, notes = [], []
    tested = MANIFEST['tested']
    if ctx.fake:
        return blocking, notes
    build = subprocess.run(['/usr/bin/sw_vers', '-buildVersion'], capture_output=True, text=True).stdout.strip()
    version = subprocess.run(['/usr/bin/sw_vers', '-productVersion'], capture_output=True, text=True).stdout.strip()
    if build not in tested['macos_builds']:
        blocking.append(f'macOS {version} ({build}) is not what was tested ({tested["macos_version"]}, {", ".join(tested["macos_builds"])}). '
                        'WhateverXe and Graphics check the kernel themselves, but nothing here was ever run on this build: --any-build goes ahead anyway')
    else:
        notes.append(f'macOS {version} ({build}): the tested build')
    pci = subprocess.run(['/usr/sbin/ioreg', '-r', '-c', 'IOPCIDevice', '-d', '1'], capture_output=True, text=True, errors='replace').stdout
    for vendor, device in tested['pci_ids'].items():
        needle = f'<{device[2:4].lower()}{device[:2].lower()}0000>'
        if needle not in pci:
            blocking.append(f'no PCI device {vendor}:{device}: this does not look like the ANV15-52 these scripts are for; --any-machine goes ahead anyway')
    csr = subprocess.run(['/usr/bin/csrutil', 'status'], capture_output=True, text=True).stdout
    if 'status: enabled.' in csr or 'Filesystem Protections: enabled' in csr or 'Kext Signing: enabled' in csr:
        blocking.append('SIP is on: this system was not started from the OpenCore of this repository (csr-active-config 430A0000)')
    bootargs = subprocess.run(['/usr/sbin/sysctl', '-n', 'kern.bootargs'], capture_output=True, text=True).stdout
    for needed in ('amfi_get_out_of_my_way=0x1', 'amfi=0x80', 'ipc_control_port_options=0'):
        if needed not in bootargs:
            blocking.append(f'boot-args without {needed}: this system was not started from the OpenCore of this repository')
    if subprocess.run(['/usr/bin/xcrun', '--show-sdk-path'], capture_output=True).returncode:
        notes.append('no Command Line Tools: xcode-select --install, then again')
    return blocking, notes


def existing(ctx):
    found = []
    for cls in STEPS:
        for path in cls.touches:
            if path != KC and os.path.lexists(ctx.p(path)) and path not in found:
                found.append(path)
    return found


def cmd_doctor(ctx):
    blocking, notes = machine_problems(ctx)
    for n in notes:
        print('ok    ' + n)
    for b in blocking:
        print('STOP  ' + b)
    total, used, free = shutil.disk_usage(ctx.work if ctx.work.exists() else Path.home())
    print(f'{"ok   " if free > 6e9 else "STOP "} {free / 1e9:.0f} GB free; fetch and build need about 3 GB in {ctx.work}')
    power = subprocess.run(['/usr/bin/pmset', '-g', 'batt'], capture_output=True, text=True).stdout.splitlines()[:1]
    print(f'note  {power[0] if power else "power source unknown"}; plug the charger in before install')
    found = existing(ctx)
    print(f'note  {len(found)} of the paths install writes exist already' + (': ' + ', '.join(found[:6]) + (' ...' if len(found) > 6 else '') if found else ''))
    print('note  python ' + sys.version.split()[0] + ', clang ' + (subprocess.run(['/usr/bin/clang', '--version'], capture_output=True, text=True).stdout.split('\n')[0] or 'missing'))
    return 1 if blocking else 0


def download(ctx, name, spec=None):
    d = spec or MANIFEST['downloads'][name]
    ctx.dl.mkdir(parents=True, exist_ok=True)
    path = ctx.dl / d['file']
    if path.exists() and 'sha256' in d and sha256(path) == d['sha256']:
        return path
    print(f'  downloading {d["file"]}')
    req = urllib.request.Request(d['url'], headers={'User-Agent': 'curl/8'})
    with urllib.request.urlopen(req, timeout=600) as r, open(str(path) + '.part', 'wb') as f:
        shutil.copyfileobj(r, f)
    os.replace(str(path) + '.part', path)
    if 'sha256' in d and sha256(path) != d['sha256']:
        path.unlink()
        raise Stop(f'{d["file"]}: not the expected hash; removed. Upstream may have replaced it: do not change the manifest without looking at why')
    return path


def git(cwd, *args, check=True):
    r = subprocess.run(['/usr/bin/git', '-C', str(cwd), *args], capture_output=True, text=True, errors='replace', env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
    if check and r.returncode:
        raise Stop(f'git {" ".join(args)[:80]} failed in {cwd}: {r.stderr[-300:]}')
    return r.stdout.strip()


def checkout(path, url, rev, commit=None, sparse=None, full=False):
    """A pinned commit in its own folder. A hash that differs stops; a folder that is already right is left alone."""
    if (path / '.git').exists() and commit and git(path, 'rev-parse', 'HEAD', check=False) == commit:
        return
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    git(path, 'init', '-q')
    git(path, 'remote', 'add', 'origin', url)
    print(f'  {path.name}: {url} at {(commit or rev)[:12]}')
    if full:
        git(path, 'fetch', '-q', '--filter=blob:none', 'origin')
        git(path, 'fetch', '-q', '--filter=blob:none', 'origin', commit)
    else:
        git(path, 'fetch', '-q', '--depth', '1', '--filter=blob:none', 'origin', rev)
    if sparse:
        git(path, 'sparse-checkout', 'set', *sparse)
    git(path, 'checkout', '-q', commit if full else 'FETCH_HEAD')
    head = git(path, 'rev-parse', 'HEAD')
    if commit and head != commit:
        raise Stop(f'{path.name} is at {head[:12]}, expected {commit[:12]}')


def remote_head(ctx, url, ref):
    head = git(ctx.work, 'ls-remote', url, 'refs/heads/' + ref).split()
    if not head:
        raise Stop(f'no branch {ref} on {url}')
    return head[0]


def fetch_posh(ctx):
    """The script of the Graphics fork, from the same branch as the others. Its hash goes next to it, and install checks that."""
    d = dict(MANIFEST['downloads']['posh_patch'])
    if not ctx.args.tested:
        tested = re.search(r'/([0-9a-f]{40})/', d['url'])[1]
        head = remote_head(ctx, GRAPHICS_FORK, 'acer/current')
        if head != tested:
            d['url'] = d['url'].replace(tested, head)
            del d['sha256']
    path = download(ctx, 'posh_patch', d)
    Path(str(path) + '.sha256').write_text(sha256(path) + '\n')


def cmd_fetch(ctx):
    if os.geteuid() == 0:
        raise Stop('fetch and build run as your user, without sudo')
    if ' ' in str(ctx.work):
        raise Stop(f'the makefiles of the drivers do not take a folder with spaces: choose another one with --work, not {ctx.work}')
    for sub in (ctx.src, ctx.deps, ctx.logs):
        sub.mkdir(parents=True, exist_ok=True)
    tar = download(ctx, 'nullmoth')
    sums = ctx.pkgroot / 'SHA256SUMS'
    if not sums.exists() or sha256(sums) != MANIFEST['downloads']['nullmoth']['sums_sha256']:
        if ctx.pkgroot.exists():
            shutil.rmtree(ctx.pkgroot)
        ctx.pkgroot.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar) as t:
            t.extractall(ctx.pkgroot.parent)
        if sha256(sums) != MANIFEST['downloads']['nullmoth']['sums_sha256']:
            raise Stop('the NullMoth package does not hold the SHA256SUMS this manifest expects')
    r = subprocess.run(['/usr/bin/shasum', '-a', '256', '--strict', '--quiet', '-c', 'SHA256SUMS'], cwd=ctx.pkgroot, capture_output=True, text=True)
    if r.returncode:
        raise Stop(f'the NullMoth package does not match its SHA256SUMS: {r.stdout[-300:]}')
    download(ctx, 'graphics')
    fetch_posh(ctx)
    (ctx.deps / 'ngshim').mkdir(exist_ok=True)
    shutil.copyfile(download(ctx, 'ngshim_src'), ctx.deps / 'ngshim/ngshim.m')
    lilu = download(ctx, 'lilu_debug')
    shutil.copyfile(lilu, ctx.deps / 'lilu-debug.zip')
    if not (ctx.deps / 'lilu-debug/Lilu.kext').exists():
        with zipfile.ZipFile(lilu) as z:
            z.extractall(ctx.deps / 'lilu-debug')
    sof = MANIFEST['downloads']['sof']
    with tarfile.open(download(ctx, 'sof')) as t:
        data = t.extractfile(sof['member']).read()
    if hashlib.sha256(data).hexdigest() != sof['member_sha256']:
        raise Stop('the SOF firmware inside the archive is not the expected one')
    (ctx.deps / 'sof').mkdir(exist_ok=True)
    (ctx.deps / 'sof/sof-rpl.ri').write_bytes(data)
    mesa = MANIFEST['downloads']['mesa_include']
    include = ctx.deps / 'mesa-include'
    if not (include / mesa['check_member']).exists() or tree_sha256(include) != mesa['tree_sha256']:
        with tarfile.open(download(ctx, 'mesa_include')) as t:
            t.extractall(ctx.deps)
        if include.exists():
            shutil.rmtree(include)
        (ctx.deps / mesa['strip']).rename(include)
    if tree_sha256(include) != mesa['tree_sha256']:   # GitLab builds the archive on request, so the hash is of the files
        raise Stop('the Vulkan headers of Mesa are not the expected ones')
    for name in ('webkit_cmbase', 'webkit_vtdec', 'mt7920_patch', 'mt7920_ram', 'mtkbt_zip'):
        d = MANIFEST['downloads'][name]
        target = ctx.deps / d['dest']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(download(ctx, name), target)
    for name, d in MANIFEST['git_deps'].items():
        checkout(ctx.deps / name, d['url'], d.get('tag') or d['commit'], d.get('commit'), d.get('sparse'), d.get('full', False))
    newer = []
    for name, d in MANIFEST['forks'].items():
        commit = d['tested_commit'] if ctx.args.tested else remote_head(ctx, d['url'], d['ref'])
        checkout(ctx.src / name, d['url'], commit, commit)
        if commit != d['tested_commit']:
            newer.append(f'{name}: {d["ref"]} is at {commit[:12]}, last tested at {d["tested_commit"][:12]}')
    print(f'fetched into {ctx.work}: every hash as expected, and the {"commits last tested" if ctx.args.tested else "latest commit of each branch"}')
    for line in newer:
        print('NOTE  newer than what the status in README.md describes. ' + line)
    if newer:
        print('NOTE  to build exactly what was tested: fetch --tested')
    return 0


def cmd_build(ctx):
    if os.geteuid() == 0:
        raise Stop('fetch and build run as your user, without sudo')
    missing = [name for name in MANIFEST['forks'] if not (ctx.src / name / '.git').exists()]
    if missing:
        raise Stop(f'{missing[0]} is not there: run fetch first')
    env = dict(MANIFEST['build_env'], WORK=str(ctx.work))
    heads = fork_heads(ctx)
    forks = MANIFEST['forks']
    # These go into the binaries. For a commit that was tested they stay what they were, to give the same file; for a newer one they follow it
    if heads.get('nvenc') != forks['nvenc']['tested_commit']:
        env['NVENC_VERSION'] = 'v0.9.5-g' + heads['nvenc'][:7]
    for fork, key in (('WhateverXe', 'WHATEVERXE_DATE'), ('nvidia-macos-driver', 'NMHDA_DATE'), ('AppleALC', 'IDISPHDA_DATE')):
        if heads.get(fork) != forks[fork]['tested_commit']:
            env[key] = git(ctx.src / fork, 'show', '-s', '--format=%cs', 'HEAD')
    r = subprocess.run(['/bin/bash', str(HERE / 'build.sh'), *ctx.args.stages], env=dict(os.environ, **env))
    if r.returncode:
        raise Stop('the build stopped: the line above says where')
    return write_out_manifest(ctx)


def sha256_without_uuid(path):
    data = bytearray(Path(path).read_bytes())
    if data[:4] == b'\xcf\xfa\xed\xfe':
        offset = 32
        for _ in range(struct.unpack_from('<I', data, 16)[0]):
            cmd, size = struct.unpack_from('<II', data, offset)
            if cmd == 0x1b:  # LC_UUID
                data[offset + 8:offset + 24] = bytes(16)
                break
            offset += size
    return hashlib.sha256(data).hexdigest()


def fork_heads(ctx):
    """The commit of each fork as fetch left it."""
    return {name: git(ctx.src / name, 'rev-parse', 'HEAD') for name in MANIFEST['forks'] if (ctx.src / name / '.git').exists()}


def against_tested(rel, path, heads):
    tested = MANIFEST['tested_binaries'].get(rel)
    if not tested:
        return 'no reference'
    newer = [f for f in ARTIFACT_FORKS.get(rel, []) if f in heads and heads[f] != MANIFEST['forks'][f]['tested_commit']]
    if newer:
        return 'newer than what was tested: ' + ', '.join(f'{f} at {heads[f][:12]}' for f in newer)
    got = sha256(path)
    if got == tested['sha256']:
        return 'the same file'
    if tested.get('sha256_without_uuid') == sha256_without_uuid(path):
        return 'the same but for the UUID: ' + tested.get('note', '')
    if tested.get('reference_sha256') == got:
        return 'as the reference build: ' + tested.get('note', '')
    if tested.get('reference_sha256_without_uuid') and tested['reference_sha256_without_uuid'] == sha256_without_uuid(path):
        return 'as the reference build but for the UUID: ' + tested.get('note', '')
    return 'DIFFERENT: another compiler or SDK, see postinstall/README.md'


def write_out_manifest(ctx):
    built = {}
    for rel in ARTIFACTS:
        path = ctx.out / rel
        if path.exists():
            built[rel] = sha256(path)
    heads = fork_heads(ctx)
    (ctx.out / 'manifest.json').write_text(json.dumps({'date': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'forks': heads, 'files': built}, indent=1) + '\n')
    print('Each file against the one tested on the reference machine:')
    for rel in ARTIFACTS:
        print(f'{rel:58} {built.get(rel, "not built")[:16]:16}  {against_tested(rel, ctx.out / rel, heads) if rel in built else ""}')
    missing = [r for r in ARTIFACTS if r not in built]
    if missing:
        print('not built yet: ' + ', '.join(missing))
    return 0


def efi_problems(ctx):
    """Without these six kexts no EFI can start the system that install leaves: better to find out now."""
    manifest = ctx.out_manifest()
    problems = []
    for rel in EFI_ARTIFACTS:
        if not (ctx.out / rel).exists():
            problems.append(f'{rel} is not built, and the EFI needs it: run build')
        elif not manifest or manifest['files'].get(rel) != sha256(ctx.out / rel):
            problems.append(f'{rel} changed since the build recorded it')
    return problems


def plan_lines(ctx):
    """The dry run: every problem, every path. Returns the list of things that would stop install."""
    stops = efi_problems(ctx)
    manifest = ctx.out_manifest()
    done = ctx.read_state().get('done', {})
    for i, cls in enumerate(STEPS, 1):
        step = cls(ctx)
        print(f'\n== {i}/{len(STEPS)} {step.name}: {step.what}')
        if step.name in done:
            print('   done already')
            continue
        for line in step.detail():
            print('   ' + line)
        for rel in step.needs_out:
            if not (ctx.out / rel).exists():
                stops.append(f'{step.name}: {rel} is not built')
            elif not manifest or manifest['files'].get(rel) != sha256(ctx.out / rel):
                stops.append(f'{step.name}: {rel} is not the file the last build recorded')
            else:
                print(f'   new   {rel}: {sha256(ctx.out / rel)[:16]}')
        for problem in step.preflight():
            stops.append(f'{step.name}: {problem}')
        for path in step.touches:
            state = describe(ctx.p(path))
            print(f'   {"new" if state == "absent" else "keeps a copy, replaces"} {path}' + ('' if state == 'absent' else f' ({state})'))
    return stops


def cmd_plan(ctx):
    print('Nothing is changed by this command. Each step below saves what it replaces in ' + STATE_DIR + '/backup-<date>.')
    stops = plan_lines(ctx)
    blocking, notes = machine_problems(ctx)
    found = existing(ctx)
    state = ctx.read_state()
    print()
    for n in notes:
        print('ok    ' + n)
    for s in blocking + stops:
        print('STOP  ' + s)
    if found and not state.get('done'):
        print(f'STOP  {len(found)} of these paths exist and were not put there by this script: this is for a clean install. --allow-existing replaces them, with copies.')
    print('\nThe EFI of the finished system goes on the USB stick before install --go: docs/INSTALL.md. After it the Apple Intel driver is in /Library, and it needs WhateverXe in the EFI.')
    return 0


def cmd_install(ctx):
    args = ctx.args
    if not ctx.go:
        print('Without --go nothing is done: this is the plan.\n')
        return cmd_plan(ctx)
    if not ctx.fake and os.geteuid() != 0:
        raise Stop('install needs sudo: sudo python3 postinstall/postinstall.py install --go')
    blocking, notes = machine_problems(ctx)
    for b in blocking:
        if 'is not what was tested' in b and args.any_build:
            print('NOTE  ' + b)
        elif 'no PCI device' in b and args.any_machine:
            print('NOTE  ' + b)
        else:
            raise Stop(b)
    state = ctx.read_state()
    found = existing(ctx)
    if found and not state.get('backup') and not args.allow_existing:
        raise Stop(f'{len(found)} of the paths install writes exist already, for example {found[0]}. This is for a clean install; --allow-existing replaces them, with copies')
    manifest = ctx.out_manifest()
    forks = (manifest or {}).get('forks', {})
    if state.get('forks', forks) != forks:
        raise Stop('an earlier run installed builds of other commits. Go back first, then install these: sudo python3 postinstall/postinstall.py rollback --go')
    wanted = [cls(ctx) for cls in STEPS if cls.name not in (args.skip or [])]
    problems = efi_problems(ctx)
    for step in wanted:
        if step.name in state.get('done', {}):
            continue
        for rel in step.needs_out:
            if not (ctx.out / rel).exists():
                problems.append(f'{rel} is not built: run build')
            elif not manifest or manifest['files'].get(rel) != sha256(ctx.out / rel):
                problems.append(f'{rel} changed since the build recorded it')
        problems += [f'{step.name}: {p}' for p in step.preflight()]
    if problems:
        raise Stop('nothing was changed:\n  ' + '\n  '.join(problems))
    state.setdefault('done', {})
    if state.get('backup') and os.path.isdir(ctx.p(state['backup'])):
        ctx.backup = Path(ctx.p(state['backup']))
        print('an earlier run stopped or was partly undone: going on with the same copies')
    else:
        open_backup(ctx)
    state['backup'] = str(ctx.backup)[len(ctx.root):]
    state['forks'] = forks
    ctx.write_state(state)
    backup = str(ctx.backup)[len(ctx.root):]
    print(f'copies of what is replaced: {backup}. Do not restart until this says it has finished, whatever a step prints.')
    half_way = (f'The steps before it are done, and this system is half way: do not restart. Run this again to go on from here, or go back with:\n'
                f'  sudo bash {backup}/rollback.sh --go')
    for i, step in enumerate(wanted, 1):
        print(f'\n== {i}/{len(wanted)} {step.name}: {step.what}')
        if step.name in state['done']:
            print('   done already')
            continue
        try:
            snapshot(ctx, step)
            step.run()
            wrong = step.check()
        except (Stop, subprocess.CalledProcessError, OSError, KeyboardInterrupt) as e:
            raise Stop(f'{step.name} failed: {str(e) or "interrupted"}\n{half_way}')
        if wrong:
            raise Stop(f'{step.name}: {wrong}\n{half_way}')
        state['done'][step.name] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        ctx.write_state(state)
        print('   ok')
    print('\nThe drivers are in /Library. Before you restart, the EFI of the finished system must be on the stick; if you have not done it yet, do it now:')
    print(f'  python3 efi/build_efi.py build --profile full --compiled {ctx.out}')
    print('  python3 efi/build_efi.py deploy --profile full --volume /Volumes/NAME --go')
    print('Then shut down, start \\EFI\\OC\\OpenCore.efi from rEFInd, and at the desktop: python3 postinstall/postinstall.py verify')
    print(f'To go back: sudo bash {backup}/rollback.sh --go')
    return 0


def cmd_rollback(ctx):
    state = ctx.read_state()
    if not state.get('backup'):
        raise Stop(f'no install recorded in {ctx.state_file}. If a rollback stopped half way, run rollback.sh again from the latest backup folder next to it')
    cmd = ['/bin/bash', ctx.p(state['backup']) + '/rollback.sh']
    if ctx.fake:
        cmd += ['--root', ctx.root]
    if ctx.go:
        cmd += ['--go']
        if not ctx.fake and os.geteuid() != 0:
            raise Stop('rollback needs sudo')
    if subprocess.run(cmd).returncode:
        raise Stop('rollback did not finish: the lines above say where')
    return 0


def cmd_state(ctx):
    manifest = ctx.out_manifest()
    state = ctx.read_state()
    print(f'recorded install: {state.get("backup", "none")}; steps done: {", ".join(state.get("done", {})) or "none"}')
    built = (manifest or {}).get('files', {})
    rows = [('NVRM', EXT + '/NVRM.kext/Contents/MacOS/NVRM', 'NVRM.kext/Contents/MacOS/NVRM'),
            ('NVRMFB', EXT + '/NVRMFB.kext/Contents/MacOS/NVRMFB', 'NVRMFB.kext/Contents/MacOS/NVRMFB'),
            ('NVAccel', EXT + '/NVAccel.kext/Contents/MacOS/NVAccel', 'NVAccel.kext/Contents/MacOS/NVAccel'),
            ('NVRMAGDC', EXT + '/NVRMAGDC.kext/Contents/MacOS/NVRMAGDC', 'NVRMAGDC.kext/Contents/MacOS/NVRMAGDC'),
            ('LatSOFAudio', EXT + '/LatSOFAudio.kext/Contents/MacOS/LatSOFAudio', 'LatSOFAudio.kext/Contents/MacOS/LatSOFAudio'),
            ('translator', NVMTL + '/Contents/MacOS/libnvmtl_translate.dylib', 'bundle/libnvmtl_translate.dylib'),
            ('decoder', NVMTL + '/Contents/MacOS/libnvdec_h264.dylib', 'bundle/libnvencvt.dylib'),
            ('nitrod', NITRO_DIR + '/nitrod', 'nitrosense/nitrod')]
    for label, path, rel in rows:
        cur = describe(ctx.p(path))
        print(f'{label:12} {cur:16} {"= the build" if built.get(rel, "").startswith(cur) else "built " + built[rel][:16] if rel in built else ""}')
    metal = describe(ctx.p(METAL))
    files = MANIFEST['installed_files']
    print(f'{"Metal driver":12} {metal:16} {"patched" if metal == files["graphics_metal_patched"][:16] else "stock 0.4.0" if metal == files["graphics_metal_stock"][:16] else ""}')
    bridge = describe(ctx.p(IMPOSTOR))
    print(f'{"Metal bridge":12} {bridge:16} {"NGShim" if built.get("bundle/impostor.dylib", "").startswith(bridge) or MANIFEST["tested_binaries"]["bundle/impostor.dylib"]["sha256"].startswith(bridge) else "of Graphics 0.4.0" if bridge == files["graphics_impostor_stock"][:16] else ""}')
    nvk = describe(ctx.p(GB + '/nvmtl/libvulkan_nouveau.dylib'))
    print(f'{"NVK":12} {nvk:16} {"without flat binds" if nvk == files["nvk_out"][:16] else "as in the 2.6.6 package" if nvk == files["nvk_in"][:16] else ""}')
    print(f'{"collection":12} {describe(ctx.p(KC)):16}')
    print(f'{"NVMTL seal":12} {"ok" if subprocess.run(["/usr/bin/codesign", "--verify", ctx.p(NVMTL)], capture_output=True).returncode == 0 else "does not verify, or absent"}')
    return 0


def listed(text, ident):
    """The whole bundle id: com.nullmoth.NVRM is not there because com.nullmoth.NVRMFB is."""
    return re.search(rf'(^|\W){re.escape(ident)}(\W|$)', text, re.M) is not None


def gpu_has_metal(displays, name):
    """In the block of that GPU of system_profiler, not in the one after it."""
    return any(name in block.splitlines()[0] and 'Metal Support: Metal' in block for block in displays.split('Chipset Model:')[1:])


def cmd_verify(ctx):
    """After a reboot into the full EFI. Reads, never writes. Prints what it saw; a pass here is not a stability result."""
    bad = 0

    def line(ok, text):
        nonlocal bad
        bad += not ok
        print(('ok    ' if ok else 'FAIL  ') + text)

    build = subprocess.run(['/usr/bin/sw_vers', '-buildVersion'], capture_output=True, text=True).stdout.strip()
    print(f'macOS build {build}; tested {", ".join(MANIFEST["tested"]["macos_builds"])}')
    loaded = subprocess.run(['/usr/bin/kmutil', 'showloaded', '--list-only'], capture_output=True, text=True).stdout
    for ident in MANIFEST['aux_collection_ids'] + ['org.b00t0x.WhateverXe', 'com.nullmoth.NMHDA', 'com.nitrosense.NitroEC', 'org.nullmoth.SMCNvidiaGPU', 'as.vit9696.AppleALC']:
        line(listed(loaded, ident), f'loaded {ident}')
    displays = subprocess.run(['/usr/sbin/system_profiler', 'SPDisplaysDataType'], capture_output=True, text=True).stdout
    line(gpu_has_metal(displays, 'Iris Xe'), 'Iris Xe with Metal')
    line(gpu_has_metal(displays, 'RTX 5050'), 'RTX 5050 with Metal')
    print('\n'.join('      ' + x.strip() for x in displays.splitlines() if re.search(r'Chipset Model|Metal Support|UI Looks like|Connection Type', x)))
    metal = describe(METAL)
    line(metal == MANIFEST['installed_files']['graphics_metal_patched'][:16], f'Metal driver patched for the POSH leak ({metal})')
    line(subprocess.run(['/usr/bin/codesign', '--verify', NVMTL], capture_output=True).returncode == 0, 'NVMTLDriver.bundle seal')
    with tempfile.TemporaryDirectory() as t:
        probe = Path(t) / 'blendtest'
        built_probe = subprocess.run(['/usr/bin/clang', '-fobjc-arc', str(HERE / 'blendtest.m'), '-framework', 'Metal', '-framework', 'Foundation', '-o', str(probe)], capture_output=True)
        line(built_probe.returncode == 0, 'blend test compiled; it needs the Command Line Tools')
        if built_probe.returncode == 0:
            result = subprocess.run([str(probe)], capture_output=True, text=True, errors='replace')
            line(result.returncode == 0, 'blend test on the Intel Metal device, in a new process; it does not say what WindowServer does')
            print('\n'.join('      ' + x for x in result.stdout.splitlines() if x.startswith(('device', 'blend', 'pixel'))))
    server = subprocess.run(['/bin/sh', '-c', 'ps -o lstart= -p $(pgrep -x WindowServer)'], capture_output=True, text=True).stdout.strip()
    print(f'      WindowServer started {server}: a logout does not restart it here, so anything it loads needs a reboot')
    gpu = subprocess.run(['/usr/sbin/sysctl', '-n', 'kern.nvgpustate'], capture_output=True, text=True).stdout.strip()
    print(f'      kern.nvgpustate: {gpu or "no answer: SMCNvidiaGPU is not bound"}')
    daemon = subprocess.run(['/bin/launchctl', 'print', 'system/com.nitrosense.nitrod'], capture_output=True, text=True)
    line(daemon.returncode == 0 and 'state = running' in daemon.stdout, 'nitrod running')
    print(f'{bad} line(s) failed. This says what is loaded, not that it is stable: the status table in README.md lists what to try by hand.')
    return 1 if bad else 0


class Tee:
    def __init__(self, stream, path):
        self.stream = stream
        self.file = open(path, 'a')

    def write(self, text):
        self.stream.write(text)
        self.file.write(text)

    def flush(self):
        self.stream.flush()
        self.file.flush()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command', choices=['doctor', 'fetch', 'build', 'plan', 'install', 'state', 'verify', 'rollback'])
    p.add_argument('stages', nargs='*', help='build only: which stages of build.sh')
    p.add_argument('--work', help='work folder, default ~/anv15-52-build')
    p.add_argument('--root', help='a copy of the system tree to work on instead of /')
    p.add_argument('--go', action='store_true', help='install, rollback: do it')
    p.add_argument('--allow-existing', action='store_true', help='install: replace what is there, with copies')
    p.add_argument('--any-build', action='store_true', help='install: go ahead on a macOS build never tried')
    p.add_argument('--any-machine', action='store_true', help='install: go ahead without the PCI ids of the ANV15-52')
    p.add_argument('--tested', action='store_true', help='fetch: the commits last tested, instead of the latest of each branch')
    p.add_argument('--skip', action='append', choices=[cls.name for cls in STEPS], help='install: leave out a step; can be repeated')
    args = p.parse_args()
    os.umask(0o022)   # sudo keeps the umask of the shell, and what root writes here is read by everyone
    ctx = Ctx(args)
    if ctx.work.exists():
        ctx.logs.mkdir(parents=True, exist_ok=True)
        if args.command in ('install', 'rollback') and args.go:
            log = ctx.logs / f'{args.command}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.log'
            sys.stdout = Tee(sys.stdout, log)
            print(f'log: {log}')
    commands = {'doctor': cmd_doctor, 'fetch': cmd_fetch, 'build': cmd_build, 'plan': cmd_plan, 'install': cmd_install, 'state': cmd_state, 'verify': cmd_verify, 'rollback': cmd_rollback}
    try:
        sys.exit(commands[args.command](ctx))
    except Stop as e:
        sys.exit(f'STOP: {e}')
    except KeyboardInterrupt:
        sys.exit('STOP: interrupted')


if __name__ == '__main__':
    main()
