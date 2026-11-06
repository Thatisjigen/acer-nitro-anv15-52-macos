# Post-install

Builds the drivers from the latest commit of the `acer/current` branches of the forks and installs them into `/Library`, in order, after a clean install of macOS. The nine kexts for the EFI come from the same build.

> [!CAUTION]
> **These scripts have never run on a clean install, and `install --go` has never run on a real system.** That can only be tried by formatting. Below is what was tried and what was not. Back up your data first.

## Commands

From the repository folder, on a freshly installed macOS, with the network and the build tools (`xcode-select --install`). Xcode is not needed.

| Command | What it does | `sudo` |
| --- | --- | --- |
| `python3 postinstall/postinstall.py doctor` | Read only: machine, macOS build, SIP, boot-args, space | No |
| `python3 postinstall/postinstall.py fetch` | Downloads and checks, in `~/anv15-52-build`, and takes the latest commit of each fork. `--tested` takes the commits last tested instead. REFUSES `sudo` | No |
| `python3 postinstall/postinstall.py build` | Compiles, in the same folder. REFUSES `sudo` | No |
| `python3 postinstall/postinstall.py plan` | **Dry run:** what `install` would do, file by file. Writes nothing | No |
| `sudo python3 postinstall/postinstall.py install --go` | Installs. Without `--go` it is the same as `plan` | Yes |
| `python3 postinstall/postinstall.py state` | What is there now, against what was built | No |
| `python3 postinstall/postinstall.py verify` | After the reboot: kexts loaded, Metal, signatures, hashes | No |
| `sudo python3 postinstall/postinstall.py rollback --go` | Everything back. Without `--go` it says what it would do | Yes |

None of them restarts the PC. **The `full` EFI goes on the USB stick before `install --go`:** the Apple Intel driver ends up in `/Library`, and it needs WhateverXe. The guide is [docs/INSTALL.md](../docs/INSTALL.md). `build` must also have compiled the six kexts for the EFI, or `install` stops before touching the system.

`install` stops:

