#!/usr/bin/env python3
"""The install and rollback logic of postinstall.py on a fake system tree, with small stand-ins for the drivers. No sudo, no download.

  python3 tests/test_postinstall.py

--root keeps every write inside a temporary folder, and there kmutil, installer and launchctl do not run. What this shows: the order of the
steps, the refusals, the copies, the way back. What it cannot show: that the real drivers load. Needs macOS with the Command Line Tools,
for codesign, pkgbuild and clang.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'postinstall/postinstall.py'
REAL = json.loads((ROOT / 'postinstall/manifest.json').read_text())
KEXTS = ['NVRM', 'NVRMFB', 'NVAccel', 'NVRMAGDC']
FOR_EFI = ['NMHDA', 'NitroEC', 'SMCNvidiaGPU', 'WhateverXe', 'HybridPM', 'AppleALC', 'IDispHDA', 'AirportMtkWlan', 'SimpleMtkBtPatcher', 'BTLEAdvFixup', 'NMAppFree', 'USBDiskKeeper']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(root, ignore=()):
    """{relative path: content hash, or link target, or a mark for a folder}"""
    out = {}
    for dirpath, dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        if any(rel == i or rel.startswith(i + '/') for i in ignore):
            continue
        for d in dirs:
            p = os.path.join(dirpath, d)
            out[os.path.relpath(p, root)] = 'link ' + os.readlink(p) if os.path.islink(p) else 'folder'
        for f in files:
            p = os.path.join(dirpath, f)
            out[os.path.relpath(p, root)] = 'link ' + os.readlink(p) if os.path.islink(p) else sha(p)
    return out


def machine_code(path, tag):
    subprocess.run(['/usr/bin/clang', '-x', 'c', '-dynamiclib', '-o', str(path), '-'], input=f'const char *t = "{tag}"; int f(void) {{ return 1; }}'.encode(), check=True)
    subprocess.run(['/usr/bin/codesign', '-f', '-s', '-', str(path)], check=True, capture_output=True)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class Fixture:
    """A work folder as fetch and build would leave it, and a manifest with the hashes of these stand-ins."""

    def __init__(self):
        self.base = Path(tempfile.mkdtemp(prefix='anv-test-'))
        self.work = self.base / 'work'
        self.root = self.base / 'root'
        self.root.mkdir()
        out, dl, deps = self.work / 'out', self.work / 'dl', self.work / 'deps'
        for d in (out, dl, deps):
            d.mkdir(parents=True)
        for k in KEXTS + ['LatSOFAudio'] + FOR_EFI:
            write(out / f'{k}.kext/Contents/MacOS/{k}', f'built {k}\n')
            write(out / f'{k}.kext/Contents/Info.plist', f'plist {k}\n')
        (out / 'bundle').mkdir()
        machine_code(out / 'bundle/NVMTLDriver', 'plugin')
        machine_code(out / 'bundle/libnvmtl_translate.dylib', 'translator')
        machine_code(out / 'bundle/libnvencvt.dylib', 'decoder')
        (out / 'nvmtl').mkdir()
        machine_code(out / 'nvmtl/libvulkan_nouveau.dylib', 'nvk built here')
        write(out / 'nitrosense/nitrod', 'nitrod\n')
        write(out / 'nitrosense/nitroctl', 'nitroctl\n')
        write(out / 'nitrosense/NitroSense.app/Contents/MacOS/NitroSense', 'app\n')
        files = {}
        for rel in [f'{k}.kext/Contents/MacOS/{k}' for k in KEXTS + ['LatSOFAudio'] + FOR_EFI] + ['bundle/NVMTLDriver', 'bundle/libnvmtl_translate.dylib', 'bundle/libnvencvt.dylib', 'nvmtl/libvulkan_nouveau.dylib',
                                                                                         'nitrosense/nitrod', 'nitrosense/nitroctl', 'nitrosense/NitroSense.app/Contents/MacOS/NitroSense']:
            files[rel] = sha(out / rel)
        write(out / 'manifest.json', json.dumps({'files': files, 'forks': {'WhateverXe': 'a' * 40}}))

        # NullMoth's package: only what the steps read
        pkg = deps / 'nullmoth/pkgroot'
        for k in KEXTS:
            write(pkg / f'Library/Extensions/{k}.kext/Contents/MacOS/{k}', f'release {k}\n')
            write(pkg / f'Library/Extensions/{k}.kext/Contents/Info.plist', f'release plist {k}\n')
        write(pkg / 'Library/Extensions/NVRM.kext/Contents/_CodeSignature/CodeResources', 'release signature\n')
        write(pkg / 'Library/Extensions/NMXAudio.kext/Contents/MacOS/NMXAudio', 'the audio driver of the package\n')
        macos = pkg / 'Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS'
        macos.mkdir(parents=True)
        machine_code(macos / 'NVMTLDriver', 'release plugin')
        machine_code(macos / 'libnvmtl_translate.dylib', 'release translator')
        machine_code(macos / 'libnvdec_h264.dylib', 'release h264')
        machine_code(macos / 'libnvdec_hevc.dylib', 'release hevc')
        write(pkg / 'Library/GPUBundles/NVMTLDriver.bundle/Contents/Info.plist',
              '<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict><key>CFBundleExecutable</key><string>NVMTLDriver</string>'
              '<key>CFBundleIdentifier</key><string>com.nullmoth.NVMTLDriver</string></dict></plist>\n')
        nvk = write(pkg / 'Library/GPUBundles/nvmtl/libvulkan_nouveau.dylib', 'nvk\n')
        write(pkg / 'Library/GPUBundles/nvmtl/nvrm610.conf', 'NVMTL_RES2_WS=1\n')
        write(pkg / 'Library/GPUBundles/nvmtl-allow.txt', '*\n')
        write(pkg / 'Library/NullMoth/kexts/26/NVAccel.kext/Contents/MacOS/NVAccel', 'release NVAccel\n')
        # what NullMoth's installer writes beside the driver, and the nullmoth step removes
        write(pkg / 'Library/NullMoth/backlight.sh', 'backlight job\n')
        write(pkg / 'Library/LaunchDaemons/com.nullmoth.backlight.plist', 'backlight job\n')
        write(pkg / 'Library/NullMoth/added-boot-args', 'gfxrst=4\n')
        write(pkg / 'install.sh', '#!/bin/bash\nexit 1\n')
        sums = subprocess.run('find Library -type f -exec shasum -a 256 {} +', shell=True, cwd=pkg, capture_output=True, text=True, check=True).stdout
        write(pkg / 'SHA256SUMS', sums)
        with tarfile.open(dl / 'nullmoth.tar.gz', 'w:gz') as t:
            t.add(pkg, arcname='pkgroot')

        # Graphics: a real flat package with a stand-in payload
        payload = self.base / 'payload'
        for name in ('AppleIntelTGLCompat', 'AppleIntelTGLGraphics', 'AppleIntelTGLGraphicsFramebuffer'):
            write(payload / f'Library/Extensions/{name}.kext/Contents/Info.plist', f'{name}\n')
        for name in ('AppleIntelTGLGraphicsGLDriver', 'AppleIntelTGLGraphicsVADriver', 'XeCompilerAdapter'):
            write(payload / f'Library/GPUBundles/{name}.bundle/Contents/Info.plist', f'{name}\n')
        metal = write(payload / 'Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver', 'stock metal\n')
        impostor = write(payload / 'Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/impostor.dylib', 'impostor of Graphics\n')
        write(payload / 'Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/descriptor.dylib', 'descriptor\n')
        write(payload / 'Library/GPUBundles/XeOpenCL/x', 'x\n')
        common = self.base / 'Common.pkg'
        subprocess.run(['/usr/bin/pkgbuild', '--quiet', '--root', str(payload), '--identifier', 'test.Common', '--version', '1', str(common)], check=True)
        subprocess.run(['/usr/bin/productbuild', '--quiet', '--package', str(common), str(dl / 'graphics.pkg')], check=True)

        self.manifest = json.loads(json.dumps(REAL))
        downloads = self.manifest['downloads']
        downloads['nullmoth'].update(file='nullmoth.tar.gz', sha256=sha(dl / 'nullmoth.tar.gz'), sums_sha256=sha(pkg / 'SHA256SUMS'))
        downloads['graphics'].update(file='graphics.pkg', sha256=sha(dl / 'graphics.pkg'))
        self.manifest['installed_files'].update(
            nullmoth_decoders={'libnvdec_h264.dylib': sha(macos / 'libnvdec_h264.dylib'), 'libnvdec_hevc.dylib': sha(macos / 'libnvdec_hevc.dylib')},
            nvk_in=sha(nvk), graphics_metal=sha(metal), graphics_impostor=sha(impostor))
        self.manifest_path = write(self.base / 'manifest.json', json.dumps(self.manifest))
        # A Graphics package with the hash its manifest names, which the installer cannot open: the graphics step fails after nullmoth
        broken = write(dl / 'graphics-broken.pkg', 'not a package\n')
        other = json.loads(json.dumps(self.manifest))
        other['downloads']['graphics'].update(file=broken.name, sha256=sha(broken))
        self.broken_graphics = {'ANV_MANIFEST': str(write(self.base / 'manifest-broken-graphics.json', json.dumps(other)))}

    def run(self, *args, env=None, check=True):
        full = dict(os.environ, ANV_MANIFEST=str(self.manifest_path))
        full.update(env or {})
        r = subprocess.run([sys.executable, '-I', str(SCRIPT), *args, '--root', str(self.root), '--work', str(self.work)], capture_output=True, text=True, env=full)
        if check and r.returncode:
            raise AssertionError(r.stdout + r.stderr)
        return r

    def install(self, *extra, env=None, check=True):
        return self.run('install', '--go', *extra, env=env, check=check)

    def close(self):
        shutil.rmtree(self.base, ignore_errors=True)


class Install(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.addCleanup(self.f.close)
        self.root = self.f.root

    def test_plan_and_dry_runs_write_nothing(self):
        before = tree(self.root)
        self.assertIn('nullmoth', self.f.run('plan').stdout)
        self.assertIn('Without --go', self.f.run('install').stdout)
        self.assertEqual(tree(self.root), before)

    def test_install_puts_the_builds_in_place(self):
        out = self.f.install().stdout
        self.assertIn('The drivers are in /Library', out)
        ext = self.root / 'Library/Extensions'
        for k in KEXTS + ['LatSOFAudio']:
            self.assertEqual(sha(ext / f'{k}.kext/Contents/MacOS/{k}'), sha(self.f.work / f'out/{k}.kext/Contents/MacOS/{k}'))
        self.assertFalse((ext / 'NVRM.kext/Contents/_CodeSignature').exists(), 'the signature of the release must go')
        self.assertFalse((ext / 'NMXAudio.kext').exists(), 'the audio driver of the package must not stay')
        for extra in ('Library/LaunchDaemons/com.nullmoth.backlight.plist', 'Library/NullMoth/backlight.sh', 'Library/NullMoth/added-boot-args'):
            self.assertFalse((self.root / extra).exists(), f'{extra} must not stay')
        macos = self.root / 'Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS'
        self.assertEqual(sha(macos / 'libnvmtl_translate.dylib'), sha(self.f.work / 'out/bundle/libnvmtl_translate.dylib'))
        self.assertEqual(sha(macos / 'libnvdec_h264.dylib'), sha(self.f.work / 'out/bundle/libnvencvt.dylib'))
        self.assertEqual(sha(macos / 'libnvencvt.dylib'), sha(self.f.work / 'out/bundle/libnvencvt.dylib'))
        self.assertEqual(os.readlink(macos / 'libnvdec_hevc.dylib'), 'libnvdec_h264.dylib')
        self.assertEqual(sha(self.root / 'Library/GPUBundles/nvmtl/libvulkan_nouveau.dylib'), sha(self.f.work / 'out/nvmtl/libvulkan_nouveau.dylib'))
        self.assertEqual((self.root / 'Library/GPUBundles/nvmtl/nvrm610.conf').read_text(), 'NVMTL_RES2_WS=1\nNVMTL_NVENCVT=com.apple.WebKit.GPU\n')
        self.assertTrue((self.root / 'Library/Displays/Contents/Resources/Overrides/DisplayVendorID-e77/DisplayProductID-1513').is_file())
        self.assertEqual(subprocess.run(['/usr/bin/codesign', '--verify', str(macos.parent.parent)], capture_output=True).returncode, 0)
        intel = self.root / 'Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS'
        self.assertEqual((intel / 'AppleIntelTGLGraphicsMTLDriver').read_text(), 'stock metal\n')
        self.assertEqual((intel / 'impostor.dylib').read_text(), 'impostor of Graphics\n', 'the bridge stays the one of Graphics')
        self.assertEqual(stat.S_IMODE(os.stat(ext / 'NVRM.kext/Contents/MacOS/NVRM').st_mode), 0o755)
        self.assertEqual((self.root / 'Library/KernelCollections/AuxiliaryKernelExtensions.kc').read_text(), 'collection of the auxkc step\n')
        self.assertTrue((self.root / 'Library/LaunchDaemons/com.nitrosense.nitrod.plist').exists())
        self.assertTrue((self.root / 'Applications/NitroSense.app').is_dir())

    def test_rollback_without_go_changes_nothing(self):
        self.f.install()
        before = tree(self.root)
        self.assertIn('Nothing is changed', self.f.run('rollback').stdout)
        self.assertEqual(tree(self.root), before)

    def assert_no_driver_left(self):
        for dirpath, dirs, files in os.walk(self.root):
            rel = os.path.relpath(dirpath, self.root)
            if rel.startswith('Library/ANV15-52'):
                continue
            self.assertEqual(files, [], f'{rel} still holds {files}')

    def test_rollback_removes_every_file(self):
        self.f.install()
        self.f.run('rollback', '--go')
        self.assert_no_driver_left()

    def test_rollback_works_without_python_from_the_backup_folder(self):
        self.f.install()
        backup = next((self.root / 'Library/ANV15-52').glob('backup-*'))
        r = subprocess.run(['/bin/bash', str(backup / 'rollback.sh'), '--go'], capture_output=True, text=True, env={'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_no_driver_left()

    def test_existing_system_is_refused_then_replaced_with_copies(self):
        old = write(self.root / 'Library/Extensions/NVRM.kext/Contents/MacOS/NVRM', 'someone else\n')
        write(self.root / 'Library/KernelCollections/AuxiliaryKernelExtensions.kc', 'old collection\n')
        before = tree(self.root)
        r = self.f.install(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('clean install', r.stderr)
        self.assertEqual(tree(self.root), before)
        self.f.install('--allow-existing')
        self.assertNotEqual(old.read_text(), 'someone else\n')
        self.f.run('rollback', '--go')
        self.assertEqual(old.read_text(), 'someone else\n')
        self.assertEqual((self.root / 'Library/KernelCollections/AuxiliaryKernelExtensions.kc').read_text(), 'old collection\n')

    def test_a_build_changed_after_the_build_step_stops_before_anything(self):
        before = tree(self.root)
        write(self.f.work / 'out/NVRM.kext/Contents/MacOS/NVRM', 'tampered\n')
        r = self.f.install(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('changed since the build', r.stderr)
        self.assertEqual(tree(self.root), before)

    def test_a_download_with_the_wrong_hash_stops_before_anything(self):
        before = tree(self.root)
        with open(self.f.work / 'dl/graphics.pkg', 'ab') as f:
            f.write(b'x')
        r = self.f.install(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('expected hash', r.stderr)
        self.assertEqual(tree(self.root), before)

    def test_a_step_that_fails_stops_and_rollback_still_works(self):
        r = self.f.install(env=self.f.broken_graphics, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('graphics failed', r.stderr)
        self.assertIn('rollback.sh', r.stderr)
        self.assertFalse((self.root / 'Library/Extensions/LatSOFAudio.kext').exists(), 'the steps after it must not run')
        self.f.run('rollback', '--go')
        self.assert_no_driver_left()

    def test_a_run_that_stopped_goes_on_and_keeps_its_first_copies(self):
        old = write(self.root / 'Library/GPUBundles/XeOpenCL/mine', 'from before\n')
        self.f.install('--allow-existing', env=self.f.broken_graphics, check=False)
        self.assertFalse((self.root / 'Library/Extensions/LatSOFAudio.kext').exists())
        out = self.f.install().stdout
        self.assertIn('same copies', out)
        self.assertIn('done already', out)
        self.assertTrue((self.root / 'Library/Extensions/LatSOFAudio.kext').exists())
        self.f.run('rollback', '--go')
        self.assertEqual(old.read_text(), 'from before\n')
        self.assertFalse((self.root / 'Library/Extensions/NVRM.kext').exists())

    def test_steps_already_done_do_not_stop_the_next_run(self):
        self.f.install('--skip', 'latsof', '--skip', 'auxkc', '--skip', 'nitrosense')
        self.f.install()
        self.assertTrue((self.root / 'Library/Extensions/LatSOFAudio.kext').exists())
        self.assertIn('done already', self.f.run('plan').stdout)

    def backup_folder(self):
        return next((self.root / 'Library/ANV15-52').glob('backup-*'))

    def rollback_sh(self, *args):
        return subprocess.run(['/bin/bash', str(self.backup_folder() / 'rollback.sh'), *args], capture_output=True, text=True, env={'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'})

    def test_a_broken_journal_line_removes_nothing(self):
        # In Recovery the root is the data volume, found from the script's own path: an empty path would mean all of it
        self.f.install()
        journal = self.backup_folder() / 'journal.tsv'
        journal.write_text(journal.read_text() + '\nnitrosense\nnitrosense\t/Library/Extensions\tabs\nnitrosense\t/\tabsent\n')
        r = self.rollback_sh('--go')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout.count('BAD line'), 4, r.stdout)
        self.assertTrue(self.backup_folder().is_dir(), 'the volume and the copies must stay')
        self.assertFalse((self.root / 'Library/Extensions/NVRM.kext').exists(), 'the whole lines still count')

    def test_after_rollback_sh_install_does_everything_again(self):
        self.f.install()
        self.assertEqual(self.rollback_sh('--go').returncode, 0)
        out = self.f.install().stdout
        self.assertNotIn('done already', out)
        self.assertTrue((self.root / 'Library/Extensions/NVRM.kext').is_dir())
        self.assertTrue((self.root / 'Library/Extensions/LatSOFAudio.kext').is_dir())

    def test_a_kext_for_the_efi_that_is_missing_stops_before_anything(self):
        before = tree(self.root)
        shutil.rmtree(self.f.work / 'out/WhateverXe.kext')
        r = self.f.install(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('the EFI needs it', r.stderr)
        self.assertEqual(tree(self.root), before)
        self.assertIn('the EFI needs it', self.f.run('plan').stdout)

    def test_an_nvk_that_was_not_built_stops_before_anything(self):
        before = tree(self.root)
        os.unlink(self.f.work / 'out/nvmtl/libvulkan_nouveau.dylib')
        r = self.f.install(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('nvmtl/libvulkan_nouveau.dylib is not built', r.stderr)
        self.assertEqual(tree(self.root), before)

    def test_a_copy_that_fails_leaves_no_line_and_is_made_again(self):
        unreadable = write(self.root / 'Library/Extensions/NVAccel.kext/Contents/MacOS/NVAccel', 'someone else\n')
        os.chmod(unreadable, 0)
        r = self.f.install('--allow-existing', check=False)
        os.chmod(unreadable, 0o644)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('nullmoth failed', r.stderr)
        self.assertIn('do not restart', r.stderr)
        journal = self.backup_folder() / 'journal.tsv'
        self.assertFalse(journal.exists(), 'no line before every copy of the step is made')
        self.assertEqual(unreadable.read_text(), 'someone else\n')
        self.f.install()
        self.assertNotEqual(unreadable.read_text(), 'someone else\n')
        self.f.run('rollback', '--go')
        self.assertEqual(unreadable.read_text(), 'someone else\n')

    def test_ctrl_c_lets_the_running_command_finish_its_clean_up(self):
        # What NullMoth's installer and Apple's installer get from Ctx.run: stays until Ctrl-C, then cleans up slowly
        mark = str(self.f.base / 'slow')
        slow = write(self.f.base / 'slow.sh', 'trap \'sleep 0.5; echo cleaning up; echo done > "$1.cleaned"; exit 3\' INT\necho > "$1.started"\nwhile :; do sleep 0.1; done\n')
        driver = ('import argparse, importlib.util, sys\n'
                  'spec = importlib.util.spec_from_file_location("postinstall", sys.argv[1])\n'
                  'm = importlib.util.module_from_spec(spec)\n'
                  'spec.loader.exec_module(m)\n'
                  'try:\n'
                  '    m.Ctx(argparse.Namespace(work=sys.argv[2])).run(["/bin/bash", sys.argv[3], sys.argv[4]])\n'
                  'except m.Stop as e:\n'
                  '    sys.exit(f"STOP: {e}")\n')
        p = subprocess.Popen([sys.executable, '-I', '-c', driver, str(SCRIPT), str(self.f.work), str(slow), mark],
                             env=dict(os.environ, ANV_MANIFEST=str(self.f.manifest_path)), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             start_new_session=True, preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
        for _ in range(600):
            if os.path.exists(mark + '.started'):
                break
            time.sleep(0.1)
        self.assertTrue(os.path.exists(mark + '.started'))
        os.killpg(p.pid, signal.SIGINT)
        out, err = p.communicate(timeout=60)
        self.assertNotEqual(p.returncode, 0)
        self.assertTrue(os.path.exists(mark + '.cleaned'), 'its clean-up must not die on a closed pipe')
        self.assertIn('cleaning up', out)
        self.assertIn('interrupted', err)

    def test_a_step_name_that_does_not_exist_is_refused(self):
        before = tree(self.root)
        r = self.f.run('install', '--go', '--skip', 'nonsense', check=False)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(tree(self.root), before)

    def test_a_package_folder_of_another_version_stops_before_anything(self):
        before = tree(self.root)
        with open(self.f.work / 'deps/nullmoth/pkgroot/SHA256SUMS', 'a') as f:
            f.write('\n')
        r = self.f.install(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('run fetch', r.stderr)
        self.assertEqual(tree(self.root), before)

    def test_another_build_cannot_go_on_top_of_a_run_that_stopped(self):
        self.f.install(env=self.f.broken_graphics, check=False)
        built = self.f.work / 'out/manifest.json'
        manifest = json.loads(built.read_text())
        manifest['forks']['WhateverXe'] = 'b' * 40
        built.write_text(json.dumps(manifest))
        r = self.f.install(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('other commits', r.stderr)


class Reading(unittest.TestCase):
    """What verify reads, on sample text: a line that passes has to mean what it says."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('postinstall', SCRIPT)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def test_a_gpu_without_metal_is_not_saved_by_the_next_one(self):
        text = 'Chipset Model: Intel Iris Xe\n  Type: GPU\nChipset Model: NVIDIA GeForce RTX 5050\n  Metal Support: Metal 3\n'
        self.assertFalse(self.m.gpu_has_metal(text, 'Iris Xe'))
        self.assertTrue(self.m.gpu_has_metal(text, 'RTX 5050'))
        self.assertFalse(self.m.gpu_has_metal('', 'RTX 5050'))

    def test_a_build_of_a_newer_commit_is_not_called_different(self):
        rel = 'WhateverXe.kext/Contents/MacOS/WhateverXe'
        with tempfile.NamedTemporaryFile() as f:
            f.write(b'another binary')
            f.flush()
            tested = self.m.MANIFEST['forks']['WhateverXe']['tested_commit']
            self.assertIn('DIFFERENT', self.m.against_tested(rel, f.name, {'WhateverXe': tested}))
            self.assertIn('newer than what was tested', self.m.against_tested(rel, f.name, {'WhateverXe': 'b' * 40}))
            # The sensors are built with NVRM
            rel = 'SMCNvidiaGPU.kext/Contents/MacOS/SMCNvidiaGPU'
            heads = {'SMCNvidiaGPU': self.m.MANIFEST['forks']['SMCNvidiaGPU']['tested_commit'], 'nvidia-macos-driver': 'b' * 40}
            self.assertIn('newer than what was tested', self.m.against_tested(rel, f.name, heads))

    def test_a_bundle_id_is_not_found_inside_a_longer_one(self):
        text = '  1  0 0x1 0x2 0x3 com.nullmoth.NVRMFB (1.0) <1 2>\n  2  0 0x1 0x2 0x3 com.apple.driver.AppleIntelTGLGraphicsFramebuffer (1.0)\n'
        self.assertTrue(self.m.listed(text, 'com.nullmoth.NVRMFB'))
        self.assertFalse(self.m.listed(text, 'com.nullmoth.NVRM'))
        self.assertFalse(self.m.listed(text, 'com.apple.driver.AppleIntelTGLGraphics'))


if __name__ == '__main__':
    unittest.main(verbosity=1)