- if the macOS build is not one that was tested (`--any-build` goes on anyway);
- if the PCI IDs `8086:A7A0` and `10DE:2D98` are missing (`--any-machine`);
- if SIP is on or the boot-args are missing: it means you did not start from this EFI;
- if it finds the drivers already in place (`--allow-existing` replaces them, with copies);
- if a compiled file changed after the build, or a download does not have the expected hash;
- if an earlier run installed builds of other commits: see [updating](#updating).

## The steps, in order

| # | Step | What it installs | From |
| --- | --- | --- | --- |
| 1 | `nullmoth` | Kexts, Metal plugin, NVK and GSP firmware in `/Library/Extensions`, `/Library/GPUBundles`, `/Library/NullMoth` | `nullmoth-nvidia-2.7.2.tar.gz` with its `install.sh`, which also rebuilds the auxiliary collection. It prints a "Done. Reboot now" and an "Undo" of its own: they do not apply here. It also adds its audio driver, `NMXAudio`, and this step removes it: sound here comes from AppleALC, LatSOF-Audio and NMHDA |
| 2 | `graphics` | The `AppleIntelTGL*` kexts and the Intel bundles | `WhateverXe-Graphics-0.4.0.pkg` by b00t0x, with `installer` |
| 3 | `posh` | Two bytes in the installed Intel Metal driver, for the memory leak | `tools/posh_patch.sh` of the WhateverXe-Graphics fork. The patched file is not published: it is made here |
| 4 | `ngshim` | NGShim by umeow0716, with three fixes by JulioNectar, in place of Graphics' `impostor.dylib`, the bridge of the Intel Metal driver. After `posh`, which wants the bundle untouched | `ngshim.m` of umeow0716/NootedGreen, with its hash, and [xefix/xefix.m](xefix/xefix.m), compiled here |
| 5 | `nvrm-kexts` | NVRM, NVRMFB, NVAccel and NVRMAGDC, compiled, over those of the package | `nvidia-macos-driver` |
| 6 | `plugin` | `NVMTLDriver` and `libnvmtl_translate.dylib`, then a new signature for the bundle | `nvidia-macos-driver` |
| 7 | `decoder` | `libnvencvt` in place of NullMoth's two decoders and under its own name, then a new signature. One line in `nvrm610.conf` sends the Aerial wallpaper to it | `nvenc` |
| 8 | `nvk-binds` | NVK without 2940 useless symbol lookups: apps open Metal sooner | `drop_flat_weak_binds.py` in this folder, on the file of the package |
| 9 | `latsof` | `LatSOFAudio.kext`, internal microphone | `LatSOF-Audio`, with the SOF firmware downloaded from sof-bin |
| 10 | `hidpi-panel` | A display override for the CSOT panel, so that macOS offers HiDPI modes. Ignored by any other panel | [overrides/](overrides/) |
| 11 | `auxkc` | The auxiliary kext collection, from `/Library/Extensions` | `kmutil`. It swaps it only if it holds all eight expected IDs |
| 12 | `nitrosense` | `nitrod`, `nitroctl`, LaunchDaemon, `/Applications/NitroSense.app` | `NitroSense-macOS`. It starts at the reboot, as it needs NitroEC from the EFI |

Eight more compiled kexts go in the EFI, not in `/Library`: WhateverXe, AppleALC, IDispHDA, NMHDA, SMCNvidiaGPU, HybridPM, NitroEC and AirportMtkWlan ([efi/README.md](../efi/README.md)). AirportMtkWlan carries the MT7920 firmware, downloaded with its hash from linux-firmware and built into the kext on your machine: MediaTek's licence keeps it out of this repository, so do not publish that kext. SMCNvidiaGPU has to match NVRM, and `build` compiles it together with the NVRM it just made.

**Not installed:** NMIntelFB and its daemon (turned off by `-nmintelfboff`), `NMXAudio`, and `nvutild` and the boot diagnostics, which NullMoth no longer needs.

## The forks

Every change to someone else's project is a commit on a public fork, on the branch `acer/current` (`main` in HybridPM). The commits last tested are in [manifest.json](manifest.json).

| Fork | Upstream | What it adds |
| --- | --- | --- |
| [WhateverXe](https://github.com/Thatisjigen/WhateverXe/tree/acer/current) | [b00t0x/WhateverXe](https://github.com/b00t0x/WhateverXe) 0.7.0 | eDP handoff, sleep and wake, recovery from GPU hangs, USB-C hot plug, HiDPI, HDR. Stock 0.7.0 does not accelerate the Iris Xe on this PC |
| [WhateverXe-Graphics](https://github.com/Thatisjigen/WhateverXe-Graphics/tree/acer/current) | [b00t0x/WhateverXe-Graphics](https://github.com/b00t0x/WhateverXe-Graphics) 0.4.0 | A script that fixes the memory leak in the installed Metal driver; the modified file is not published |
| [nvidia-macos-driver](https://github.com/Thatisjigen/nvidia-macos-driver/tree/acer/current) | [nullmoth/nvidia-macos-driver](https://github.com/nullmoth/nvidia-macos-driver) 2.7.2 | Wake, HDMI audio and zero-copy flips in the kexts; two-GPU fixes, pipeline cache and Photo Booth in the plugin and translator, with patches by Dino-VN and Dat Nguyen, among them the icons |
| [nvenc](https://github.com/Thatisjigen/nvenc/tree/acer/current) | [mickys/nvenc](https://github.com/mickys/nvenc) | NVDEC decoders for the RTX 5050: H.264, HEVC, VP9, AV1 |
| [NitroSense-macOS](https://github.com/Thatisjigen/NitroSense-macOS/tree/acer/current) | [ptnzzn/NitroSense-macOS](https://github.com/ptnzzn/NitroSense-macOS) | The EC of the ANV15-52: fans, modes, charge limit |
| [SMCNvidiaGPU](https://github.com/Thatisjigen/SMCNvidiaGPU/tree/acer/current) | [zzzyy678/SMCNvidiaGPU](https://github.com/zzzyy678/SMCNvidiaGPU) | RTX sensors, built together with NVRM |
| [LatSOF-Audio](https://github.com/Thatisjigen/LatSOF-Audio/tree/acer/current) | [pokipoi/LatSOF-Audio](https://github.com/pokipoi/LatSOF-Audio) | Raptor Lake-P, automatic DSP start. Firmware not included |
| [AppleALC](https://github.com/Thatisjigen/AppleALC/tree/acer/current) | [acidanthera/AppleALC](https://github.com/acidanthera/AppleALC) 1.9.8 | Layouts 66 and 67 for this ALC245, and IDispHDA, the audio of the Iris Xe over USB-C |
| [SimpleMtkWlan](https://github.com/Thatisjigen/SimpleMtkWlan/tree/acer/current) | [e5u/SimpleMtkWlan](https://github.com/e5u/SimpleMtkWlan) 1.6.0 | The MT7920, `14C3:7920`: detection and firmware as in Linux, and Wi-Fi 6 behind `-mtkhe` with the access point's BSS color. GPL-2.0; the firmware is generated at build, not in Git |
| [SimpleMtkBtFw](https://github.com/Thatisjigen/SimpleMtkBtFw/tree/acer/current) | [flxxxxddd/SimpleMtkBtFw](https://github.com/flxxxxddd/SimpleMtkBtFw) 1.1.0 | The Bluetooth patcher prepares USB buffers read only: no backtrace for every USB transfer |
| [HybridPM](https://github.com/Thatisjigen/HybridPM) | XE-PM of [JulioNectar](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe) | A standalone Lilu plugin; on with `-hpm` |

**Do not open pull requests upstream from these branches** without rewriting and understanding the code: parts were written with AI tools, and NullMoth does not accept AI-written contributions. The original authors stay the authors of the commits taken from them.

## Hash checks

- **Downloads:** each archive has its SHA-256 in [manifest.json](manifest.json). If it does not match, the file is deleted and everything stops. The NullMoth package is also checked against its own `SHA256SUMS`, whose hash is in the manifest: a folder unpacked from another version does not pass.
- **Forks:** `fetch` takes the head of each branch, so there is no hash to compare with beforehand: Git checks that the sources are that commit, and `fetch` says when one is newer than what was last tested. `fetch --tested` takes the commits listed in the manifest. `posh_patch.sh` comes from the head of its fork as well, and it still refuses any Metal driver but the one of Graphics 0.4.0.
- **Compiled files:** `build` writes the commits and the hash of each file in `out/manifest.json`, and `install` refuses a file changed afterwards. Then each step reads back what it wrote.
- **Against what was tested:** `build` compares each file with the one tested on the reference machine, and says whether it is the same file, or that its fork is newer than what was tested. A difference is a warning, not a stop: another compiler changes the files.

## Copies and rollback

Before each step, everything the step touches goes to `/Library/ANV15-52/backup-<date>/files`, and `journal.tsv` notes what was there and what was not, only once all the step's copies are made. If a step stops, running `install --go` again goes on from there with the same copies. Ctrl-C does the same, and lets the running command finish its clean-up.

`rollback` reads the journal from the bottom: what was there comes back, what was not is removed. **It is always complete:** half way, the kexts on disk would not match the auxiliary collection. An incomplete line in the journal is not acted on, and is reported. The same can be done from Recovery with `rollback.sh`, which does not need Python: [docs/RECOVERY.md](../docs/RECOVERY.md). After a rollback, `install --go` starts from the beginning.

These do not go back: the NVRAM variables NullMoth clears, the `installer` receipts in `/var/db/receipts`, and the EFI, which is separate.

## Updating

`fetch` and `build` again take the latest commits, and then the EFI and `/Library` get them together. `install` does not go on top of builds of other commits, so it is a rollback followed by an install, before you restart:

```bash
python3 postinstall/postinstall.py fetch
```

```bash
python3 postinstall/postinstall.py build
```

```bash
python3 efi/build_efi.py build --profile full --compiled ~/anv15-52-build/out
```

```bash
python3 efi/build_efi.py deploy --profile full --volume /Volumes/OPENCORE --go
```

```bash
sudo python3 postinstall/postinstall.py rollback --go
```

```bash
sudo python3 postinstall/postinstall.py install --go
```

SMCNvidiaGPU is built together with NVRM, so the two stay together even when only one of them moved. If a fork moves to a new base, such as a newer NullMoth package, `manifest.json` has to change with it: `fetch` does not know that by itself. Like everything else on this page, this path has only been tried on a copy of the system tree.

## What was really tried

On one machine, with macOS 26.7.2 (25G332), Command Line Tools 26.6, clang 21.0.0 and SDK 26.5, at the commits listed in the manifest. **Nothing was installed by these scripts.** The drivers themselves, as a set, have had one clean boot and one sleep cycle on that machine, and no long measure.

**`fetch` and `build` from zero, in an empty folder:** about 15 minutes in all, 2.4 GB. All download hashes matched; WhateverXe passed 203 of 203 CPU tests. The forks on GitHub carry the code the test machine runs, without the codes of a work log in names, comments and strings. So 14 of 21 files are the same file as the running ones, and the others differ only where the code does not:

| File | Result |
| --- | --- |
| NVRM, NVRMFB, NVAccel, NVRMAGDC | **The same file, byte for byte** |
| `NVMTLDriver` (before the bundle's signature) | **The same file** |
| NGShim with `xefix.m`, LatSOFAudio, NMHDA | **The same file** |
| SMCNvidiaGPU, HybridPM, AppleALC, IDispHDA, NitroEC, SimpleMtkBtPatcher | **The same file** |
| AirportMtkWlan | Differs only in its version string, which carries the short commit of the branch it is built from: built with the string of the one that ran, it is the same file |
| WhateverXe | Same code. The running one has the old names of its diagnostics, its IORegistry keys among them, and its UUID depends on the paths of the objects |
| `nitrod`, `nitroctl`, NitroSense.app | Same code. The running ones still have the date of an EC dump in their texts, and the app a help line that pointed at the work log |
| `libnvencvt` | Same code. The running one was built before one log line lost a code of the work log, with another version string, in another folder |
| `libnvmtl_translate` | Same sources. The running one keeps the paths of the folder it was built in; here they read `/build/translator`. `build` always compiles it in `/private/tmp/anv15-52-translator`, because cargo puts that path in the hash of its symbols |

The files that match were built separately, in another folder. `libnvencvt` and `libnvmtl_translate`, built again in a second folder, come out the same each time, the translator also with Rust and crates downloaded again. This says the `acer/current` branches on GitHub really are what runs on that machine, NVRM and the kexts included. It does not say they work on another one.

**JulioNectar's fixes:** compute ordered against render and blit, working barriers in serial compute encoders, no rectangles in WindowServer's blur. They are in every Metal process on the Iris Xe, WindowServer included. What they fix is declared by the author, on his Dell XPS 13 Plus; on the test machine they have had two boots and one sleep cycle with no reset, and no gain was measured. [docs/RECOVERY.md](../docs/RECOVERY.md) says how to turn them off live.

**NVAccel, something to know:** it is compiled without `NM_TAHOE`, the variant NullMoth uses for macOS 15, while its release for Tahoe uses the other one. On Tahoe this variant takes 19 `IOAccel*` methods from the Intel kext `AppleIntelTGLGraphics` (`kmutil libraries`), so without Graphics the auxiliary collection should not build, though that was not tried: it is one reason why `graphics` comes before `nvrm-kexts`. It has run this way on the test machine, and the scripts stay on what was tested. Whether it has to do with anything still open was not investigated.

**The logic of `install` and `rollback`, on a fake system:** `python3 tests/test_postinstall.py`, 23 tests with stand-in files: refusals, copies, going on after an error or Ctrl-C, rollback with and without Python, broken journal lines.

**`install --go` with the real files, on a copy of the system tree** (`--root`, no `sudo`; `kmutil`, `installer` and `launchctl` do not run, everything else does, `posh_patch.sh` included). The resulting tree was then compared with the running system:

| Folder | Same | Different | What changes |
| --- | --- | --- | --- |
| `/Library/Extensions` | 19 files of 23 | 4 | The `Info.plist` of four kexts, only for the version: 2.6.6 on the machine, 2.7.2 here. The binaries are the same. The machine also has NMIntelFB and Apple's HighPoint kexts |
| `/Library/GPUBundles` | 120 files | 5 | The decoder under its two names and the translator, see above; the plugin and its seal, which follow them. The machine also has the shader caches |
| NitroSense, app and daemon | 8 of 8 | 0 | The machine also has its `config.json` |
| Panel override | 1 of 1 | 0 | |

The patched Metal driver comes out with the same hash as on the machine (`b24816e8`). The rollback left the copy empty, and after it `install` started from the beginning.

**`doctor`, `plan`, `state` and `verify` on the running system:** they run without writing anything. `verify` passes on every line: 13 kexts loaded, Metal on both GPUs, patched Metal driver, bundle signature, `nitrod` running.

**`deploy` of the EFI:** on a FAT test image, not on a real stick: first write, replacement, and refusal of a broken `config.plist` without touching the one already written.

**Recovery:** the commands `rollback.sh` uses are in the 26.6.2 recovery image; Python is not.

**Following the branches:** `fetch` going back to an older commit with `--tested` and forward to the head without it, on one fork, and `build` then calling the file newer than what was tested, not different.

## What was not tried

- `install --go` on a real system. In particular: `kmutil` run from here, the `install.sh` of **2.7.2** (the test machine went through the one of 2.5.5, then the pieces by hand), `installer` and `launchctl`.
- The reboot after all this, on a system where the pieces arrive together. This exact combination has never run.
- A real rollback, from the system or from Recovery.
- Any other ANV15-52.

## If you update something

- A fork moves on: `fetch` takes it by itself. To say it was tested: `python3 tools/update_pins.py --write`, then update `tested_binaries` and the status in the [README](../README.md). Until then the README describes the older commits.
- Before publishing: `bash tools/check_all.sh`.
